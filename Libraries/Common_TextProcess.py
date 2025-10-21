import re

from difflib import SequenceMatcher

from . import Common_MyUtils as MyUtils

ex = MyUtils.exc

# ===============================
# 1. Abbreviation
# ===============================

# Phụ âm đầu
VALID_ONSETS = [
    "b", "c", "ch", "d", "đ", "g", "gh", "gi",
    "h", "k", "kh", "l", "m", "n", "ng", "ngh",
    "nh", "p", "ph", "q", "r", "s", "t", "th",
    "tr", "v", "x"
]

# Nguyên âm
VALID_NUCLEI = [
    "a", "ă", "â", "e", "ê", "i", "o", "ô", "ơ", "u", "ư", "y",

    "ia", "iê", "ya", "ya", "ua", "uô", "ưa", "ươ",
    "ai", "ao", "au", "ay", "âu", "ây",
    "eo", "êu",
    "ia", "iê", "yê",
    "oi", "ôi", "ơi",
    "ua", "uô", "ươ", "ưu", "uy", "uya"
]

# Phụ âm cuối
VALID_CODAS = ["c", "ch", "m", "n", "ng", "nh", "p", "t"]

# ===== Hàm kiểm tra viết tắt =====
def is_abbreviation(word: str) -> bool:
    """
    Trả về True nếu từ KHÔNG phải âm tiết tiếng Việt chuẩn,
    tức là có khả năng là viết tắt.
    Quy tắc:
    1. Không có nguyên âm hoặc nguyên âm không hợp lệ -> viết tắt
    2. Phụ âm đầu không hợp lệ -> viết tắt
    3. Phụ âm cuối không hợp lệ -> viết tắt
    4. Nhiều hơn 3 phần (đầu - nguyên âm - cuối) -> viết tắt
    """
    w = word.lower()
    w = re.sub(r'[^a-zăâêôơưđ]', '', w)

    if not w:
        return True

    # 1. Tìm phụ âm đầu
    onset = None
    for o in sorted(VALID_ONSETS, key=len, reverse=True):
        if w.startswith(o):
            onset = o
            break

    rest = w[len(onset):] if onset else w
    if onset is None and rest and rest[0] not in "aeiouyăâêôơư":
        return True  # phụ âm đầu không hợp lệ

    # 2. Tìm phụ âm cuối
    coda = None
    for c in sorted(VALID_CODAS, key=len, reverse=True):
        if rest.endswith(c):
            coda = c
            break

    nucleus = rest[:-len(coda)] if coda else rest

    # 3. Kiểm tra nguyên âm
    if not nucleus:
        return True
    if nucleus not in VALID_NUCLEI:
        return True

    # 4. Kiểm tra số phần
    parts = [p for p in [onset, nucleus, coda] if p]
    if len(parts) > 3:
        return True

    return False

# ===============================
# 2. Words
# ===============================

# ===== Hàm chuẩn hóa từ ======================
def normalize_word(w: str) -> str:
    return re.sub(r'[^A-Za-zÀ-ỹĐđ0-9]', '', w)

# ===== Hàm so sánh độ tương đồng =============
def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

# ===== Hàm chuyển số La Mã ===================
def is_roman(s):
    return bool(re.fullmatch(r'[IVXLC]+', s))

# ===== Chuyển số La Mã sang số Ả Rập =========
def roman_to_int(s):
    roman_numerals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}
    result, prev = 0, 0
    for c in reversed(s):
        val = roman_numerals.get(c, 0)
        if val < prev:
            result -= val
        else:
            result += val
            prev = val
    return result

# ===== Hàm loại bỏ khoảng trắng thừa =========
def strip_extra_spaces(s: str) -> str:
    if not isinstance(s, str):
        return s
    return re.sub(r'\s+', ' ', s).strip()

def merge_txt(RawDataDict, JsonKey, JsonField):
    paragraphs = RawDataDict.get(JsonKey, [])
    merged = "\n".join(p.get(JsonField, "").strip() for p in paragraphs if p.get(JsonField))
    merged = re.sub(r"\n{2,}", "\n", merged.strip())
    return merged