# MergeData.py
from statistics import mean, multimode
from collections import Counter


# ===============================
# HÀM CHÍNH
# ===============================
def mergeLinesToParagraphs(baseJson):
    """
    Nhận vào JSON sau extractData (lines-level)
    Trả về JSON mới (paragraph-level)
    """
    general = baseJson["general"]
    lines = baseJson["lines"]

    paragraphs = []
    buffer = []

    for i, curr in enumerate(lines):
        if not buffer:
            buffer.append(curr)
            continue

        prev = lines[i-1]

        if canMerge(prev, curr, i-1, i):
            buffer.append(curr)

        else:
            paragraphs.append(buildParagraph(buffer, len(paragraphs)+1, general))
            buffer = [curr]

    if buffer:
        paragraphs.append(buildParagraph(buffer, len(paragraphs)+1, general))

    merged = {"general": general, "paragraphs": paragraphs}
    # >>> TÍNH LẠI 'common' TRONG GENERAL DỰA TRÊN PARAGRAPHS
    merged = recomputeCommonsInGeneralAfterMerge(merged)

    return {"general": general, "paragraphs": paragraphs}



# ===============================
# CÁC HÀM ĐIỀU KIỆN MERGE
# ===============================

def canMerge(prev, curr, idx_prev=None, idx_curr=None):
    """
    Kiểm tra line curr có thể merge vào prev không
    Ghi log lý do True/False
    """
    pair = f"[{idx_prev+1}->{idx_curr+1}]" if idx_prev is not None else ""

    if isNewPara(curr):
        print(f"{pair} Merge=False | Reason: isNewPara")
        return False

    if not isSameFontSize(prev, curr):
        print(f"{pair} Merge=False | Reason: FontSize mismatch")
        return False

    if not isSameFStyle(prev, curr):
        print(f"{pair} Merge=False | Reason: Style mismatch")
        return False
    
    if not isNear(prev, curr):
        print(f"{pair} Merge=False | Reason: Not near")
        return False

    if isSameAlign(prev, curr):
        print(f"{pair} Merge=True | Reason: SameAlign")
        return True

    if isBadAlign(prev, curr):
        print(f"{pair} Merge=False | Reason: BadAlign")
        return False

    if canMergeWithAlign(prev) or canMergeWithLeft(prev, curr):
        print(f"{pair} Merge=True | Reason: Align exception")
        return True

    print(f"{pair} Merge=False | Reason: Fallback")
    return False


# Check MarkerText
def isNewPara(line):
    return line.get("MarkerText") not in (None, "", " ")

# Check FontSize
def isSameFontSize(prev, curr):
    return abs(prev["FontSize"] - curr["FontSize"]) <= 0.7


# Check Style
def isSameStyle(prev, curr):
    return isSameLineStyle(prev, curr) or isSameFirstStyle(prev, curr) or isSameLastStyle(prev, curr) or isSameWordStyle(prev, curr)

def isSameFStyle(prev, curr):
    return isSameLineFStyle(prev, curr) or isSameFirstFStyle(prev, curr) or isSameLastFStyle(prev, curr) or isSameWordFStyle(prev, curr)

def isSameCase(prev, curr):
    return isSameLineCase(prev, curr) or isSameFirstCase(prev, curr) or isSameLastCase(prev, curr) or isSameWordCase(prev, curr)

# Line - Line
def isSameLineStyle(prev, curr):
    return prev["Style"] == curr["Style"]

def isSameLineFStyle(prev, curr):
    return prev["Style"] %1000 == curr["Style"] %1000

def isSameLineCase(prev, curr):
    return prev["Style"] /1000 == curr["Style"] /1000

# First - Line
def isSameFirstStyle(prev, curr):
    return prev["Style"] == curr["Words"]["First"]["Style"]

def isSameFirstFStyle(prev, curr):
    return prev["Style"] %1000 == curr["Words"]["First"]["Style"] %1000

def isSameFirstCase(prev, curr):
    return prev["Style"] /1000 == curr["Words"]["First"]["Style"] /1000

# Last - Line
def isSameLastStyle(prev, curr):
    return prev["Words"]["Last"]["Style"] == curr["Style"]

def isSameLastFStyle(prev, curr):
    return prev["Words"]["Last"]["Style"] %1000 == curr["Style"] %1000

def isSameLastCase(prev, curr):
    return prev["Words"]["Last"]["Style"] /1000 == curr["Style"] /1000

# Last - First
def isSameWordStyle(prev, curr):
    return prev["Words"]["Last"]["Style"] == curr["Words"]["First"]["Style"]

def isSameWordFStyle(prev, curr):
    return prev["Words"]["Last"]["Style"] %1000 == curr["Words"]["First"]["Style"] %1000

def isSameWordCase(prev, curr):
    return prev["Words"]["Last"]["Style"] /1000 == curr["Words"]["First"]["Style"] /1000


