import logging
import re, os
import torch
import faiss
import numpy as np

from typing import Dict, List, Any, Tuple, Optional

from . import Common_MyUtils as MyUtils

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class DirectFaissIndexer:
    """
        1) FaissPath (.faiss): chỉ chứa vectors,
        2) MapDataPath (.json): content + index,
        3) MappingPath (.json): ánh xạ key <-> index.
    """

    def __init__(
        self,
        indexer: Any,
        device: str = "cpu",
        batch_size: int = 32,
        show_progress: bool = False,
        flatten_mode: str = "split",
        join_sep: str = "\n",
        allowed_schema_types: Tuple[str, ...] = ("string", "array", "dict"),
        max_chars_per_text: Optional[int] = None,
        normalize: bool = True,
        verbose: bool = False,
        list_policy: str = "split", # "merge" | "split"
    ):
        self.indexer = indexer
        self.device = device
        self.batch_size = batch_size
        self.show_progress = show_progress
        self.flatten_mode = flatten_mode
        self.join_sep = join_sep
        self.allowed_schema_types = allowed_schema_types
        self.max_chars_per_text = max_chars_per_text
        self.normalize = normalize
        self.verbose = verbose
        self.list_policy = list_policy

        self._non_keep_pattern = re.compile(r"[^\w\s\(\)\.\,\;\:\-–]", flags=re.UNICODE)

    # ---------- Schema & chọn trường ----------

    @staticmethod
    def _base_key_for_schema(key: str) -> str:

        return re.sub(r"\[\d+\]", "", key)

    def _eligible_by_schema(self, key: str, schema: Optional[Dict[str, str]]) -> bool:
        if schema is None:
            return True
        base_key = self._base_key_for_schema(key)
        typ = schema.get(base_key)
        return (typ in self.allowed_schema_types) if typ is not None else False

    # ---------- Tiền xử lý & flatten ----------
    def _preprocess_data(self, data: Any) -> Any:

        if MyUtils and hasattr(MyUtils, "preprocess_data"):
            return MyUtils.preprocess_data(
                data,
                non_keep_pattern=self._non_keep_pattern,
                max_chars_per_text=self.max_chars_per_text
            )

    def _flatten_json(self, data: Any) -> Dict[str, Any]:
        """
        Flatten JSON theo list_policy:
        - merge: gộp list/dict chứa chuỗi thành 1 đoạn text duy nhất
        - split: tách từng phần tử
        """
        # Nếu merge, xử lý JSON trước khi flatten
        if self.list_policy == "merge":
            def _merge_lists(obj):
                if isinstance(obj, dict):
                    return {k: _merge_lists(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    # Nếu list chỉ chứa chuỗi / số, gộp lại
                    if all(isinstance(i, (str, int, float)) for i in obj):
                        return self.join_sep.join(map(str, obj))
                    # Nếu list chứa dict hoặc list lồng, đệ quy
                    return [_merge_lists(v) for v in obj]
                else:
                    return obj

            data = _merge_lists(data)

        # Sau đó gọi MyUtils.flatten_json như cũ
        return MyUtils.flatten_json(
            data,
            prefix="",
            flatten_mode=self.flatten_mode,
            join_sep=self.join_sep
        )

    # ---------- Encode (batch) với fallback OOM CPU ----------
    def _encode_texts(self, texts: List[str]) -> torch.Tensor:
        try:
            embs = self.indexer.encode(
                sentences=texts,
                batch_size=self.batch_size,
                convert_to_tensor=True,
                device=self.device,
                show_progress_bar=self.show_progress,
            )
            return embs
        except RuntimeError as e:
            if "CUDA out of memory" in str(e):
                print("⚠️ CUDA OOM → fallback CPU.")
                try:
                    self.indexer.to("cpu")
                except Exception:
                    pass
                embs = self.indexer.encode(
                    sentences=texts,
                    batch_size=self.batch_size,
                    convert_to_tensor=True,
                    device="cpu",
                    show_progress_bar=self.show_progress,
                )
                return embs
            raise

    # ---------- Build FAISS ----------
    @staticmethod
    def _l2_normalize(mat: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return mat / norms

    def _create_faiss_index(self, matrix: np.ndarray) -> faiss.Index:
        dim = int(matrix.shape[1])
        index = faiss.IndexFlatIP(dim)
        index.add(matrix.astype("float32"))
        return index


    # ================================================================
    #  Hàm lọc trùng nhưng vẫn gom nhóm chunk tương ứng
    # ================================================================
    def deduplicates_with_mask(
        self,
        pairs: List[Tuple[str, str]],
        chunk_map: List[int]
    ) -> Tuple[List[Tuple[str, str]], List[List[int]]]:

        assert len(pairs) == len(chunk_map), "pairs và chunk_map phải đồng dài"

        seen_per_key: Dict[str, Dict[str, int]] = {}
        # base_key -> text_norm -> index trong filtered_pairs

        filtered_pairs: List[Tuple[str, str]] = []
        chunk_groups: List[List[int]] = []

        for (key, text), c in zip(pairs, chunk_map):
            text_norm = text.strip()
            if not text_norm:
                continue

            base_key = re.sub(r"\[\d+\]", "", key)
            if base_key not in seen_per_key:
                seen_per_key[base_key] = {}

            # Nếu text đã xuất hiện → thêm chunk vào nhóm cũ
            if text_norm in seen_per_key[base_key]:
                idx = seen_per_key[base_key][text_norm]
                if c not in chunk_groups[idx]:
                    chunk_groups[idx].append(c)
                continue

            # Nếu chưa có → tạo mới
            seen_per_key[base_key][text_norm] = len(filtered_pairs)
            filtered_pairs.append((key, text_norm))
            chunk_groups.append([c])

        return filtered_pairs, chunk_groups

    # ================================================================
    #  Hàm build_from_json
    # ================================================================
    def build_from_json(
        self,
        SegmentPath: str,
        SchemaDict: Optional[str],
        FaissPath: str,
        MapDataPath: str,
        MappingPath: str,
        MapChunkPath: Optional[str] = None,
    ) -> None:
        assert os.path.exists(SegmentPath), f"Không thấy file JSON: {SegmentPath}"

        os.makedirs(os.path.dirname(FaissPath), exist_ok=True)
        os.makedirs(os.path.dirname(MapDataPath), exist_ok=True)
        os.makedirs(os.path.dirname(MappingPath), exist_ok=True)
        if MapChunkPath:
            os.makedirs(os.path.dirname(MapChunkPath), exist_ok=True)

        schema = SchemaDict

        # 1️⃣ Read JSON
        data_obj = MyUtils.read_json(SegmentPath)
        data_list = data_obj if isinstance(data_obj, list) else [data_obj]

        # 2️⃣ Flatten + lưu chunk_id
        pair_list: List[Tuple[str, str]] = []
        chunk_map: List[int] = []
        for chunk_id, item in enumerate(data_list, start=1):
            processed = self._preprocess_data(item)
            flat = self._flatten_json(processed)
            for k, v in flat.items():
                if not self._eligible_by_schema(k, schema):
                    continue
                if isinstance(v, str) and v.strip():
                    pair_list.append((k, v.strip()))
                    chunk_map.append(chunk_id)

        if not pair_list:
            raise ValueError("Không tìm thấy nội dung văn bản hợp lệ để encode.")

        # 3️⃣ Loại trùng nhưng gom nhóm chunk
        pair_list, chunk_groups = self.deduplicates_with_mask(pair_list, chunk_map)

        # 4️⃣ Encode
        keys  = [k for k, _ in pair_list]
        texts = [t for _, t in pair_list]
        embs_t = self._encode_texts(texts)
        embs = embs_t.detach().cpu().numpy()
        if self.normalize:
            embs = self._l2_normalize(embs)

        # 5️⃣ FAISS
        FaissIndex = self._create_faiss_index(embs)
        # faiss.write_index(FaissIndex, FaissPath)
        # logging.info(f"✅ Đã xây FAISS: {FaissPath}")
        
        # 6️⃣ Mapping + MapData

        index_to_key = {str(i): k for i, k in enumerate(keys)}
        Mapping = {
            "meta": {
                "count": len(keys),
                "dim": int(embs.shape[1]),
                "metric": "ip",
                "normalized": bool(self.normalize),
            },

            "index_to_key": index_to_key,
        }
        MapData = {
            "items": [{"index": i, "key": k, "text": t} for i, (k, t) in enumerate(pair_list)],
            "meta": {
                "count": len(keys),
                "flatten_mode": self.flatten_mode,
                "schema_used": schema is not None,
                "list_policy": self.list_policy
            }
        }

        return FaissIndex, Mapping, MapData, chunk_groups