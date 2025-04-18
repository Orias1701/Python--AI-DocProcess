import json
import faiss
import numpy as np
from typing import Any, Dict, List
import google.generativeai as genai
from sentence_transformers import CrossEncoder
from sentence_transformers import SentenceTransformer
from google.api_core.exceptions import ResourceExhausted


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
    k: int = 10,
    disable: bool = True,
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
    k: int = 5,
    disable: bool = True,
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
    # prompt,
    query: str,
    results: List[Dict[str, Any]],
    responser_model: str = "gemini-2.0-flash-exp",
    score_threshold: float = 0.85,
    max_results: int = 3,
    gemini_api_key: str = None,
    disable: bool = True,
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