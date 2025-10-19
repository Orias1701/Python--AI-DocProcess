import logging
import re, os
import openpyxl
import json, csv
import pandas as pd
from collections import Counter
from typing import Dict, List, Any, Tuple, Optional


# ===============================
# 0. ERROR CATCHER
# ===============================
def exc(func, fallback=None):
    """
    Thực thi func() an toàn.
    Nếu lỗi → log exception (e) và trả về fallback.
    """
    try:
        return func()
    except Exception as e:
        logging.warning(e)
        return fallback
    
# ===============================
# 1. JSON
# ===============================
def read_json(path: str) -> Any:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(data: Any, path: str, indent: int = 2) -> None:
    dir_path = os.path.dirname(path)
    if dir_path: os.makedirs(dir_path, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)

def insert_json(data: Any, path: str, indent: int = 2):
    dir_path = os.path.dirname(path)
    if dir_path: os.makedirs(dir_path, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


# ===============================
# 2. JSONL
# ===============================
def read_jsonl(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

def write_jsonl(data: List[dict], path: str) -> None:
    dir_path = os.path.dirname(path)
    if dir_path: os.makedirs(dir_path, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

def insert_jsonl(data: List[dict], path: str):
    dir_path = os.path.dirname(path)
    if dir_path: os.makedirs(dir_path, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')


# ===============================
# 3. CSV
# ===============================
def read_csv(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(data: List[dict], path: str) -> None:
    dir_path = os.path.dirname(path)
    if dir_path: os.makedirs(dir_path, exist_ok=True)
    if not data:
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)


# ===============================
# 4.XLSX
# ===============================
def read_xlsx(path: str, sheet_name: str = None) -> List[dict]:
    wb = openpyxl.load_workbook(path)
    sheet = wb[sheet_name] if sheet_name else wb.active
    rows = list(sheet.values)
    headers = rows[0]
    return [dict(zip(headers, row)) for row in rows[1:]]

def write_xlsx(data: List[dict], path: str, sheet_name: str = "Sheet1") -> None:
    dir_path = os.path.dirname(path)
    if dir_path: os.makedirs(dir_path, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    if not data:
        wb.save(path)
        return
    ws.append(list(data[0].keys()))
    for row in data:
        ws.append(list(row.values()))
    wb.save(path)

def convert_to_xlsx(json_path, xlsx_path):
    os.makedirs(os.path.dirname(xlsx_path), exist_ok=True)
    """Chuyển file JSON (dạng list các object) hoặc JSONL sang XLSX."""
    try:
        if json_path.endswith('.jsonl'):
            df = pd.read_json(json_path, lines=True)
        else:
            df = pd.read_json(json_path)
            
        column_order = ["category", "sub_category", "url", "title", "description", "content", "date", "words"]
        df = df[[col for col in column_order if col in df.columns]]
        df.to_excel(xlsx_path, index=False, engine='openpyxl')
        print(f"-> Đã xuất thành công file Excel tại {xlsx_path}")
    except (FileNotFoundError, ValueError) as e:
        print(f"-> Không có dữ liệu hoặc lỗi khi chuyển sang Excel: {e}")


# ===============================
# 5. Convert
# ===============================
def json_convert(data: Any, pretty: bool = True) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2 if pretty else None)

def jsonl_convert(data: List[dict]) -> str:
    return "\n".join(json.dumps(item, ensure_ascii=False) for item in data)


# ===============================
# 6. Sort
# ===============================
def sort_records(data: List[dict], keys: List[str]) -> List[dict]:
    """Sắp xếp theo nhiều keys với ưu tiên từ trái sang phải"""
    return sorted(data, key=lambda x: tuple(x.get(k) for k in keys))


# ===============================
# 7. Most Common
# ===============================
def most_common(values):
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]

DEFAULT_NON_KEEP_PATTERN = re.compile(r"[^\w\s\(\)\.\,\;\:\-–]", flags=re.UNICODE)

def preprocess_text(
    text: Any,
    non_keep_pattern: re.Pattern = DEFAULT_NON_KEEP_PATTERN,
    max_chars_per_text: int | None = None,
) -> Any:
    """
    Làm sạch chuỗi: strip, bỏ ký tự không mong muốn, rút gọn khoảng trắng.
    Vẫn cho phép list/dict đi qua để hàm preprocess_data xử lý đệ quy.
    """
    if isinstance(text, list):
        # Truyền tiếp đủ tham số khi gọi đệ quy
        return [preprocess_text(t, non_keep_pattern=non_keep_pattern, max_chars_per_text=max_chars_per_text) for t in text]
    if isinstance(text, str):
        s = text.strip()  # <-- sửa từ s = strip()
        s = non_keep_pattern.sub("", s)
        s = re.sub(r"[ ]{2,}", " ", s)
        if max_chars_per_text is not None and len(s) > max_chars_per_text:
            s = s[: max_chars_per_text]
        return s
    return text

def preprocess_data(
    data: Any,
    non_keep_pattern: re.Pattern = DEFAULT_NON_KEEP_PATTERN,
    max_chars_per_text: int | None = None,
) -> Any:
    """Đệ quy tiền xử lý lên toàn bộ JSON."""
    if isinstance(data, dict):
        return {
            k: preprocess_data(v, non_keep_pattern=non_keep_pattern, max_chars_per_text=max_chars_per_text)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [
            preprocess_data(x, non_keep_pattern=non_keep_pattern, max_chars_per_text=max_chars_per_text)
            for x in data
        ]
    return preprocess_text(data, non_keep_pattern=non_keep_pattern, max_chars_per_text=max_chars_per_text)


# ===============================
# 9. Json
# ===============================
def flatten_json(
    data: Any,
    prefix: str = "",
    flatten_mode: str = "split",  # mặc định: tách từng phần tử list
    join_sep: str = "\n",         # mặc định: xuống dòng khi join list
) -> Dict[str, Any]:
    """
    Làm phẳng JSON với xử lý list theo flatten_mode.

    - "split": mỗi phần tử list tạo key riêng: a.b[0], a.b[1], ...
               Nếu phần tử là dict/list → tiếp tục flatten (được lồng chỉ số).
    - "join":  join list về 1 chuỗi (join_sep). (Phần tử không phải str sẽ str())
    - "keep":  giữ nguyên list (chỉ gán 1 key cho toàn list).

    Trả về: dict key->giá trị (lá).
    """
    flat: Dict[str, Any] = {}

    def _recur(node: Any, pfx: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                new_pfx = f"{pfx}{k}" if not pfx else f"{pfx}.{k}"
                _recur(v, new_pfx)
            return

        if isinstance(node, list):
            if flatten_mode == "split":
                for i, item in enumerate(node):
                    idx_key = f"{pfx}[{i}]"
                    _recur(item, idx_key)
            elif flatten_mode == "join":
                joined = join_sep.join(str(x).strip() for x in node if str(x).strip())
                flat[pfx] = joined
            else:  # "keep"
                flat[pfx] = node
            return

        # lá: số/chuỗi/None/...
        flat[pfx] = node

    _recur(data, prefix.rstrip("."))
    return flat


def deduplicates_by_key(pairs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    Lọc trùng theo value trong cùng key (hoặc base_key).

    Giữ lại **lần xuất hiện đầu tiên** của mỗi (key, text),
    loại bỏ những dòng có cùng key và cùng text lặp lại sau đó.

    Args:
        pairs: Danh sách (key, text) sau khi flatten.

    Returns:
        Danh sách (key, text) đã loại bỏ trùng lặp.
    """
    seen_per_key: Dict[str, set] = {}
    filtered: List[Tuple[str, str]] = []

    for key, text in pairs:
        text_norm = text.strip()
        if not text_norm:
            continue

        base_key = re.sub(r"\[\d+\]", "", key)
        if base_key not in seen_per_key:
            seen_per_key[base_key] = set()

        if text_norm in seen_per_key[base_key]:
            continue

        seen_per_key[base_key].add(text_norm)
        filtered.append((key, text_norm))

    return filtered
