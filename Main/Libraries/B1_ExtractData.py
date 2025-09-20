import re
import os
import json
import tempfile
import fitz
from collections import Counter, defaultdict
from difflib import SequenceMatcher


# ===============================
# 1. Utils
# ===============================
def load_exceptions(file_path="../tests/ex.exceptions.json"):
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


def load_patterns(markers_path="../tests/ex.markers.json", status_path="../tests/ex.status.json"):
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
            return {"marker_text": marker_text}
    return {"marker_text": None}


def format_marker(marker_text, patterns):
    """
    Chuẩn hoá MarkerText theo đúng logic cũ
    """
    if not marker_text:
        return None

    formatted = marker_text
    formatted = re.sub(r'\b[0-9]+\b', '123', formatted)        # số Ả Rập
    formatted = re.sub(r'\b[IVXLC]+\b', 'XVI', formatted)      # số La Mã

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
        elif re.match(r'^[a-zđêôơư]$', part):
            formatted_parts.append('abc')
        elif re.match(r'^[A-Z]$', part):
            formatted_parts.append('ABC')
        elif re.match(r'^[A-ZĐÊÔƠƯ]$', part):
            formatted_parts.append('ABC')
        else:
            formatted_parts.append(part)
    return ''.join(formatted_parts)


def normalizeRomanMarkers(lines):
    """
    Chuẩn hoá MarkerType cho các nhóm có số La Mã
    """
    format_groups = defaultdict(list)
    for idx, line in enumerate(lines):
        fmt = line.get("MarkerType")
        marker = line.get("MarkerText")
        if fmt and marker:
            format_groups[fmt].append((idx, marker))

    for fmt, group in format_groups.items():
        roman_markers = []
        for idx, marker in group:
            m = re.search(r'\b([IVXLC]+)\b', marker)
            if m and is_roman(m.group(1)):
                roman_markers.append((idx, m.group(1)))
            else:
                break

        if roman_markers:
            roman_numbers = [roman_to_int(rm[1]) for rm in roman_markers]
            expected = list(range(min(roman_numbers), max(roman_numbers) + 1))
            if sorted(roman_numbers) != expected:
                for idx, _ in roman_markers:
                    lines[idx]["MarkerType"] = re.sub(r'\b[IVXLC]+\b', "ABC", lines[idx]["MarkerType"])
    return lines


# ===============================
# 2. Các hàm get*
# ===============================
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
    """CaseStyle (toàn line) + FontStyle (min theo từng thuộc tính trên mọi span)"""
    text = line.get("text", "")
    spans = line.get("spans", [])

    # ===== CaseStyle (giữ logic cũ, tính trên toàn line sau khi lọc ngoại lệ) =====
    words = text.split()
    exception_texts = exceptions["common_words"] | set(exceptions["proper_names"]) | exceptions["abbreviations"]

    filtered = []
    for w in words:
        clean_w = re.sub(r'[^a-zA-ZÀ-ỹà-ỹ0-9]', '', w)
        if clean_w and clean_w.lower() not in exception_texts:
            filtered.append(clean_w)

    if filtered:
        if all(w.isupper() for w in filtered):
            case_style = 3000
        elif all(w.istitle() for w in filtered):
            case_style = 2000
        else:
            case_style = 1000
    else:
        case_style = 1000  # mặc định

    # ===== FontStyle (min theo từng thuộc tính trên các spans) =====
    if spans:
        bold_all = True
        italic_all = True
        underline_all = True
        for s in spans:
            flags = s.get("flags", 0)
            b = bool(flags & 16)
            i = bool(flags & 2)
            u = bool(flags & 8)
            bold_all = bold_all and b
            italic_all = italic_all and i
            underline_all = underline_all and u
        font_style = (100 if bold_all else 0) + (10 if italic_all else 0) + (1 if underline_all else 0)
    else:
        font_style = 0

    return case_style + font_style


def round_half(x):
    """Làm tròn số về bội số gần nhất của 0.5"""
    return round(x * 2) / 2.0