# Linespace
def isNear(prev, curr):
    if "Position" not in prev or "Position" not in curr:
        return False
    if "LineHeight" not in curr:
        return False
    
    hig_curr = curr["LineHeight"]
    top_prev = prev["Position"]["Top"]
    top_curr = curr["Position"]["Top"]
    bot_curr = curr["Position"]["Bot"]
    
    return (top_curr < top_prev * 2) and (top_curr < bot_curr * 2) and (top_curr < hig_curr * 5)


def isSameAlign(prev, curr):
    return prev.get("Align") == curr.get("Align")

def isBadAlign(prev, curr):
    return (prev.get("Align") != "right" and curr.get("Align") == "right")

def isNoSameAlign0(prev):
    return prev.get("Align") == "Justify"

def isNoSameAlignC(prev):
    return prev.get("Align") == "Center"

def isNoSameAlignR(prev):
    return prev.get("Align") == "Right"

def isNoSameAlignL(prev, curr):
    return prev.get("Align") == "Left" and curr.get("Align") == "Justify"

def canMergeWithAlign(prev):
    return isNoSameAlign0(prev) or isNoSameAlignC(prev) or isNoSameAlignR(prev)

def canMergeWithLeft(prev, curr):
    return isNoSameAlignL(prev, curr)


# ===============================
# HÀM BUILD PARAGRAPH
# ===============================

def buildParagraph(lines, para_id, general=None):
    """
    Tạo dict Paragraph từ list lines đã merge
    """
    text = " ".join([ln["Text"] for ln in lines])
    marker_text = lines[0]["MarkerText"]
    marker_type = lines[0]["MarkerType"]

    # Style: lấy min theo từng chữ số
    style = mergeStyle([ln["Style"] for ln in lines])

    # first_word = lines[0]["Words"]["First"]
    # last_word = lines[-1]["Words"]["Last"]

    fs_values = [ln["FontSize"] for ln in lines if ln.get("FontSize") is not None]

    if fs_values:
        modes = multimode(fs_values)  # trả về list tất cả các mode
        if len(modes) == 1:
            font_size = modes[0]
        else:
            # có nhiều mode → chọn gần với commonFontSize trong general
            if general and general.get("commonFontSize") is not None:
                target = general["commonFontSize"]
                font_size = min(modes, key=lambda x: abs(x - target))
            else:
                font_size = mean(fs_values)
        font_size = round(font_size, 1)
    else:
        font_size = 12.0
    align = mostCommon([ln["Align"] for ln in lines]) or lines[-1]["Align"]

    return {
        "Paragraph": para_id,
        "Text": text,
        "MarkerText": marker_text,
        "MarkerType": marker_type,
        "Style": style,
        "FontSize": font_size,
        "Align": align,
        # "Words": {
        #     "First": first_word,
        #     "Last": last_word
        # }
    }


# ===============================
# HELPERS
# ===============================

def mergeStyle(styles):
    """
    styles: list số 4 chữ số (CaseStyle*1000 + FontStyle)
    - Lấy min của từng chữ số
    """
    digits = [list(str(s).zfill(4)) for s in styles]
    min_digits = [min(int(d[i]) for d in digits) for i in range(4)]
    return int("".join(str(d) for d in min_digits))


def mostCommon(values):
    if not values:
        return None
    count = Counter(values)
    most = count.most_common(1)
    return most[0][0] if most else None


# ===============================
# RESOLVE COMMONS
# ===============================

def recomputeCommonsInGeneralAfterMerge(mergedJson):
    """
    Cập nhật lại các 'common' trong mergedJson['general'] dựa trên danh sách paragraphs.
    Các field cập nhật:
      - commonFontSize
      - commonFontSizes: [{FontSize, Count}, ...] (giảm dần theo Count)
      - commonMarkers: top marker thỏa ngưỡng >= 0.5% tổng số paragraph, tối đa 10 mục
    """
    paragraphs = mergedJson.get("paragraphs", [])
    total = len(paragraphs)

    # --- Font sizes ---
    fs_values = [p["FontSize"] for p in paragraphs if p.get("FontSize") is not None]
    fs_counter = Counter(fs_values)

    commonFontSizes = [{"FontSize": round(fs, 1), "Count": cnt}
                       for fs, cnt in fs_counter.most_common()]
    commonFontSize = commonFontSizes[0]["FontSize"] if commonFontSizes else None

    # --- Markers ---
    mk_values = [p["MarkerType"] for p in paragraphs if p.get("MarkerType")]
    mk_counter = Counter(mk_values)
    threshold = max(1, int(total * 0.005))
    commonMarkers = [m for m, c in mk_counter.most_common(10) if c >= threshold]

    # --- Ghi đè vào general ---
    mergedJson["general"].update({
        "commonFontSize": commonFontSize,
        "commonFontSizes": commonFontSizes,
        "commonMarkers": commonMarkers
    })
    return mergedJson
