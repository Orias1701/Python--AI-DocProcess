import os
import json
import torch # type: ignore
import faiss # type: ignore
import pickle
import logging
import numpy as np # type: ignore
from typing import Any, Dict, List, Tuple

# Thiết lập logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def inspect_torch_path(torch_path: str) -> None:
    """
    Kiểm tra nội dung file .pt để xác định cấu trúc và dữ liệu.
    
    Args:
        torch_path: Đường dẫn đến file .pt (torch_path từ DEFINE)
    """
    try:
        logging.info(f"Đang tải file .pt: {torch_path}")
        data = torch.load(torch_path, map_location=torch.device('cpu'), weights_only=False)
        
        logging.info(f"Kiểu dữ liệu: {type(data)}")
        if isinstance(data, dict):
            logging.info(f"Số lượng khóa cấp cao nhất: {len(data)}")
            for i, (key, value) in enumerate(data.items()):
                logging.info(f"Khóa: {key}, Kiểu giá trị: {type(value)}, Giá trị mẫu: {str(value)[:100]}...")
                if i >= 5:
                    break
        elif isinstance(data, list):
            logging.info(f"Số lượng phần tử: {len(data)}")
            for i, value in enumerate(data[:5]):
                logging.info(f"Phần tử {i}, Kiểu giá trị: {type(value)}, Giá trị mẫu: {str(value)[:100]}...")
        else:
            logging.info(f"Dữ liệu: {str(data)[:100]}...")
    except Exception as e:
        logging.error(f"Lỗi khi tải file .pt: {str(e)}")
        raise


def extract_embeddings_and_data(data: Any, prefix: str = "") -> Tuple[List[Tuple[str, np.ndarray]], Dict[str, Any]]:
    """
    Trích xuất đệ quy embedding và dữ liệu thông thường từ dữ liệu đầu vào.
    Tìm embedding dựa trên khóa chứa 'embedding' (như contents.<i>.Merged_embedding).
    
    Args:
        data: Dữ liệu đầu vào (từ điển, danh sách, v.v.)
        prefix: Tiền tố cho khóa
    """
    embeddings_list = []
    data_mapping = {}
    
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                sub_embeds, sub_data = extract_embeddings_and_data(value, full_key)
                embeddings_list.extend(sub_embeds)
                data_mapping.update(sub_data)
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                for i, item in enumerate(value):
                    sub_embeds, sub_data = extract_embeddings_and_data(item, f"{full_key}.{i}")
                    embeddings_list.extend(sub_embeds)
                    data_mapping.update(sub_data)
            elif isinstance(value, (torch.Tensor, np.ndarray)):
                try:
                    embedding = value.cpu().numpy() if isinstance(value, torch.Tensor) else value
                    if embedding.ndim > 1:
                        embedding = embedding.flatten()
                    embeddings_list.append((full_key, embedding))
                except Exception as e:
                    logging.warning(f"Lỗi khi xử lý embedding tại {full_key}: {str(e)}")
                    data_mapping[full_key] = value
            elif isinstance(value, (list, tuple)) and full_key.lower().find("embedding") != -1:
                try:
                    embedding = np.array(value, dtype=np.float32)
                    if embedding.ndim > 1:
                        embedding = embedding.flatten()
                    embeddings_list.append((full_key, embedding))
                except Exception as e:
                    logging.warning(f"Lỗi khi chuyển danh sách thành embedding tại {full_key}: {str(e)}")
                    data_mapping[full_key] = value
            else:
                data_mapping[full_key] = value
    
    elif isinstance(data, list):
        for i, item in enumerate(data):
            full_key = f"{prefix}.item{i}" if prefix else f"item{i}"
            if isinstance(item, (dict, list)):
                sub_embeds, sub_data = extract_embeddings_and_data(item, full_key)
                embeddings_list.extend(sub_embeds)
                data_mapping.update(sub_data)
            elif isinstance(item, (torch.Tensor, np.ndarray)):
                try:
                    embedding = item.cpu().numpy() if isinstance(item, torch.Tensor) else item
                    if embedding.ndim > 1:
                        embedding = embedding.flatten()
                    embeddings_list.append((full_key, embedding))
                except Exception as e:
                    logging.warning(f"Lỗi khi xử lý embedding tại {full_key}: {str(e)}")
                    data_mapping[full_key] = item
            elif isinstance(item, (list, tuple)) and "embedding" in prefix.lower():
                try:
                    embedding = np.array(item, dtype=np.float32)
                    if embedding.ndim > 1:
                        embedding = embedding.flatten()
                    embeddings_list.append((full_key, embedding))
                except Exception as e:
                    logging.warning(f"Lỗi khi chuyển danh sách thành embedding tại {full_key}: {str(e)}")
                    data_mapping[full_key] = item
            else:
                data_mapping[full_key] = item
    
    return embeddings_list, data_mapping