def getFontSize(line):
    spans = line.get("spans", [])
    if spans:
        valid_spans = [s for s in spans if s.get("text", "").strip()]
        if valid_spans:
            sizes = [s.get("size", 12.0) for s in valid_spans]
        else:
            sizes = [s.get("size", 12.0) for s in spans]  # fallback

        avg = sum(sizes) / len(sizes)
        return round(avg * 2) / 2  # làm tròn 0.5
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
    """
    Lấy (Text, Style, FontSize) của từ đầu/cuối dựa trên chính span chứa từ đó
    - Hoàn toàn độc lập với Style/FontSize của line
    - Bỏ qua spans rỗng / chỉ chứa khoảng trắng
    """
    spans = line.get("spans", [])
    full_text = line.get("text", "")
    if not spans or not full_text.strip():
        return ("", 0, 0.0)

    # chỉ giữ spans có chữ thật
    valid_spans = [s for s in spans if s.get("text", "").strip()]
    if not valid_spans:
        valid_spans = spans  # fallback

    def build_style_for_word(word_text, span):
        # CaseStyle cho CHÍNH từ đó
        clean = re.sub(r'[^A-Za-zÀ-ỹà-ỹ0-9]', '', word_text)
        if clean and clean.isupper():
            cs = 3000
        elif clean and clean.istitle():
            cs = 2000
        else:
            cs = 1000

        # FontStyle từ span của từ đó
        flags = span.get("flags", 0)
        bold = bool(flags & 16)
        italic = bool(flags & 2)
        underline = bool(flags & 8)
        fs = (100 if bold else 0) + (10 if italic else 0) + (1 if underline else 0)

        return cs + fs

    if position == "first":
        for s in valid_spans:
            words_in_span = s.get("text", "").split()
            if words_in_span:
                raw = words_in_span[0]
                word = raw.rstrip(".,!?;:…")
                size = round(s.get("size", 12.0), 1)
                style = build_style_for_word(word, s)
                return (word, style, size)
    else:
        for s in reversed(valid_spans):
            words_in_span = s.get("text", "").split()
            if words_in_span:
                raw = words_in_span[-1]
                word = raw.rstrip(".,!?;:…")
                size = round(s.get("size", 12.0), 1)
                style = build_style_for_word(word, s)
                return (word, style, size)

    return ("", 0, 0.0)


def getFirstWord(line):
    t, s, f = getWord(line, "first")
    return {"Text": t, "Style": s, "FontSize": f}


def getLastWord(line):
    t, s, f = getWord(line, "last")
    return {"Text": t, "Style": s, "FontSize": f}

def getLastWord(line):
    t, s, f = getWord(line, "last")
    return {"Text": t, "Style": s, "FontSize": f}


def getTextStatus(pdf_path, exceptions, patterns):
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


# ===============================
# 3. Các hàm set*
# ===============================
def most_common(values):
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]


def setPageCoords(lines, pageGeneralSize):
    x0s = [round(l["Coords"]["X0"], 1) for l in lines]
    x1s = [round(l["Coords"]["X1"], 1) for l in lines]
    y0s = [round(l["Coords"]["Y0"], 1) for l in lines]
    y1s = [round(l["Coords"]["Y1"], 1) for l in lines]

    xStart = most_common(x0s)
    page_width = pageGeneralSize[1]
    threshold = page_width * 0.75
    x1_candidates = [x for x in x1s if x >= threshold]
    xEnd = most_common(x1_candidates) if x1_candidates else max(x1s)

    yStart = min(y0s)
    yEnd = max(y1s)
    xMid = round((xStart + xEnd) / 2, 1)
    yMid = round((yStart + yEnd) / 2, 1)

    return (xStart, yStart, xEnd, yEnd, xMid, yMid)


def setPageRegionSize(xStart, yStart, xEnd, yEnd):
    return (round(xEnd - xStart, 1), round(yEnd - yStart, 1))


def setCommonStatus(lines, attr, rank=1):
    values = [l[attr] for l in lines if l.get(attr) is not None]
    counter = Counter(values)
    return counter.most_common(rank)


