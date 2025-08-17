# MergeData.py

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
    current_para = []

    for i, line in enumerate(lines):
        if not current_para:
            current_para.append(line)
        else:
            prev_line = current_para[-1]
            if canMerge(prev_line, line):
                current_para.append(line)
            else:
                paragraphs.append(buildParagraph(current_para, len(paragraphs)+1))
                current_para = [line]

    if current_para:
        paragraphs.append(buildParagraph(current_para, len(paragraphs)+1))

    return {"general": general, "paragraphs": paragraphs}


# ===============================
# CÁC HÀM ĐIỀU KIỆN MERGE
# ===============================
def canMerge(prev, curr):
    """
    Kiểm tra line curr có thể merge vào prev không
    """
    # Trường hợp mở đoạn mới
    if isNewPara(curr):
        return False

    if not isSameFontSize(prev, curr):
        return False

    if not isSameStyle(prev, curr):
        return False

    if not isNear(prev, curr):
        return False

    if isSameAlign(prev, curr):
        return True

    if isBadAlign(prev, curr):
        return False

    if canMergeWithAlign(prev, curr) or canMergeWithLeft(prev, curr):
        return True

    return False


def isNewPara(line):
    return line.get("MarkerText") not in (None, "", " ")


def isSameFontSize(prev, curr):
    return abs(prev["FontSize"] - curr["FontSize"]) <= 0.7


def isSameStyle(prev, curr):
    return isSameLineStyle(prev, curr) or isSameFirstStyle(prev, curr) or isSameLastStyle(prev, curr) or isSameWordStyle(prev, curr)


def isSameLineStyle(prev, curr):
    return prev["Style"] == curr["Style"]


def isSameFirstStyle(prev, curr):
    return prev["Style"] == curr["Words"]["First"]["Style"]


def isSameLastStyle(prev, curr):
    return prev["Words"]["Last"]["Style"] == curr["Style"]


def isSameWordStyle(prev, curr):
    return prev["Words"]["Last"]["Style"] == curr["Words"]["First"]["Style"]


def isNear(prev, curr):
    if "Position" not in prev or "Position" not in curr:
        return False
    if "LineHeight" not in curr:
        return False
    
    hig_curr = curr["LineHeight"]

    top_prev = prev["Position"]["Top"]
    top_curr = curr["Position"]["Top"]
    bot_curr = curr["Position"]["Bot"]
    
    return (top_curr < top_prev * 1.75) and (top_curr < bot_curr * 1.75) and (top_curr < hig_curr*4)


def isSameAlign(prev, curr):
    return prev.get("Align") == curr.get("Align")


def isBadAlign(prev, curr):
    return (prev.get("Align") != "right" and curr.get("Align") == "right")


def isNoSameAlign0(prev):
    return prev.get("Align") == "justify"


def isNoSameAlignC(prev):
    return prev.get("Align") == "center"


def isNoSameAlignR(prev):
    return prev.get("Align") == "right"


def isNoSameAlignL(prev, curr):
    return prev.get("Align") == "left" and curr.get("Align") == "justify"


def canMergeWithAlign(prev, curr):
    return isNoSameAlign0(prev) or isNoSameAlignC(prev) or (isNoSameAlignR(prev) and curr.get("Align") != "center")


def canMergeWithLeft(prev, curr):
    return isNoSameAlignL(prev, curr)


# ===============================
# HÀM BUILD PARAGRAPH
# ===============================
def buildParagraph(lines, para_id):
    """
    Tạo dict Paragraph từ list lines đã merge
    """
    text = " ".join([ln["Text"] for ln in lines])
    marker_text = lines[0]["MarkerText"]
    marker_type = lines[0]["MarkerType"]

    # Style: lấy min theo từng chữ số
    style = mergeStyle([ln["Style"] for ln in lines])

    first_word = lines[0]["Words"]["First"]
    last_word = lines[-1]["Words"]["Last"]

    font_size = round(sum([ln["FontSize"] for ln in lines]) / len(lines), 1)
    align = mostCommon([ln["Align"] for ln in lines]) or lines[-1]["Align"]

    return {
        "Paragraph": para_id,
        "Text": text,
        "MarkerText": marker_text,
        "MarkerType": marker_type,
        "Style": style,
        "FontSize": font_size,
        "Align": align,
        "Words": {
            "First": first_word,
            "Last": last_word
        }
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