def create_faiss_index(embeddings: List[Tuple[str, np.ndarray]], nlist: int = 100) -> Tuple[faiss.Index, Dict[str, int]]:
    """
    Tạo chỉ mục FAISS (IndexFlatIP) từ danh sách (khóa, embedding).
    
    Args:
        embeddings: Danh sách các cặp (khóa, embedding)
        nlist: Số lượng cụm cho IndexFlatIP
    """
    if not embeddings:
        raise ValueError("Không tìm thấy embedding trong dữ liệu đầu vào. Vui lòng kiểm tra file .pt.")
    
    embedding_dim = len(embeddings[0][1])
    if not all(len(emb) == embedding_dim for _, emb in embeddings):
        raise ValueError("Tất cả embedding phải có cùng chiều.")
    
    embedding_matrix = np.array([emb for _, emb in embeddings]).astype('float32')    
    logging.info("Đang thêm embedding vào chỉ mục...")

    embedding_dim = embedding_matrix.shape[1]
    
    # Tạo IndexFlatIP
    index = faiss.IndexFlatIP(embedding_dim)
    index.add(embedding_matrix)
    
    key_to_index = {key: idx for idx, (key, _) in enumerate(embeddings)}
    
    return index, key_to_index


def convert_pt_to_faiss(torch_path: str, faiss_path: str, mapping_path: str, data_path: str, data_key: str, nlist: int = 100, use_pickle: bool = False) -> None:

    """
    Chuyển file .pt sang chỉ mục FAISS và lưu ánh xạ khóa cùng dữ liệu thông thường.
    Sử dụng torch_path (torch_path), faiss_path, mapping_path, data_path từ DEFINE.
    
    Args:
        torch_path: Đường dẫn đến file .pt (torch_path)
        faiss_path: Đường dẫn lưu chỉ mục FAISS
        mapping_path: Đường dẫn lưu ánh xạ khóa
        data_path: Đường dẫn lưu dữ liệu thông thường
        use_pickle: Nếu True, lưu dưới dạng pickle thay vì JSON
        nlist: Số lượng cụm cho IndexFlatIP
    """
    try:
        # Kiểm tra file .pt tồn tại
        if not os.path.exists(torch_path):
            raise FileNotFoundError(f"File .pt không tồn tại: {torch_path}")
        
        # Tạo thư mục đầu ra nếu chưa tồn tại
        os.makedirs(os.path.dirname(faiss_path), exist_ok=True)
        
        # Kiểm tra cấu trúc file .pt
        inspect_torch_path(torch_path)
        
        # Tải file .pt
        logging.info(f"Đang tải file .pt: {torch_path}")
        data = torch.load(torch_path, map_location=torch.device('cpu'), weights_only=False)
        
        # Trích xuất embedding và dữ liệu thông thường
        logging.info("Đang trích xuất embedding và dữ liệu...")
        embeddings_list, data_mapping = extract_embeddings_and_data(data)
        
        # Kiểm tra xem có embedding nào không
        if not embeddings_list:
            logging.error("Không tìm thấy embedding nào trong file .pt. Vui lòng kiểm tra cấu trúc dữ liệu.")
            raise ValueError("Không tìm thấy embedding nào trong file .pt.")
        
        logging.info(f"Tìm thấy {len(embeddings_list)} embedding.")
        
        # Tạo chỉ mục FAISS
        logging.info("Đang tạo chỉ mục FAISS...")
        faiss_index, key_to_index = create_faiss_index(embeddings_list, nlist=nlist)
        
        # Lưu chỉ mục FAISS
        logging.info(f"Đang lưu chỉ mục FAISS vào {faiss_path}")
        faiss.write_index(faiss_index, faiss_path)
        
        # Lưu ánh xạ khóa sang chỉ số
        logging.info(f"Đang lưu ánh xạ khóa vào {mapping_path}")
        if use_pickle:
            with open(mapping_path, 'wb') as f:
                pickle.dump(key_to_index, f)
        else:
            with open(mapping_path, 'w', encoding='utf-8') as f:
                json.dump(key_to_index, f, indent=4, ensure_ascii=False)
        
        # Lưu dữ liệu thông thường
        logging.info(f"Đang lưu dữ liệu thông thường vào {data_path}")
        if use_pickle:
            with open(data_path, 'wb') as f:
                pickle.dump(data_mapping, f)
        else:
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(data_mapping, f, indent=4, ensure_ascii=False)
        
        logging.info("Chuyển đổi hoàn tất.")
        
    except Exception as e:
        logging.error(f"Lỗi trong quá trình chuyển đổi: {str(e)}")
        raise