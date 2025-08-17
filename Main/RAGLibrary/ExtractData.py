"""
Module ExtractData (refactored)
- Tách riêng các nhóm hàm: Utils, get*, set*, delStatus, extractData
- Đầu ra JSON rõ ràng, dễ bảo trì, dễ mở rộng
"""

import re
import os
import json
import tempfile
from collections import Counter
import fitz
from docx2pdf import convert


# ==== 1. Utils ====
def load_exceptions(file_path="exceptions.json"):
    """Nạp danh sách ngoại lệ từ JSON"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {
                "common_words": set(data.get("common_words", [])),
                "proper_names": [item["text"] for item in data.get("proper_names", [])],
                "abbreviations": set(item["text"].lower() for item in data.get("abbreviations", []))
            }
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        raise Exception(f"Lỗi khi tải ngoại lệ: {e}")


def load_patterns(markers_path="markers.json", status_path="status.json"):
    """Nạp danh sách marker, status pattern từ JSON"""
    try:
        with open(markers_path, 'r', encoding='utf-8') as f:
            markers_data = json.load(f)

        keywords = markers_data.get("keywords", [])
        title_keywords = '|'.join(re.escape(k[0].upper() + k[1:].lower()) for k in keywords)
        upper_keywords = '|'.join(re.escape(k.upper()) for k in keywords)
        all_keywords = f"{title_keywords}|{upper_keywords}"

        compiled_markers = []
        for item in markers_data.get("markers", []):
            pattern_str = item["pattern"].replace("{keywords}", all_keywords)
            try:
                compiled_pattern = re.compile(pattern_str)
            except re.error:
                continue
            compiled_markers.append({
                "pattern": compiled_pattern,
                "description": item.get("description", ""),
                "type": item.get("type", "")
            })

        return {
            "markers": compiled_markers,
            "keywords_set": set(k.lower() for k in keywords)
        }
    except Exception as e:
        raise Exception(f"Lỗi khi tải mẫu: {e}")


def similar(a, b):
    """So sánh độ tương đồng hai chuỗi"""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()


def is_roman(s):
    return bool(re.fullmatch(r'[IVXLC]+', s))


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

def extract_marker(text, patterns):
    for pattern_info in patterns["markers"]:
        match = pattern_info["pattern"].match(text)
        if match:
            marker_text = re.sub(r'^\s+', '', match.group(0))
            marker_text = re.sub(r'\s+$', ' ', marker_text) 
            return {
                "marker_text": marker_text
            }
    return {
        "marker_text": None
    }

def format_marker(marker_text, patterns):
    """
    Chuẩn hoá MarkerText theo đúng logic cũ:
    1. Số Ả Rập  => '123'
    2. Số La Mã  => 'XVI'
    3. Token 1 ký tự: a..z => 'abc', A..Z => 'ABC'
    4. Token nằm trong keywords_set thì giữ nguyên
    5. Các token khác giữ nguyên
    """
    if not marker_text:
        return None
    
    formatted = marker_text
    # 1. Chuẩn hoá số Ả Rập
    formatted = re.sub(r'\b[0-9]+\b', '123', formatted)
    # 2. Chuẩn hoá số La Mã
    formatted = re.sub(r'\b[IVXLC]+\b', 'XVI', formatted)

    # 3. Xử lý từng token
    parts = re.split(r'(\W+)', formatted)
    formatted_parts = []
    
    for part in parts:
        if re.match(r'(\W+)', part):
            formatted_parts.append(part)
            continue

        if part.lower() in patterns["keywords_set"]:
            formatted_parts.append(part)
        elif re.match(r'^[a-z]$', part):
            formatted_parts.append('abc')
        elif re.match(r'^[A-Z]$', part):
            formatted_parts.append('ABC')
        else:
            formatted_parts.append(part)
    
    return ''.join(formatted_parts)


# ==== 2. Các hàm get* ====
def getPageGeneralSize(page):
    return [round(page.rect.height, 1), round(page.rect.width, 1)]


def getText(line):
    return line.get("text", "")


def getMarker(text, patterns):
    info = extract_marker(text, patterns)
    marker_text = info.get("marker_text")
    marker_type = format_marker(marker_text, patterns) if marker_text else None
    return marker_text, marker_type


def getStyle(line, exceptions):
    """CaseStyle + FontStyle"""
    text = line.get("text", "")
    spans = line.get("spans", [])
    # CaseStyle
    words = text.split()
    exception_texts = exceptions["common_words"] | set(exceptions["proper_names"]) | exceptions["abbreviations"]
    filtered = [w for w in words if w.lower() not in exception_texts]
    if all(w.isupper() for w in filtered if w.isalpha()):
        case_style = 1000
    elif all(w.istitle() for w in filtered if w.isalpha()):
        case_style = 2000
    else:
        case_style = 3000
    # FontStyle
    font_style = 0
    for s in spans:
        bold = bool(s["flags"] & 16)
        italic = bool(s["flags"] & 2)
        underline = bool(s["flags"] & 8)
        font_style = (100 if bold else 0) + (10 if italic else 0) + (1 if underline else 0)
        break
    return case_style + font_style


def getFontSize(line):
    spans = line.get("spans", [])
    if spans:
        return round(spans[0]["size"], 1)
    return 12.0


def getCoords(line):
    spans = line.get("spans", [])
    if not spans:
        return (0, 0, 0, 0, 0)
    x0 = round(spans[0]["bbox"][0], 1)
    y0 = round(spans[0]["bbox"][1], 1)
    x1 = round(spans[-1]["bbox"][2], 1)
    y1 = round(spans[-1]["bbox"][3], 1)
    xm = round((x0 + x1) / 2, 1)
    return (x0, x1, xm, y0, y1)


def getWord(line, position="first"):
    words = line.get("text", "").split()
    if not words:
        return ("", 0, 0.0, 0.0)
    word = words[0] if position == "first" else words[-1]
    style = getStyle(line, {"common_words": set(), "proper_names": [], "abbreviations": set()})
    font_size = getFontSize(line)
    width = len(word) * (font_size * 0.5)  # ước lượng
    return (word, style, font_size, round(width, 1))


def getFirstWord(line):
    t, s, f, w = getWord(line, "first")
    return {"Text": t, "Style": s, "FontSize": f, "Width": w}


def getLastWord(line):
    t, s, f, w = getWord(line, "last")
    return {"Text": t, "Style": s, "FontSize": f, "Width": w}


def getTextStatus(pdf_path, exceptions, patterns):
    """Trích xuất thông tin gốc từ PDF"""
    doc = fitz.open(pdf_path)
    general = {"pageGeneralSize": getPageGeneralSize(doc[0])}
    lines = []
    for i, page in enumerate(doc):
        text_dict = page.get_text("dict")
        for block in text_dict["blocks"]:
            if "lines" in block:
                for l in block["lines"]:
                    text = "".join(span["text"] for span in l["spans"]).strip()
                    if not text:
                        continue
                    marker_text, marker_type = getMarker(text, patterns)
                    style = getStyle({"text": text, "spans": l["spans"]}, exceptions)
                    fontsize = getFontSize({"spans": l["spans"]})
                    x0, x1, xm, y0, y1 = getCoords({"spans": l["spans"]})
                    line_dict = {
                        "Line": len(lines) + 1,
                        "Text": text,
                        "MarkerText": marker_text,
                        "MarkerType": marker_type,
                        "Style": style,
                        "FontSize": fontsize,
                        "Words": {
                            "First": getFirstWord({"text": text, "spans": l["spans"]}),
                            "Last": getLastWord({"text": text, "spans": l["spans"]})
                        },
                        "Coords": {"X0": x0, "X1": x1, "XM": xm, "Y0": y0, "Y1": y1}
                    }
                    lines.append(line_dict)
    return {"general": general, "lines": lines}


# ==== 3. Các hàm set* ====
def setPageCoords(lines):
    x0s = [l["Coords"]["X0"] for l in lines]
    x1s = [l["Coords"]["X1"] for l in lines]
    y0s = [l["Coords"]["Y0"] for l in lines]
    y1s = [l["Coords"]["Y1"] for l in lines]
    xStart, yStart = min(x0s), min(y0s)
    xEnd, yEnd = max(x1s), max(y1s)
    return (xStart, yStart, xEnd, yEnd, round((xStart + xEnd)/2, 1), round((yStart + yEnd)/2, 1))


def setPageRegionSize(xStart, yStart, xEnd, yEnd):
    return (round(xEnd - xStart, 1), round(yEnd - yStart, 1))


def setCommonStatus(lines, attr, rank=1):
    values = [l[attr] for l in lines if l.get(attr) is not None]
    counter = Counter(values)
    return counter.most_common(rank)


def setCommonFontSize(lines):
    fs, _ = setCommonStatus(lines, "FontSize", 1)[0]
    return round(fs, 1)


def setCommonMarkers(lines):
    total = len(lines)
    counter = Counter([l["MarkerType"] for l in lines if l["MarkerType"]])
    results = []
    for marker, count in counter.most_common(10):
        if count >= total * 0.005:
            results.append(marker)
        else:
            break
    return results


def setLineSize(line):
    x0, x1, y0, y1 = line["Coords"]["X0"], line["Coords"]["X1"], line["Coords"]["Y0"], line["Coords"]["Y1"]
    return (round(x1 - x0, 1), round(y1 - y0, 1))


def setPosition(line, prev_line, next_line, xStart, xEnd, xMid):
    left = round(line["Coords"]["X0"] - xStart, 1)
    right = round(xEnd - line["Coords"]["X1"], 1)
    mid = round(line["Coords"]["XM"] - xMid, 1)
    top = round(line["Coords"]["Y1"] - prev_line["Coords"]["Y1"], 1) if prev_line else 0
    bot = round(next_line["Coords"]["Y1"] - line["Coords"]["Y1"], 1) if next_line else 0
    return (left, right, mid, top, bot)


def setAlign(position, regionWidth):
    mid = abs(position["Mid"])
    left = position["Left"]
    if mid <= 0.01 * regionWidth:
        if left > 0.01 * regionWidth:
            return "Center"
        else:
            return "Justify"
    elif position["Mid"] > 0.01 * regionWidth:
        return "Right"
    else:
        return "Left"


def setTextStatus(baseJson):
    lines = baseJson["lines"]
    xStart, yStart, xEnd, yEnd, xMid, yMid = setPageCoords(lines)
    regionWidth, regionHeight = setPageRegionSize(xStart, yStart, xEnd, yEnd)
    commonFontSize = setCommonFontSize(lines)
    commonMarkers = setCommonMarkers(lines)

    new_general = {
        "pageGeneralSize": baseJson["general"]["pageGeneralSize"],
        "pageCoords": {"xStart": xStart, "yStart": yStart, "xEnd": xEnd, "yEnd": yEnd, "xMid": xMid, "yMid": yMid},
        "pageRegionWidth": regionWidth,
        "pageRegionHeight": regionHeight,
        "commonFontSize": commonFontSize,
        "commonMarkers": commonMarkers
    }

    new_lines = []
    for i, line in enumerate(lines):
        lineWidth, lineHeight = setLineSize(line)
        pos = setPosition(line, lines[i-1] if i > 0 else None,
                        lines[i+1] if i < len(lines)-1 else None,
                        xStart, xEnd, xMid)
        pos_dict = {"Left": pos[0], "Right": pos[1], "Mid": pos[2], "Top": pos[3], "Bot": pos[4]}

        line_dict = {
            **line,
            "LineWidth": lineWidth,
            "LineHeight": lineHeight,
            "Position": pos_dict,
            "Align": setAlign(pos_dict, regionWidth)
        }

        new_lines.append(line_dict)

    return {"general": new_general, "lines": new_lines}


# ==== 4. Hàm delStatus ====
def delStatus(jsonDict, deleteList):
    for line in jsonDict["lines"]:
        for attr in deleteList:
            if attr in line:
                del line[attr]
    return jsonDict


# ==== 5. Hàm chính extractData ====
def extractData(path, exceptions_path="exceptions.json", markers_path="markers.json", status_path="status.json"):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File {path} không tồn tại")
    file_ext = os.path.splitext(path)[1].lower()
    pdf_path = path
    temp_file = None
    if file_ext == ".docx":
        temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        convert(path, temp_file.name)
        pdf_path = temp_file.name

    try:
        exceptions = load_exceptions(exceptions_path)
        patterns = load_patterns(markers_path, status_path)

        baseJson = getTextStatus(pdf_path, exceptions, patterns)
        modifiedJson = setTextStatus(baseJson)
        finalJson = delStatus(modifiedJson, ["Position", "Coords"])
        return finalJson
    finally:
        if temp_file:
            os.remove(temp_file.name)
