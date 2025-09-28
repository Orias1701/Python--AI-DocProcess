import os
import json
import torch
from typing import Any, Dict, Optional

def print_json(
    DATA_KEY: str,
    EMBE_KEY: str,
    pt_path: str,
    index: int = 0,
    max_str_len: int = 200,
    max_list_items: int = 10,
    max_depth: int = 6,
) -> None:
    """
    In ra bộ dữ liệu thứ `index` từ DATA_KEY và EMBE_KEY trong file .pt, theo dạng tóm tắt.

    Args:
        DATA_KEY: Khóa chứa dữ liệu văn bản (vd: 'DATA' hay 'contents').
        EMBE_KEY: Khóa chứa dữ liệu embedding (vd: 'EMBEDDINGS' hay 'embeddings').
        pt_path : Đường dẫn tới file .pt.
        index   : Chỉ mục bộ dữ liệu muốn xem (mặc định 0).
        max_str_len   : Cắt ngắn chuỗi dài hơn ngưỡng này (mặc định 200).
        max_list_items: Giới hạn số phần tử được in cho list/dict (mặc định 10).
        max_depth     : Độ sâu đệ quy tối đa khi in (mặc định 6).
    """
    try:
        if not os.path.exists(pt_path):
            print(f"File không tồn tại: {pt_path}")
            return

        # Torch >= 2.5 có weights_only; nếu phiên bản cũ sẽ bỏ qua tham số này
        try:
            data = torch.load(pt_path, map_location="cpu", weights_only=False)
        except TypeError:
            data = torch.load(pt_path, map_location="cpu")

        def summarize(obj: Any, depth: int = 0) -> Any:
            """Tóm tắt đối tượng theo cây, tránh in dài."""
            if depth >= max_depth:
                return "...(truncated depth)..."

            # Tensor: in shape/dtype + 5 giá trị đầu
            if isinstance(obj, torch.Tensor):
                flat = obj.flatten()
                sample = flat[:5].tolist() if flat.numel() > 0 else []
                return {
                    "__tensor__": True,
                    "shape": list(obj.shape),
                    "dtype": str(obj.dtype),
                    "sample_values": sample,
                }

            # Lá đơn giản
            if obj is None or isinstance(obj, (int, float, bool)):
                return obj

            if isinstance(obj, str):
                s = obj if len(obj) <= max_str_len else (obj[:max_str_len] + "…")
                return s

            # List vector số: chỉ in độ dài + 5 giá trị đầu
            if isinstance(obj, list):
                if all(isinstance(x, (int, float)) for x in obj):
                    head = obj[:5]
                    return {"__vector_len__": len(obj), "head": head}
                # List thường
                out = [summarize(x, depth + 1) for x in obj[:max_list_items]]
                if len(obj) > max_list_items:
                    out.append(f"… (+{len(obj) - max_list_items} more)")
                return out

            # Dict: giới hạn số key
            if isinstance(obj, dict):
                keys = list(obj.keys())
                shown_keys = keys[:max_list_items]
                out: Dict[str, Any] = {}
                for k in shown_keys:
                    out[k] = summarize(obj[k], depth + 1)
                if len(keys) > max_list_items:
                    out["__truncated__"] = f"+{len(keys) - max_list_items} more keys"
                return out

            # Fallback
            return str(obj)

        # ===== In DATA_KEY =====
        if not (isinstance(data, dict) and DATA_KEY in data):
            print(f"Dữ liệu không đúng định dạng: không tìm thấy key '{DATA_KEY}'")
        else:
            content = data[DATA_KEY]
            if not isinstance(content, list) or not content:
                print(f"Dữ liệu rỗng hoặc không phải danh sách cho '{DATA_KEY}'")
            else:
                i = max(0, min(index, len(content) - 1))
                first_json = content[i]
                processed_json = summarize(first_json)
                print(f"[{DATA_KEY}] Tổng số mục: {len(content)} — In mục index={i}")
                print(json.dumps(processed_json, ensure_ascii=False, indent=2))

        # ===== In EMBE_KEY =====
        if not (isinstance(data, dict) and EMBE_KEY in data):
            print(f"Dữ liệu không đúng định dạng: không tìm thấy key '{EMBE_KEY}'")
        else:
            embeddings = data[EMBE_KEY]
            if not isinstance(embeddings, list) or not embeddings:
                print(f"Dữ liệu rỗng hoặc không phải danh sách cho '{EMBE_KEY}'")
            else:
                j = max(0, min(index, len(embeddings) - 1))
                first_embedding = embeddings[j]

                # Nếu là tensor: tóm tắt
                if isinstance(first_embedding, torch.Tensor):
                    info = summarize(first_embedding)
                    print(f"\n[{EMBE_KEY}] Tổng số mục: {len(embeddings)} — In mục index={j}")
                    print(json.dumps(info, ensure_ascii=False, indent=2))

                # Nếu là dict {flat_key: [float,...]}: thống kê nhanh + tóm tắt
                elif isinstance(first_embedding, dict):
                    # Thống kê số vector và phân bố chiều
                    dim_hist: Dict[Optional[int], int] = {}
                    num_vectors = 0
                    for k, v in first_embedding.items():
                        dim = None
                        if isinstance(v, list) and all(isinstance(x, (int, float)) for x in v):
                            dim = len(v)
                            num_vectors += 1
                        dim_hist[dim] = dim_hist.get(dim, 0) + 1

                    stats = {
                        "num_vectors": num_vectors,
                        "dim_histogram": {str(k): v for k, v in dim_hist.items()},
                    }
                    print(f"\n[{EMBE_KEY}] Tổng số mục: {len(embeddings)} — In mục index={j}")
                    print("Thống kê nhanh embedding:")
                    print(json.dumps(stats, ensure_ascii=False, indent=2))

                    processed_embedding = summarize(first_embedding)
                    print("\nMẫu embedding (đã tóm tắt):")
                    print(json.dumps(processed_embedding, ensure_ascii=False, indent=2))

                # Trường hợp khác (list lồng, v.v.)
                else:
                    processed_embedding = summarize(first_embedding)
                    print(f"\n[{EMBE_KEY}] Tổng số mục: {len(embeddings)} — In mục index={j}")
                    print(json.dumps(processed_embedding, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"Lỗi khi đọc file .pt: {str(e)}")
