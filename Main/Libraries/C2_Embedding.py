import os
import re
import json
import torch
from copy import deepcopy
from typing import Any, Dict, List, Tuple, Optional
from . import A0_MyUtils as A0

class JSONEmbedding:
    """
    Pipeline sinh embedding cho dữ liệu JSON (NO-MERGE, tách phần tử list).
    - Mọi lời gọi model.encode đều dùng list[str].
    - Dùng deepcopy để tránh tác dụng phụ trên JSON lồng nhau.
    - flatten_json hỗ trợ 3 chế độ xử lý list: split | join | keep (mặc định: split).
    """

    def __init__(
        self,
        model: Any,
        device: str = "cpu",
        batch_size: int = 32,
        show_progress: bool = False,
        flatten_mode: str = "split",        # "split" | "join" | "keep"
        join_sep: str = "\n",
        allowed_schema_types: Tuple[str, ...] = ("string", "array", "dict"),
        max_chars_per_text: Optional[int] = None,
        verbose: bool = False,
    ) -> None:
        self.model = model
        self.device = device
        self.batch_size = batch_size
        self.show_progress = show_progress
        self.flatten_mode = flatten_mode
        self.join_sep = join_sep
        self.allowed_schema_types = allowed_schema_types
        self.max_chars_per_text = max_chars_per_text
        self.verbose = verbose

        # biên dịch regex 1 lần
        self._non_keep_pattern = re.compile(r"[^\w\s\(\)\.\,\;\:\-–]", flags=re.UNICODE)

    # ========== 1) Tiền xử lý ==========

    # ========== 2) Schema ==========

    @staticmethod
    def load_schema(schema_path: str) -> Dict[str, str]:
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ========== 3) Flatten JSON ==========

    # ========== 4) Tương thích schema & chọn trường cần embed ==========

    @staticmethod
    def _base_key_for_schema(key: str) -> str:
        """
        Bỏ chỉ số [i] để đối khớp với khóa trong schema.
        Ví dụ: "Contents[2]" -> "Contents"; "a.b[3].c" -> "a.b.c"
        """
        return re.sub(r"\[\d+\]", "", key)

    def _eligible_by_schema(self, key: str, schema: Optional[Dict[str, str]]) -> bool:
        """
        Trả về True nếu:
        - Không có schema (embed mọi key lá dạng text hợp lệ), hoặc
        - Có schema và kiểu của base_key nằm trong allowed_schema_types.
        """
        if schema is None:
            return True
        base_key = self._base_key_for_schema(key)
        typ = schema.get(base_key)
        return (typ in self.allowed_schema_types) if typ is not None else False

    # ========== 5) Tạo embedding (luôn dùng list[str]) ==========

    def _encode_texts(self, texts: List[str]) -> torch.Tensor:
        """
        Mọi lời gọi model.encode đều dùng list[str].
        Tự fallback CPU khi thiếu VRAM.
        """
        # logging nhẹ
        if self.verbose:
            sample = texts[:2] if len(texts) > 1 else texts
            print(f"[encode] n_texts={len(texts)}, sample={sample!r}, device={self.device}, bs={self.batch_size}")

        try:
            embs = self.model.encode(
                sentences=texts,
                batch_size=self.batch_size,
                convert_to_tensor=True,
                device=self.device,
                show_progress_bar=self.show_progress,
            )
            return embs
        except RuntimeError as e:
            if "CUDA out of memory" in str(e):
                print("⚠️ CUDA OOM. Fallback về CPU.")
                try:
                    self.model.to("cpu")  # nếu model có .to
                except Exception:
                    pass
                embs = self.model.encode(
                    sentences=texts,
                    batch_size=self.batch_size,
                    convert_to_tensor=True,
                    device="cpu",
                    show_progress_bar=self.show_progress,
                )
                return embs
            raise

    # ========== 6) Embed dữ liệu ==========

    def embed_data(
        self,
        data: Any,
        schema: Optional[Dict[str, str]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, List[float]]]:
        """
        - Tiền xử lý JSON (deepcopy + preprocess).
        - Làm phẳng (flatten) theo cấu hình list_mode.
        - Chọn các key hợp lệ theo schema.
        - Gom toàn bộ text → 1 lần encode theo batch.
        - Trả về:
            result: bản sao dữ liệu gốc + các khóa "… Embedding" (đặt đúng nhánh theo tiền tố '.').
            embed_dict: { "<flat_key> Embedding": [float, ...], ... }
        """
        # deepcopy để an toàn với JSON lồng
        original = deepcopy(data)
        processed = A0.preprocess_data(
            original,
            non_keep_pattern=self._non_keep_pattern,
            max_chars_per_text=self.max_chars_per_text
        )


        flat = A0.flatten_json(
            processed,
            prefix="",
            flatten_mode=self.flatten_mode,
            join_sep=self.join_sep
        )

        # Lọc các mục text hợp lệ để embed
        embed_items: List[Tuple[str, str]] = []  # [(flat_key, text), ...]
        for k, v in flat.items():
            if not self._eligible_by_schema(k, schema):
                continue
            # chỉ embed khi là chuỗi non-empty
            if isinstance(v, str) and v.strip():
                embed_items.append((k, v.strip()))
            # nếu giữ nguyên list ("keep"), ta không embed cả list; cần "split"/"join" để có str

        if not embed_items:
            return processed, {}

        # Gọi encode 1 lần cho tất cả
        texts = [t for _, t in embed_items]  # luôn là list[str]
        embs = self._encode_texts(texts)     # Tensor [N, D]

        # Gắn embedding trở lại cấu trúc dữ liệu (inline)
        result = deepcopy(processed)
        embed_dict: Dict[str, List[float]] = {}

        for (flat_key, _), vec in zip(embed_items, embs):
            embed_key_full = f"{flat_key} Embedding"
            embed_list = vec.detach().cpu().tolist()
            embed_dict[embed_key_full] = embed_list

            # chèn theo nhánh (tách theo '.')
            path_parts = flat_key.split(".")
            curr = result
            # đi tới node cha cuối
            for part in path_parts[:-1]:
                curr = curr.setdefault(part, {}) if isinstance(curr, dict) else curr
            # thêm cặp key: "<leaf> Embedding"
            leaf = path_parts[-1] + " Embedding"
            if isinstance(curr, dict):
                curr[leaf] = embed_list
            else:
                # nếu curr không phải dict (trường hợp hiếm), gắn ở cấp gốc
                result[embed_key_full] = embed_list

        return result, embed_dict

    # ========== 7) Xử lý file JSON & lưu .pt ==========

    def embeddingRun(
        self,
        json_path: str,
        schema_path: Optional[str],
        torch_path: str,
        data_key: str = "DATA",
        embe_key: str = "EMBEDDINGS",
        skip_if_exists: bool = True,
    ) -> None:
        """
        Đọc JSON đầu vào, sinh embedding theo schema (nếu có), và lưu ra .pt:
            {
              data_key:  [result_item1, result_item2, ...],
              embe_key:  [embed_dict_item1, embed_dict_item2, ...]
            }
        """
        if skip_if_exists and os.path.exists(torch_path):
            print(f"Embedding đã tồn tại ở {torch_path}. Bỏ qua.")
            return

        schema: Optional[Dict[str, str]] = None
        if schema_path:
            schema = self.load_schema(schema_path)
            if not schema:
                raise ValueError("Schema rỗng hoặc không hợp lệ.")

        with open(json_path, "r", encoding="utf-8") as f:
            data_obj = json.load(f)

        # Chuẩn hoá: đảm bảo xử lý được cả list và đơn lẻ
        data_list = data_obj if isinstance(data_obj, list) else [data_obj]

        out_results: List[Dict[str, Any]] = []
        out_embeds: List[Dict[str, List[float]]] = []

        for item in data_list:
            result, embed_dict = self.embed_data(item, schema=schema)
            out_results.append(result)
            out_embeds.append(embed_dict)

        torch.save({data_key: out_results, embe_key: out_embeds}, torch_path)
        print(f"Đã lưu embedding vào: {torch_path}")