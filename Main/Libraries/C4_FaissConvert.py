import os
import re
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
    - Lọc theo `mode`: bỏ qua nhánh (ví dụ "embeddings"), chỉ giữ nhánh cần thiết (ví dụ "contents").
    - Lọc theo schema: chỉ giữ n subindex cuối trong schema (vd: "Level 3", "Contents").
    - map_data_path: CHỈ ghi dữ liệu thường (không ghi vector embedding).
    """

    def __init__(
        self,
        schema_ex_path: str,
        torch_path: str,
        faiss_path: str,
        mapping_path: str,
        map_data_path: str,
        keep_last: int = 2,
        nlist: int = 100,
        mode: str = None,
        use_pickle: bool = False
    ):
        self.schema_ex_path = schema_ex_path
        self.torch_path = torch_path
        self.faiss_path = faiss_path
        self.mapping_path = mapping_path
        self.map_data_path = map_data_path
        self.keep_last = keep_last
        self.nlist = nlist
        self.mode = mode
        self.use_pickle = use_pickle

        # Đọc schema (nếu có)
        self.schema: Dict[str, str] = {}
        if self.schema_ex_path and os.path.exists(self.schema_ex_path):
            with open(self.schema_ex_path, "r", encoding="utf-8") as f:
                self.schema = json.load(f)

        # Xác định các field cần giữ: n field cuối trong schema
        if self.schema:
            fields = list(self.schema.keys())
            self.keep_fields = set(fields[-self.keep_last:])
            logging.info(f"Chỉ giữ {self.keep_last} field cuối trong schema: {self.keep_fields}")
        else:
            self.keep_fields = None
            logging.warning("Không có schema → giữ TẤT CẢ embedding (không lọc theo schema).")

        # Chuẩn hóa mode cho so khớp không phân biệt hoa/thường
        self._mode_norm = self.mode.lower() if isinstance(self.mode, str) else None

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
                logging.info(f"Khóa: {key}, Kiểu giá trị: {type(value)}, Giá trị mẫu: {str(value)[:100]}...")
                if i >= 5:
                    break
        elif isinstance(data, list):
            logging.info(f"Số lượng phần tử: {len(data)}")
        else:
            logging.info(f"Dữ liệu: {str(data)[:100]}...")
        return data

    def _base_key_for_schema(self, key: str) -> str:
        """
        Chuẩn hóa tên field lá để so khớp với schema:
        - bỏ chỉ số [i]
        - bỏ hậu tố ' Embedding'
        - lấy token cuối sau dấu '.'
        """
        return re.sub(r"\[\d+\]", "", key).replace(" Embedding", "").split(".")[-1]

    def _should_include(self, key: str) -> bool:
        """
        Trả về True nếu field lá thuộc nhóm giữ lại (keep_fields) theo schema.
        Nếu không có schema → giữ tất cả.
        """
        if not self.keep_fields:
            return True
        base = self._base_key_for_schema(key)
        return base in self.keep_fields

    def _skip_by_mode(self, full_key: str, key_only: str) -> bool:
        """
        Bỏ qua một nhánh theo `mode` (không phân biệt hoa/thường).
        Ví dụ: mode='embeddings' → bỏ mọi key bắt đầu bằng 'embeddings' ở top-level.
        """
        if not self._mode_norm:
            return False
        return (
            key_only.lower() == self._mode_norm or
            full_key.lower().startswith(self._mode_norm)
        )

    # ====== Extract ======
    def _extract_embeddings_and_data(
        self, data: Any, prefix: str = ""
    ) -> Tuple[List[Tuple[str, np.ndarray]], Dict[str, Any]]:
        """
        Trích xuất đệ quy:
        - embeddings_list: [(full_key, np.ndarray), ...] CHỈ gồm các vector được phép index (lọc theo schema/mode).
        - data_mapping: dict các dữ liệu thường (text, số, list...), KHÔNG chứa vector embedding.
        """
        embeddings_list: List[Tuple[str, np.ndarray]] = []
        data_mapping: Dict[str, Any] = {}

        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else key

                # Lọc theo mode (bỏ nhánh không muốn convert)
                if self._skip_by_mode(full_key, key):
                    continue

                if isinstance(value, dict):
                    sub_embeds, sub_data = self._extract_embeddings_and_data(value, full_key)
                    embeddings_list.extend(sub_embeds)
                    data_mapping.update(sub_data)

                elif isinstance(value, list) and value and isinstance(value[0], dict):
                    # list các dict: đi sâu từng phần tử
                    for i, item in enumerate(value):
                        sub_embeds, sub_data = self._extract_embeddings_and_data(item, f"{full_key}.{i}")
                        embeddings_list.extend(sub_embeds)
                        data_mapping.update(sub_data)

                elif isinstance(value, (torch.Tensor, np.ndarray)):
                    # Vector (embedding) dạng tensor/ndarray
                    arr = ex(lambda: value.cpu().numpy() if isinstance(value, torch.Tensor) else value)
                    if isinstance(arr, np.ndarray):
                        if arr.ndim > 1:
                            arr = arr.reshape(-1)  # flatten an toàn
                        # Chỉ đưa vào FAISS nếu qua lọc schema
                        if self._should_include(full_key):
                            embeddings_list.append((full_key, arr.astype("float32")))
                        # KHÔNG ghi vector vào data_mapping
                    else:
                        # Không phải ndarray → ghi như dữ liệu thường
                        data_mapping[full_key] = value

                elif isinstance(value, (list, tuple)) and "embedding" in full_key.lower():
                    # Vector (embedding) được lưu dạng list ở JSON (khi encode từ C2)
                    arr = ex(lambda: np.array(value, dtype=np.float32))
                    if isinstance(arr, np.ndarray):
                        if arr.ndim > 1:
                            arr = arr.reshape(-1)
                        if self._should_include(full_key):
                            embeddings_list.append((full_key, arr))
                    # KHÔNG ghi vector vào data_mapping

                else:
                    # Dữ liệu thường: ghi lại vào map_data
                    data_mapping[full_key] = value

        elif isinstance(data, list):
            for i, item in enumerate(data):
                full_key = f"{prefix}.{i}" if prefix else str(i)
                # Ở cấp list gốc (top-level), nếu muốn bỏ cả nhánh theo mode thì đã xử lý ở dict cha.
                if isinstance(item, (dict, list)):
                    sub_embeds, sub_data = self._extract_embeddings_and_data(item, full_key)
                    embeddings_list.extend(sub_embeds)
                    data_mapping.update(sub_data)
                elif isinstance(item, (torch.Tensor, np.ndarray)):
                    arr = ex(lambda: item.cpu().numpy() if isinstance(item, torch.Tensor) else item)
                    if isinstance(arr, np.ndarray):
                        if arr.ndim > 1:
                            arr = arr.reshape(-1)
                        if self._should_include(full_key):
                            embeddings_list.append((full_key, arr.astype("float32")))
                    # KHÔNG ghi vector vào map_data
                elif isinstance(item, (list, tuple)) and "embedding" in (prefix.lower() if isinstance(prefix, str) else ""):
                    arr = ex(lambda: np.array(item, dtype=np.float32))
                    if isinstance(arr, np.ndarray):
                        if arr.ndim > 1:
                            arr = arr.reshape(-1)
                        if self._should_include(full_key):
                            embeddings_list.append((full_key, arr))
                    # KHÔNG ghi vector vào map_data
                else:
                    data_mapping[full_key] = item

        return embeddings_list, data_mapping

    # ====== FAISS ======
    def _create_faiss_index(self, embeddings: List[Tuple[str, np.ndarray]]) -> Tuple[faiss.Index, Dict[str, int]]:
        if not embeddings:
            raise ValueError("Không tìm thấy embedding trong dữ liệu đầu vào.")

        dim = int(embeddings[0][1].shape[-1])
        if not all(emb.shape[-1] == dim for _, emb in embeddings):
            raise ValueError("Tất cả embedding phải có cùng chiều.")

        matrix = np.stack([emb for _, emb in embeddings]).astype("float32")
        logging.info("Đang thêm embedding vào chỉ mục...")

        index = faiss.IndexFlatIP(dim)
        index.add(matrix)

        key_to_index = {key: idx for idx, (key, _) in enumerate(embeddings)}
        return index, key_to_index

    # ====== Public ======
    def convert(self) -> None:
        """Full pipeline: đọc .pt → extract (lọc) → FAISS → ghi file"""
        if not os.path.exists(self.torch_path):
            raise FileNotFoundError(f"File .pt không tồn tại: {self.torch_path}")

        os.makedirs(os.path.dirname(self.faiss_path), exist_ok=True)

        # 1) Inspect
        self._inspect_torch_path()

        # 2) Load
        logging.info(f"Đang tải file .pt: {self.torch_path}")
        data = ex(lambda: torch.load(self.torch_path, map_location=torch.device("cpu"), weights_only=False))
        if data is None:
            raise RuntimeError(f"Không thể tải dữ liệu từ file .pt: {self.torch_path}")

        # 3) Extract & filter
        logging.info("Đang trích xuất embedding và dữ liệu...")
        embeddings_list, data_mapping = self._extract_embeddings_and_data(data)
        if not embeddings_list:
            raise ValueError("Không tìm thấy embedding nào trong file .pt.")
        logging.info(f"Tìm thấy {len(embeddings_list)} embedding.")

        # 4) Build FAISS
        logging.info("Đang tạo chỉ mục FAISS...")
        faiss_index, key_to_index = self._create_faiss_index(embeddings_list)

        # 5) Save FAISS
        ex(lambda: faiss.write_index(faiss_index, self.faiss_path))

        # 6) Save mapping
        logging.info(f"Đang lưu ánh xạ khóa vào {self.mapping_path}")
        if self.use_pickle:
            ex(lambda: pickle.dump(key_to_index, open(self.mapping_path, "wb")))
        else:
            ex(lambda: json.dump(key_to_index, open(self.mapping_path, "w", encoding="utf-8"),
                                 indent=4, ensure_ascii=False))

        # 7) Save map_data (CHỈ dữ liệu thường, KHÔNG vector embedding)
        logging.info(f"Đang lưu dữ liệu thường vào {self.map_data_path}")
        if self.use_pickle:
            ex(lambda: pickle.dump(data_mapping, open(self.map_data_path, "wb")))
        else:
            ex(lambda: json.dump(data_mapping, open(self.map_data_path, "w", encoding="utf-8"),
                                 indent=4, ensure_ascii=False))

        logging.info("Chuyển đổi hoàn tất.")
