import os
import json
import warnings
import faiss
import logging
import numpy as np
from typing import Any, Dict, List
from sentence_transformers import SentenceTransformer

""" SEARCH """

"""
Tìm kiếm văn bản liên quan đến câu hỏi sử dụng FAISS IndexFlatIP, chỉ so sánh với Câu hỏi Embedding
và trả về nội dung gộp của Câu hỏi và Câu trả lời.

Args:
    MERGE: Chế độ ánh xạ ('Merge' để dùng logic cũ, bất kỳ giá trị khác để dùng logic mới)
    query: Câu hỏi dạng văn bản
    embedd_model: Tên mô hình embedding
    faiss_path: Đường dẫn chỉ mục FAISS
    mapping_path: Đường dẫn file ánh xạ
    mapping_data: Đường dẫn file dữ liệu text
    device: Thiết bị PyTorch (cuda hoặc cpu)
    k: Số lượng kết quả trả về
    min_score: Ngưỡng điểm FAISS tối thiểu
    batches: Có hiển thị thanh tiến trình không

Returns:
    Danh sách các kết quả: {"text": văn bản gộp (câu hỏi + câu trả lời), "faiss_score": điểm FAISS, "key": khóa}
"""

logging.getLogger("sentence_transformers").setLevel(logging.CRITICAL)
logging.getLogger("transformers").setLevel(logging.CRITICAL)
for name in logging.Logger.manager.loggerDict:
    if "sentence_transformers" in name or "transformers" in name:
        logging.getLogger(name).setLevel(logging.CRITICAL)

warnings.filterwarnings("ignore", module="sentence_transformers")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

def search_faiss_index(
    MERGE: str,
    query: str,
    embedd_model: str,
    faiss_path: str,
    mapping_path: str,
    mapping_data: str,
    device: str = "cuda",
    k: int = 10,
    min_score: float = 0.0,
    batches: bool = False,
) -> List[Dict[str, Any]]:
    try:
        # Tải mô hình SentenceTransformer
        model = SentenceTransformer(embedd_model, device=device)
        query_embedding = model.encode(query, convert_to_tensor=True, device=device, show_progress_bar=batches).cpu().numpy()
        
        # Chuẩn hóa query embedding
        query_embedding = query_embedding / np.linalg.norm(query_embedding, axis=-1, keepdims=True)
        
        # Đọc chỉ mục FAISS
        index = faiss.read_index(faiss_path)
        
        # Đọc file ánh xạ
        with open(mapping_path, 'r', encoding='utf-8') as f:
            key_to_index = json.load(f)

        # Đọc file dữ liệu văn bản
        with open(mapping_data, 'r', encoding='utf-8') as f:
            data_mapping = json.load(f)
        
        # Tìm kiếm k kết quả gần nhất
        k *= 2  # Tăng k để đảm bảo đủ kết quả sau khi lọc
        scores, indices = index.search(query_embedding.reshape(1, -1), k)
        
        # Ánh xạ kết quả
        results = []
        index_to_key = {v: k for k, v in key_to_index.items()}
        processed_indices = set()  # Theo dõi các contents.<i> đã xử lý
        
        for idx, score in zip(indices[0], scores[0]):
            if idx not in index_to_key:
                continue
            if score < min_score:
                continue
            key = index_to_key[idx]
            
            # Chỉ xử lý nếu là Câu hỏi Embedding
            if "Câu hỏi Embedding" not in key:
                continue
            
            # Lấy chỉ số contents (ví dụ: contents.0)
            content_idx = key.split(".")[1]  # contents.<i>
            if content_idx in processed_indices:
                continue  # Bỏ qua nếu contents.<i> đã được xử lý
            processed_indices.add(content_idx)
            
            # Ánh xạ văn bản câu hỏi
            if MERGE == "Merge":
                # Logic cũ: không phù hợp, nhưng giữ cho tương thích
                question_text_key = key.replace("Merged_embedding", "Merged_text")
            else:
                # Logic mới: ánh xạ Câu hỏi Embedding → Câu hỏi
                question_text_key = key.replace("Câu hỏi Embedding", "Câu hỏi")
            
            question_text = data_mapping.get(question_text_key, "")
            if not question_text:
                prefix = key.rsplit(".", 1)[0]
                question_text = next((v for k, v in data_mapping.items() if k.startswith(prefix) and isinstance(v, (str, list))), "")
            question_text = question_text if isinstance(question_text, str) else " ".join(question_text) if isinstance(question_text, list) else ""
            
            # Tìm khóa và văn bản câu trả lời (chỉ số FAISS = chỉ số câu hỏi + 1)
            answer_idx = idx + 1
            answer_key = index_to_key.get(answer_idx, "")
            if "Câu trả lời Embedding" not in answer_key:
                answer_text = ""  # Không tìm thấy câu trả lời tương ứng
            else:
                if MERGE == "Merge":
                    answer_text_key = answer_key.replace("Merged_embedding", "Merged_text")
                else:
                    answer_text_key = answer_key.replace("Câu trả lời Embedding", "Câu trả lời")
                
                answer_text = data_mapping.get(answer_text_key, "")
                if not answer_text:
                    prefix = answer_key.rsplit(".", 1)[0]
                    answer_text = next((v for k, v in data_mapping.items() if k.startswith(prefix) and isinstance(v, (str, list))), "")
                answer_text = answer_text if isinstance(answer_text, str) else " ".join(answer_text) if isinstance(answer_text, list) else ""
            
            # Gộp nội dung câu hỏi và câu trả lời
            combined_text = f"Câu hỏi: {question_text}\nCâu trả lời: {answer_text}" if question_text and answer_text else question_text or answer_text
            
            # Chỉ thêm kết quả nếu có văn bản
            if combined_text:
                results.append({
                    "text": combined_text,
                    "faiss_score": float(score),
                    "key": key
                })
        
        # Giới hạn số lượng kết quả trả về
        return results
    
    except Exception as e:
        print(f"Error during search: {str(e)}")
        raise