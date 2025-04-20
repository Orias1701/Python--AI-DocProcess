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
Tìm kiếm văn bản liên quan đến câu hỏi sử dụng FAISS IndexFlatIP.

Args:
    query: Câu hỏi dạng văn bản
    embedd_model: Tên mô hình embedding (EMBEDD_MODEL từ DEFINE)
    faiss_path: Đường dẫn chỉ mục FAISS (faiss_path từ DEFINE)
    mapping_path: Đường dẫn file ánh xạ (maping_path từ DEFINE)
    mapping_data: Đường dẫn file dữ liệu text (maping_data từ DEFINE)
    device: Thiết bị PyTorch (device từ DEFINE, ví dụ: cuda hoặc cpu)
    k: Số lượng kết quả trả về

Returns:
    Danh sách các kết quả: {"text": văn bản, "faiss_score": điểm FAISS}
"""

logging.getLogger("sentence_transformers").setLevel(logging.CRITICAL)
logging.getLogger("transformers").setLevel(logging.CRITICAL)
for name in logging.Logger.manager.loggerDict:
    if "sentence_transformers" in name or "transformers" in name:
        logging.getLogger(name).setLevel(logging.CRITICAL)
        
warnings.filterwarnings("ignore", module="sentence_transformers")

os.environ["TOKENIZERS_PARALLELISM"] = "false"

def search_faiss_index(
    query: str,
    embedd_model: str,
    faiss_path: str,
    mapping_path: str,
    mapping_data: str,
    device: str = "cuda",
    k: int = 10,
    batches: bool = False,
) -> List[Dict[str, Any]]:

    try:
        model = SentenceTransformer(embedd_model, device=device)
        query_embedding = model.encode(query, convert_to_tensor=True, device=device, show_progress_bar = batches).cpu().numpy()
        
        # Chuẩn hóa query embedding cho IndexFlatIP
        query_embedding = query_embedding / np.linalg.norm(query_embedding, axis=-1, keepdims=True)
        
        index = faiss.read_index(faiss_path)
                
        with open(mapping_path, 'r', encoding='utf-8') as f:
            key_to_index = json.load(f)

        with open(mapping_data, 'r', encoding='utf-8') as f:
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