def setCommonFontSize(lines):
    fs, _ = setCommonStatus(lines, "FontSize", 1)[0]
    return round(fs, 1)

def setCommonFontSizes(lines):
    """
    Trả về tất cả FontSize và số lượng của chúng, sắp xếp theo tần suất giảm dần.
    """
    values = [l["FontSize"] for l in lines if l.get("FontSize") is not None]
    counter = Counter(values)
    results = []
    for fs, count in counter.most_common():  # trả về tất cả
        results.append({"FontSize": round(fs, 1), "Count": count})
    return results

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
    pageGeneralSize = baseJson["general"]["pageGeneralSize"]
    xStart, yStart, xEnd, yEnd, xMid, yMid = setPageCoords(lines, pageGeneralSize)
    regionWidth, regionHeight = setPageRegionSize(xStart, yStart, xEnd, yEnd)
    commonFontSizes = setCommonFontSizes(lines)
    commonFontSize = setCommonFontSize(lines)
    commonMarkers = setCommonMarkers(lines)

    new_general = {
        "pageGeneralSize": baseJson["general"]["pageGeneralSize"],
        "pageCoords": {"xStart": xStart, "yStart": yStart, "xEnd": xEnd, "yEnd": yEnd, "xMid": xMid, "yMid": yMid},
        "pageRegionWidth": regionWidth,
        "pageRegionHeight": regionHeight,
        "commonFontSize": commonFontSize,
        "commonFontSizes": commonFontSizes,
        "commonMarkers": commonMarkers
    }

    new_lines = []
    for i, line in enumerate(lines):
        lineWidth, lineHeight = setLineSize(line)
        pos = setPosition(line, lines[i - 1] if i > 0 else None,
                          lines[i + 1] if i < len(lines) - 1 else None,
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


# ===============================
# 4. Các hàm del/reset
# ===============================
def delStatus(jsonDict, deleteList):
    for line in jsonDict["lines"]:
        for attr in deleteList:
            if attr in line:
                del line[attr]
    return jsonDict


def resetPosition(jsonDict):
    lines = jsonDict.get("lines", [])
    for i, line in enumerate(lines):
        pos = line.get("Position", {})

        if "Top" in pos and pos["Top"] < 0:
            top_candidates = []
            if i > 0:
                prev_top = lines[i - 1].get("Position", {}).get("Top")
                if prev_top is not None:
                    top_candidates.append(prev_top)
            if i < len(lines) - 1:
                next_top = lines[i + 1].get("Position", {}).get("Top")
                if next_top is not None:
                    top_candidates.append(next_top)
            if top_candidates:
                pos["Top"] = min(top_candidates)

        if "Bot" in pos and pos["Bot"] < 0:
            bot_candidates = []
            if i > 0:
                prev_bot = lines[i - 1].get("Position", {}).get("Bot")
                if prev_bot is not None:
                    bot_candidates.append(prev_bot)
            if i < len(lines) - 1:
                next_bot = lines[i + 1].get("Position", {}).get("Bot")
                if next_bot is not None:
                    bot_candidates.append(next_bot)
            if bot_candidates:
                pos["Bot"] = min(bot_candidates)
        line["Position"] = pos
    return jsonDict


# ===============================
# 5. Hàm chính extractData
# ===============================
def extractData(path,
                exceptions_path="../tests/ex.exceptions.json",
                markers_path="../tests/ex.markers.json",
                status_path="../tests/ex.status.json"):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File {path} không tồn tại")
    pdf_path = path
    temp_file = None

    try:
        exceptions = load_exceptions(exceptions_path)
        patterns = load_patterns(markers_path, status_path)

        baseJson = getTextStatus(pdf_path, exceptions, patterns)
        baseJson = getTextStatus(pdf_path, exceptions, patterns)

        baseJson["lines"] = normalizeRomanMarkers(baseJson["lines"])
        modifiedJson = setTextStatus(baseJson)
        cleanJson = resetPosition(modifiedJson)
        finalJson = delStatus(cleanJson, ["Coords"])
        return finalJson
    finally:
        if temp_file:
            os.remove(temp_file.name)
