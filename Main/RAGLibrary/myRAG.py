import os
import json
import torch
import faiss
import numpy as np
from typing import Any, Dict, List
from transformers import AutoTokenizer, AutoModel
from sentence_transformers import SentenceTransformer
from sentence_transformers import CrossEncoder
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted


""" PREPROCESS TEXT """

def preprocess_text(text):
    import re
    if isinstance(text, list):
        return [preprocess_text(t) for t in text]
    if isinstance(text, str):
        text = text.strip()
        text = re.sub(r'[^\w\s\(\)\.\,\;\:\-–]', '', text)
        text = re.sub(r'[ ]{2,}', ' ', text)
        return text
    return text


""" PREPROCESS DATA """

def preprocess_data(data):
    if isinstance(data, dict):
        return {key: preprocess_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [preprocess_data(item) for item in data]
    else:
        return preprocess_text(data)


""" LOAD SCHEMA """

def load_schema(schema_path):
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Schema file not found: {schema_path}")
        return {}
    except json.JSONDecodeError:
        print(f"Invalid schema file: {schema_path}")
        return {}


""" FLATTEN JSON """

def flatten_json(data, prefix, schema):
    flat = {}
    
    if schema is None:
        schema = {}

    # If data is a dictionary
    if isinstance(data, dict):
        for key, value in data.items():
            new_prefix = f"{prefix}{key}" if prefix else key
            if isinstance(value, (dict, list)):
                flat.update(flatten_json(value, f"{new_prefix}.", schema))
            else:
                flat[new_prefix] = value

    # If data is a non-empty list
    elif isinstance(data, list) and data:
        flat[prefix.rstrip('.')] = data

    return flat


""" CREATE EMBEDDING """

def create_embedding(model, device, texts, batch_size=32):
    try:
        if isinstance(texts, str):
            texts = [texts]
        embeddings = model.encode(texts, batch_size=batch_size, convert_to_tensor=True, device=device)
        return embeddings
    except RuntimeError as e:
        if "CUDA out of memory" in str(e):
            print("VRAM overflow. Switching to CPU.")
            model.to("cpu")
            return model.encode(texts, batch_size=batch_size, convert_to_tensor=True, device="cpu")
        raise e


""" CREATE EMBEDDINGS """

def create_embeddings(model, MERGE, data, schema, device, batch_size):
    flat_data = flatten_json(data, "", schema)
    embeddings = {}
    
    if MERGE == "Merge":
        merged_texts = []
        for key, value in flat_data.items():
            if schema.get(key) in ["string", "array"]:
                if isinstance(value, str) and value.strip():
                    merged_texts.append(preprocess_text(value))
                elif isinstance(value, list):
                    text = "\n".join([preprocess_text(str(item)) for item in value if str(item).strip()])
                    if text.strip():
                        merged_texts.append(text)
        if merged_texts:
            merged_text = "\n".join(merged_texts)
            if merged_text.strip():
                embedding = create_embedding(model, device, merged_text, batch_size)
                embeddings["merged_embedding"] = embedding
    else:
        for key, value in flat_data.items():
            if schema.get(key) in ["string", "array"]:
                if isinstance(value, str) and value.strip():
                    embedding = create_embedding(model, device, preprocess_text(value), batch_size)
                    embeddings[f"{key}_embedding"] = embedding
                elif isinstance(value, list):
                    text = "\n".join([preprocess_text(str(item)) for item in value if str(item).strip()])
                    if text.strip():
                        embedding = create_embedding(model, device, text, batch_size)
                        embeddings[f"{key}_embedding"] = embedding

    # Combine original data and embeddings
    if MERGE == "Merge":
        result = [{} for _ in range(len(data))] if isinstance(data, list) else {}
    else:
        result = data.copy()

    for embed_key, embed_value in embeddings.items():
        if MERGE == "Merge":
            result["merged_text"] = merged_text
            result["merged_embedding"] = embed_value.tolist()
        else:
            keys = embed_key.split("_embedding")[0].split('.')
            current = result
            for i, k in enumerate(keys[:-1]):
                current = current.setdefault(k, {})
            current[keys[-1] + "_embedding"] = embed_value.tolist()
    return result


""" JSON EMBEDDINGS """

def json_embeddings(MERGE, json_file_path, torch_path, schema_path, device, DATA_KEY, model, batch_size):
    # Check if embedding file already exists
    if os.path.exists(torch_path):
        print(f"\nEmbedding loaded from {torch_path}\n")
        return

    print(f"\nCreating embeddings for JSON data...\n")
    try:
        # Load schema
        schema = load_schema(schema_path)
        if not schema:
            raise ValueError("Schema is empty or invalid")

        # Read JSON file
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data_pairs = json.load(f)

        if not isinstance(data_pairs, list):
            data_pairs = [data_pairs]

        # Process each JSON object
        output_data = []
        for data in data_pairs:
            # Preprocess text
            flat_data = flatten_json(data, "", schema)
            for key, value in flat_data.items():
                if isinstance(value, (str, list)):
                    flat_data[key] = preprocess_text(value)
            
            # Restore original structure with preprocessed data
            processed_data = data.copy()
            for key, value in flat_data.items():
                keys = key.split('.')
                current = processed_data
                for k in keys[:-1]:
                    current = current[k]
                current[keys[-1]] = value

            # Create embeddings
            result = create_embeddings(model, MERGE, processed_data, schema, device, batch_size)
            output_data.append(result)

        # Save embeddings
        embeddings_only = []
        for item in output_data:
            flat_item = flatten_json(item, "", schema)
            if MERGE == "Merge":
                embed_dict = {k: v for k, v in flat_item.items() if k == "merged_embedding"}
            else:
                embed_dict = {k: v for k, v in flat_item.items() if k.endswith("_embedding")}
            embeddings_only.append(embed_dict)

        torch.save({
            DATA_KEY: output_data,
            "embeddings": embeddings_only
        }, torch_path)

        print(f"Embedding tensor saved to {torch_path}")

    except Exception as e:
        print(f"Error processing JSON with embeddings: {e}")
        raise


""" SEARCH """

"""
Tìm kiếm văn bản liên quan đến câu hỏi sử dụng FAISS IndexFlatIP.

Args:
    query: Câu hỏi dạng văn bản
    embedd_model: Tên mô hình embedding (EMBEDD_MODEL từ DEFINE)
    faiss_path: Đường dẫn chỉ mục FAISS (faiss_path từ DEFINE)
    mapping_path: Đường dẫn file ánh xạ (maping_path từ DEFINE)
    data_path: Đường dẫn file dữ liệu text (maping_data từ DEFINE)
    device: Thiết bị PyTorch (device từ DEFINE, ví dụ: cuda hoặc cpu)
    k: Số lượng kết quả trả về

Returns:
    Danh sách các kết quả: {"text": văn bản, "faiss_score": điểm FAISS}
"""

def search_faiss_index(
    query: str,
    embedd_model: str,
    faiss_path: str,
    mapping_path: str,
    data_path: str,
    device: str = "cuda",
    k: int = 10
) -> List[Dict[str, Any]]:

    try:
        model = SentenceTransformer(embedd_model, device=device)
        query_embedding = model.encode(query, convert_to_tensor=True, device=device).cpu().numpy()
        
        # Chuẩn hóa query embedding cho IndexFlatIP
        query_embedding = query_embedding / np.linalg.norm(query_embedding, axis=-1, keepdims=True)
        
        index = faiss.read_index(faiss_path)
                
        with open(mapping_path, 'r', encoding='utf-8') as f:
            key_to_index = json.load(f)

        with open(data_path, 'r', encoding='utf-8') as f:
            data_mapping = json.load(f)
        
        # Tìm kiếm k kết quả gần nhất
        scores, indices = index.search(query_embedding.reshape(1, -1), k)
        
        # Ánh xạ
        results = []
        index_to_key = {v: k for k, v in key_to_index.items()}
        for idx, score in zip(indices[0], scores[0]):
            if idx not in index_to_key:
                continue
            key = index_to_key[idx]
            text_key = key.replace("Merged_embedding", "Merged_text")
            text = data_mapping.get(text_key, "")
            if not text:
                text = next((v for k, v in data_mapping.items() if k.startswith(key.split("Merged_embedding")[0]) and isinstance(v, (str, list))), "")
            text = text if isinstance(text, str) else " ".join(text) if isinstance(text, list) else ""
            if text:
                results.append({
                    "text": text,
                    "faiss_score": float(score),
                    "key": key
                })
        
        return results
    
    except Exception as e:
        print(f"Error during search: {str(e)}")
        raise


""" RERANK """

"""
Xếp hạng lại kết quả sử dụng mô hình reranker.

Args:
    query: Câu hỏi dạng văn bản
    results: Danh sách kết quả sơ bộ từ search_faiss_index
    reranker_model: Tên mô hình reranker (RERANK_MODEL từ DEFINE)
    device: Thiết bị PyTorch (cuda hoặc cpu)
    k: Số lượng kết quả trả về sau reranking

Returns:
    Danh sách các kết quả: {"text": văn bản, "rerank_score": điểm reranker, "faiss_score": điểm FAISS}
"""

def rerank_results(
    query: str,
    results: List[Dict[str, Any]],
    reranker_model: str,
    device: str = "cuda",
    k: int = 5
) -> List[Dict[str, Any]]:
    try:
        if not results:
            return []
        
        # Tải mô hình reranker
        reranker = CrossEncoder(reranker_model, device=device)
        
        # Tạo cặp [query, text] để rerank
        pairs = [[query, result["text"]] for result in results]
        
        # Tính điểm rerank
        rerank_scores = reranker.predict(pairs)
        
        # Gắn điểm rerank vào kết quả
        for i, score in enumerate(rerank_scores):
            results[i]["rerank_score"] = float(score)
        
        # Sắp xếp theo rerank_score và lấy top k
        sorted_results = sorted(results, key=lambda x: x["rerank_score"], reverse=True)[:k]
        
        # Định dạng kết quả cuối
        final_results = [
            {
                "text": result["text"],
                "rerank_score": result["rerank_score"],
                "faiss_score": result["faiss_score"]
            }
            for result in sorted_results
        ]
        
        return final_results
    
    except Exception as e:
        print(f"Error during rerank: {str(e)}")
        raise


""" RESPOND """

"""
Lọc kết quả rerank và sinh câu trả lời tự nhiên bằng Gemini 1.5 Pro.

Args:
    query: Câu hỏi dạng văn bản
    results: Danh sách kết quả từ rerank_results ({'text', 'rerank_score', 'faiss_score', 'key'})
    responser_model: Tên mô hình Gemini (mặc định gemini-2.0-flash-exp)
    device: Thiết bị PyTorch (cuda hoặc cpu, chỉ để tương thích)
    score_threshold: Ngưỡng rerank_score để lọc
    max_results: Số kết quả tối đa để tổng hợp
    gemini_api_key: API key của Google AI Studio

Returns:
    Tuple: (câu trả lời tự nhiên, danh sách kết quả được lọc)
"""

def respond_naturally(
    query: str,
    results: List[Dict[str, Any]],
    responser_model: str = "gemini-2.0-flash-exp",
    score_threshold: float = 0.85,
    max_results: int = 3,
    gemini_api_key: str = None
) -> tuple[str, List[Dict[str, Any]]]:

    try:
        # Lọc kết quả theo ngưỡng rerank_score và độ dài văn bản
        filtered_results = [
            r for r in results
            if r["rerank_score"] > score_threshold and len(r["text"]) > 50
        ][:max_results]
        
        if not filtered_results:
            return "Không tìm thấy thông tin phù hợp với câu hỏi.", []
        
        # Ghép văn bản được lọc thành context
        context = "\n".join([r["text"] for r in filtered_results])
        
        genai.configure(api_key=gemini_api_key)
        
        # Kiểm tra trạng thái mô hình
        model = genai.GenerativeModel(responser_model)
        
        # Tạo prompt cho mô hình
        prompt = (
            f"Câu hỏi: {query}\n"
            f"Thông tin: {context}\n"
            f"Trả lời ngắn gọn và tự nhiên bằng tiếng Việt:"
        )
        
        # Sinh câu trả lời
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 200,
                "temperature": 0.7,
                "top_p": 0.9
            }
        )
        
        # Xử lý response
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, "content") and candidate.content.parts:
                response_text = candidate.content.parts[0].text.strip()
            else:
                raise ValueError("Không tìm thấy nội dung trong candidate của Gemini API.")
        else:
            raise ValueError("Response không có candidates.")

        return response_text, filtered_results
    
    except ResourceExhausted as e:
        error_msg = f"Vượt giới hạn API"
        print(error_msg)
        return ("Vượt giới hạn API, vui lòng thử lại sau.", [])