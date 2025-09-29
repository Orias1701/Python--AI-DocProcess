import os
import json
import torch
import faiss
import pickle
import logging
import numpy as np
from typing import Any, Dict, List, Tuple

from . import A0_MyUtils as A0
ex = A0.exc

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class Torch2FaissConverter:
    """
    Chuyển đổi file .pt sang FAISS index + mapping + dữ liệu thường.
    Hành vi giữ nguyên so với bản procedural: vẫn đọc .pt, tạo FAISS index, 
    ghi ra faiss_path, mapping_path, map_data_path.
    """

    def __init__(self, schema_ex_path: str, torch_path: str, faiss_path: str, mapping_path: str, map_data_path: str, keep_last: int = 2, nlist: int = 100, mode: str = None, use_pickle: bool = False):
        self.schema_ex_path = schema_ex_path
        self.torch_path = torch_path
        self.faiss_path = faiss_path
        self.mapping_path = mapping_path
        self.map_data_path = map_data_path
        self.keep_last = keep_last
        self.nlist = nlist
        self.mode = mode
        self.use_pickle = use_pickle
        
    # ====== Helper ======
    def _inspect_torch_path(self) -> Any:
        """In thông tin cấu trúc file .pt"""
        data = ex(lambda: torch.load(self.torch_path, map_location=torch.device("cpu"), weights_only=False))
        if data is None:
            raise RuntimeError(f"Không thể tải file .pt: {self.torch_path}")

        logging.info(f"Kiểu dữ liệu: {type(data)}")
        if isinstance(data, dict):
            logging.info(f"Số lượng khóa cấp cao nhất: {len(data)}")
            for i, (key, value) in enumerate(data.items()):
                logging.info(
                    f"Khóa: {key}, Kiểu giá trị: {type(value)}, Giá trị mẫu: {str(value)[:100]}..."
                )
                if i >= 5:
                    break
        elif isinstance(data, list):
            logging.info(f"Số lượng phần tử: {len(data)}")
            for i, value in enumerate(data[:5]):
                logging.info(
                    f"Phần tử {i}, Kiểu giá trị: {type(value)}, Giá trị mẫu: {str(value)[:100]}..."
                )
        else:
            logging.info(f"Dữ liệu: {str(data)[:100]}...")

        return data

    def _extract_embeddings_and_data(self, data: Any, prefix: str = "") -> Tuple[List[Tuple[str, np.ndarray]], Dict[str, Any]]:
        """
        Trích xuất đệ quy embeddings + dữ liệu thường từ .pt
        """
        embeddings_list = []
        data_mapping = {}

        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else key

                if full_key.startswith(self.mode) or key == self.mode:
                    continue

                if isinstance(value, dict):
                    sub_embeds, sub_data = self._extract_embeddings_and_data(value, full_key)
                    embeddings_list.extend(sub_embeds)
                    data_mapping.update(sub_data)

                elif isinstance(value, list) and value and isinstance(value[0], dict):
                    for i, item in enumerate(value):
                        sub_embeds, sub_data = self._extract_embeddings_and_data(item, f"{full_key}.{i}")
                        embeddings_list.extend(sub_embeds)
                        data_mapping.update(sub_data)

                elif isinstance(value, (torch.Tensor, np.ndarray)):
                    embedding = ex(lambda: value.cpu().numpy() if isinstance(value, torch.Tensor) else value)
                    if isinstance(embedding, np.ndarray):
                        if embedding.ndim > 1:
                            embedding = embedding.flatten()
                        embeddings_list.append((full_key, embedding))
                    else:
                        data_mapping[full_key] = value

                elif isinstance(value, (list, tuple)) and "embedding" in full_key.lower():
                    embedding = ex(lambda: np.array(value, dtype=np.float32))
                    if isinstance(embedding, np.ndarray):
                        if embedding.ndim > 1:
                            embedding = embedding.flatten()
                        embeddings_list.append((full_key, embedding))
                    else:
                        data_mapping[full_key] = value

                else:
                    data_mapping[full_key] = value

        elif isinstance(data, list):
            for i, item in enumerate(data):
                full_key = f"{prefix}.item{i}" if prefix else f"item{i}"

                if full_key.startswith(self.mode):
                    continue

                if isinstance(item, (dict, list)):
                    sub_embeds, sub_data = self._extract_embeddings_and_data(item, full_key)
                    embeddings_list.extend(sub_embeds)
                    data_mapping.update(sub_data)

                elif isinstance(item, (torch.Tensor, np.ndarray)):
                    embedding = ex(lambda: item.cpu().numpy() if isinstance(item, torch.Tensor) else item)
                    if isinstance(embedding, np.ndarray):
                        if embedding.ndim > 1:
                            embedding = embedding.flatten()
                        embeddings_list.append((full_key, embedding))
                    else:
                        data_mapping[full_key] = item

                elif isinstance(item, (list, tuple)) and "embedding" in prefix.lower():
                    embedding = ex(lambda: np.array(item, dtype=np.float32))
                    if isinstance(embedding, np.ndarray):
                        if embedding.ndim > 1:
                            embedding = embedding.flatten()
                        embeddings_list.append((full_key, embedding))
                    else:
                        data_mapping[full_key] = item

                else:
                    data_mapping[full_key] = item

        return embeddings_list, data_mapping

    def _create_faiss_index(self, embeddings: List[Tuple[str, np.ndarray]]) -> Tuple[faiss.Index, Dict[str, int]]:
        """
        Tạo chỉ mục FAISS (IndexFlatIP) từ embeddings
        """
        if not embeddings:
            raise ValueError("Không tìm thấy embedding trong dữ liệu đầu vào.")

        embedding_dim = len(embeddings[0][1])
        if not all(len(emb) == embedding_dim for _, emb in embeddings):
            raise ValueError("Tất cả embedding phải có cùng chiều.")

        embedding_matrix = np.array([emb for _, emb in embeddings]).astype("float32")
        logging.info("Đang thêm embedding vào chỉ mục...")

        index = faiss.IndexFlatIP(embedding_dim)
        index.add(embedding_matrix)

        key_to_index = {key: idx for idx, (key, _) in enumerate(embeddings)}
        return index, key_to_index

    # ====== Public ======
    def convert(self) -> None:
        """Thực hiện full pipeline: đọc .pt → extract → FAISS → ghi file"""

        if not os.path.exists(self.torch_path):
            raise FileNotFoundError(f"File .pt không tồn tại: {self.torch_path}")

        os.makedirs(os.path.dirname(self.faiss_path), exist_ok=True)

        # 1. Inspect
        self._inspect_torch_path()

        # 2. Load .pt
        logging.info(f"Đang tải file .pt: {self.torch_path}")
        data = ex(lambda: torch.load(self.torch_path, map_location=torch.device("cpu"), weights_only=False))
        if data is None:
            raise RuntimeError(f"Không thể tải dữ liệu từ file .pt: {self.torch_path}")

        # 3. Extract
        logging.info("Đang trích xuất embedding và dữ liệu...")
        embeddings_list, data_mapping = self._extract_embeddings_and_data(data)
        if not embeddings_list:
            raise ValueError("Không tìm thấy embedding nào trong file .pt.")
        logging.info(f"Tìm thấy {len(embeddings_list)} embedding.")

        # 4. Build FAISS
        logging.info("Đang tạo chỉ mục FAISS...")
        faiss_index, key_to_index = self._create_faiss_index(embeddings_list)

        # 5. Save FAISS
        ex(lambda: faiss.write_index(faiss_index, self.faiss_path))

        # 6. Save mapping
        logging.info(f"Đang lưu ánh xạ khóa vào {self.mapping_path}")
        if self.use_pickle:
            ex(lambda: pickle.dump(key_to_index, open(self.mapping_path, "wb")))
        else:
            ex(lambda: json.dump(key_to_index, open(self.mapping_path, "w", encoding="utf-8"), indent=4, ensure_ascii=False))

        # 7. Save data
        logging.info(f"Đang lưu dữ liệu thông thường vào {self.map_data_path}")
        if self.use_pickle:
            ex(lambda: pickle.dump(data_mapping, open(self.map_data_path, "wb")))
        else:
            ex(lambda: json.dump(data_mapping, open(self.map_data_path, "w", encoding="utf-8"), indent=4, ensure_ascii=False))

        logging.info("Chuyển đổi hoàn tất.")
