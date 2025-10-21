from typing import Dict, List, Any, Optional, Iterable

# --------- A. Tiện ích cơ bản ---------

def _ordered_unique_chunk_ids(reranked: List[Dict[str, Any]]) -> List[int]:
    seen, ordered = set(), []
    for r in reranked:
        for cid in r.get("chunk_ids", []):
            if isinstance(cid, (int, str)) and str(cid).isdigit():
                cid = int(cid)
                if cid not in seen:
                    seen.add(cid)
                    ordered.append(cid)
    return ordered


def _filter_fields_recursive(obj: Any, drop_lower: set) -> Any:
    """Loại bỏ các field có tên xuất hiện trong drop_lower (case-insensitive) trên toàn cấu trúc."""
    if isinstance(obj, dict):
        return {
            k: _filter_fields_recursive(v, drop_lower)
            for k, v in obj.items()
            if k.lower() not in drop_lower
        }
    if isinstance(obj, list):
        return [_filter_fields_recursive(x, drop_lower) for x in obj]
    return obj


def _iter_values_no_keys(obj: Any) -> Iterable[str]:
    """Duyệt đệ quy, chỉ yield GIÁ TRỊ (bỏ key), split theo '\n' nếu là chuỗi."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_values_no_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_values_no_keys(item)
    elif isinstance(obj, str):
        for line in obj.splitlines():
            yield line
    else:
        yield str(obj)


def _get_by_path(obj: Any, path: str) -> Any:
    """
    Lấy giá trị theo path kiểu 'A.B.C'.
    - Nếu gặp list trong quá trình đi xuống → thu thập giá trị từ từng phần tử (map-collect).
    - Nếu path không tồn tại → trả về None.
    """
    parts = path.split(".")
    def _step(o, idx=0):
        if idx == len(parts):
            return o
        key = parts[idx]
        if isinstance(o, dict):
            if key not in o:
                return None
            return _step(o[key], idx + 1)
        if isinstance(o, list):
            collected = []
            for it in o:
                collected.append(_step(it, idx))
            # gộp phẳng các None
            flat = []
            for v in collected:
                if v is None:
                    continue
                if isinstance(v, list):
                    flat.extend(v)
                else:
                    flat.append(v)
            return flat
        return None
    return _step(obj, 0)


# --------- B. Các hàm chính ---------

def extract_chunks_from_rerank_flexible(
    reranked_results: List[Dict[str, Any]],
    SegmentDict: List[Dict[str, Any]],
    n_chunks: Optional[int] = None,
    drop_fields: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    - Lấy chunk theo thứ tự từ reranked.
    - Giới hạn số lượng chunk gốc trả về bằng n_chunks (nếu có).
    - Áp dụng bỏ trường theo drop_fields (toàn bộ cấu trúc).
    - Kết quả: [{"chunk_id": int, "data": <json đã lọc>}]
    """
    if not reranked_results:
        return []

    ordered_ids = _ordered_unique_chunk_ids(reranked_results)
    if n_chunks is not None:
        ordered_ids = ordered_ids[:int(n_chunks)]

    drop_lower = set(x.lower() for x in (drop_fields or []))

    out = []
    seen = set()
    for cid in ordered_ids:
        if cid in seen:
            continue
        seen.add(cid)
        if 1 <= cid <= len(SegmentDict):
            data = SegmentDict[cid - 1]
            filtered = _filter_fields_recursive(data, drop_lower) if drop_lower else data
            out.append({"chunk_id": cid, "data": filtered})
    return out


def collect_chunk_text(chunks: List[Dict[str, Any]]) -> str:
    """Biến toàn bộ danh sách chunk thành text (bỏ key, split dòng)."""
    if not chunks:
        return "(Không có chunk nào)"

    lines: List[str] = []
    for ch in chunks:
        for line in _iter_values_no_keys(ch["data"]):
            lines.append(line)
        lines.append("")
    return "\n".join(lines).strip()


def extract_fields_for_each_chunk(
    chunks: List[Dict[str, Any]],
    fields: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    - Với mỗi chunk gốc, lấy những TRƯỜNG được truyền vào (hỗ trợ path 'A.B.C').
    - Nếu fields=None → lấy TẤT CẢ top-level fields còn lại trong chunk['data'].
    - Trả về list theo từng chunk: {"chunk_id": ..., "fields": {...}}
    """
    results = []
    for ch in chunks:
        data = ch["data"]
        if not isinstance(data, dict):
            results.append({"chunk_id": ch["chunk_id"], "fields": data})
            continue

        if fields is None:
            payload = {k: v for k, v in data.items()}
        else:
            payload = {}
            for f in fields:
                payload[f] = _get_by_path(data, f)
        results.append({"chunk_id": ch["chunk_id"], "fields": payload})
    return results


def process_chunks_pipeline(
    reranked_results: List[Dict[str, Any]],
    SegmentDict: List[Dict[str, Any]],
    drop_fields: Optional[List[str]] = None,     # Trường bị bỏ qua (áp dụng toàn bộ)
    fields: Optional[List[str]] = None,          # Trường muốn trích xuất (None → tất cả top-level)
    n_chunks: Optional[int] = None               # Số lượng chunk gốc & text (nếu None → tất cả)
) -> Dict[str, Any]:
    """
    Trả về:
      - chunks_json: đúng số lượng chunk gốc (đã drop_fields)
      - chunks_text: text từ cùng số lượng chunk (bỏ key, split dòng)
      - extracted_fields: các trường được chỉ định cho mỗi chunk
    """
    # 1️⃣ Lấy chunk gốc (JSON)
    chunks_json = extract_chunks_from_rerank_flexible(
        reranked_results=reranked_results,
        SegmentDict=SegmentDict,
        n_chunks=n_chunks,
        drop_fields=drop_fields,
    )

    # 2️⃣ Biến thành text (cùng số lượng chunk)
    chunks_text = collect_chunk_text(chunks_json)

    # 3️⃣ Lấy các trường cụ thể
    extracted_fields = extract_fields_for_each_chunk(chunks_json, fields=fields)

    return {
        "chunks_json": chunks_json,          # JSON chuẩn
        "chunks_text": chunks_text,          # text của cùng số lượng chunk
        "extracted_fields": extracted_fields # field được chọn
    }
