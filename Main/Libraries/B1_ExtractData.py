import re
import os
import json
import fitz
from collections import Counter, defaultdict
from . import A3_TextProcess as TP
from . import A4_PdfProcess as PP

# ===============================
# 1. Utils
# ===============================

def loadHardcodes(file_path, wanted=None):
    """
    Load dữ liệu JSON theo format đồng bộ:
      {
        "type": "...",
        "items": [
          {"key": "...", "values": ...}, ...
        ]
      }
    Returns: dict: {key: values}
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "items" not in data:
        raise ValueError(f"File {file_path} không đúng format đồng bộ")
    
    result = {}
    for item in data["items"]:
        key = item["key"]
        if wanted and key not in wanted:
            continue
        result[key] = item["values"]

    return result

# ===== Hàm tự động thu thập tên riêng =====
def collect_proper_names(lines, min_count=10):
    title_words = []

    for line in lines:
        text = line.get("Text", "")
        words = re.findall(r"[A-Za-zÀ-ỹĐđ0-9]+", text)
        if not words:
            continue

        # Bỏ qua từ đầu tiên
        for w in words[1:]:
            if w.istitle():
                clean_w = TP.normalize_word(w)
                if clean_w:
                    title_words.append(clean_w)

    counter = Counter(title_words)
    proper_names = {TP.normalize_word(w) for w, cnt in counter.items() if cnt >= min_count}
    print(proper_names)
    return proper_names


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
    Chuẩn hoá MarkerText
    """
    if not marker_text:
        return None

    formatted = marker_text
    formatted = re.sub(r'\b[0-9]+\b', '123', formatted)
    formatted = re.sub(r'\b[IVXLC]+\b', 'XVI', formatted)

    parts = re.split(r'(\W+)', formatted)
    formatted_parts = []
    for part in parts:
        if re.match(r'(\W+)', part):
            formatted_parts.append(part)
            continue
        if part.lower() in patterns["keywords_set"]:
            formatted_parts.append(part)
        elif re.match(r'^[a-z]$', part) or re.match(r'^[a-zđêôơư]$', part):
            formatted_parts.append('abc')
        elif re.match(r'^[A-Z]$', part) or re.match(r'^[A-ZĐÊÔƠƯ]$', part):
            formatted_parts.append('ABC')
        else:
            formatted_parts.append(part)
    return ''.join(formatted_parts)

# ===== Hàm chuẩn hoá số La Mã =====
def normalizeRomans(lines, mode="marker", replace_with="ABC"):
    format_groups = defaultdict(list)
    for idx, line in enumerate(lines):
        fmt = line.get("MarkerType")
        marker = line.get("MarkerText")
        if fmt and marker:
            format_groups[fmt].append((idx, marker))

    # --- kiểm tra MarkerType ---
    if mode == "marker":
        for fmt, group in format_groups.items():
            roman_markers = []
            for idx, marker in group:
                m = re.search(r'\b([IVXLC]+)\b', marker)
                if m and TP.is_roman(m.group(1)):
                    roman_markers.append((idx, m.group(1)))
                else:
                    break

            if roman_markers:
                roman_numbers = [TP.roman_to_int(rm[1]) for rm in roman_markers]
                expected = list(range(min(roman_numbers), max(roman_numbers) + 1))
                if sorted(roman_numbers) != expected:
                    for idx, _ in roman_markers:
                        lines[idx]["MarkerType"] = re.sub(r'\b[IVXLC]+\b', replace_with, lines[idx]["MarkerType"])

    # --- Chuẩn hoá toàn bộ Text/MarkerText ---
    elif mode == "text":
        for line in lines:
            for key in ["Text", "MarkerText", "MarkerType"]:
                if line.get(key):
                    line[key] = re.sub(r'\b[IVXLC]+\b', replace_with, line[key])

    return lines

# ===============================
# 2. Word-level functions (mới)
# ===============================

def caseStyle(word_text: str) -> int:
    """CaseStyle cho từ: 3000 (UPPER), 2000 (Title), 1000 (khác)"""
    clean = re.sub(r'[^A-Za-zÀ-ỹà-ỹ0-9]', '', word_text)
    if clean and clean.isupper():
        return 3000
    if clean and clean.istitle():
        return 2000
    return 1000

def buildStyle(word_text, span):
    """Style gộp = CaseStyle + FontStyle (100,10,1)"""
    cs = caseStyle(word_text)
    b, i, u = PP.fontFlags(span)
    fs = (100 if b else 0) + (10 if i else 0) + (1 if u else 0)
    return cs + fs

def getWordStyle(line, index: int):
    """Lấy Style của từ tại vị trí index."""
    words = PP.extractWords(line)
    if -len(words) <= index < len(words):
        word, span = words[index]
        return buildStyle(word, span)
    return 0

# ===============================
# 3. Line-level functions (mới)
# ===============================

def getPageGeneralSize(page):
    """[height, width] của trang"""
    return [round(page.rect.height, 1), round(page.rect.width, 1)]

def getLineText(line):
    """Text đầy đủ của line"""
    return line.get("text", "")

def getLineStyle(line, exceptions=None):
    """
    Style của line = CaseStyle (min trên từ hợp lệ) + FontStyle (AND spans).
    """
    words = line.get("words", [])
    spans = line.get("spans", [])

    # Gom exceptions
    exception_texts = set()
    if exceptions:
        exception_texts = (
            set(exceptions.get("common_words", [])) |
            set(exceptions.get("proper_names", [])) |
            set(exceptions.get("abbreviations", []))
        )

    # ===== CaseStyle =====
    cs_values = []
    for w, _ in words:
        clean_w = TP.normalize_word(w)
        if not clean_w:
            continue
        if clean_w in exception_texts or TP.is_abbreviation(clean_w):
            continue
        cs_values.append(caseStyle(clean_w))

    cs_line = min(cs_values) if cs_values else 1000

    # ===== FontStyle =====
    if spans:
        bold_all = italic_all = underline_all = True
        for s in spans:
            b, i, u = PP.fontFlags(s)
            bold_all &= b
            italic_all &= i
            underline_all &= u
        fs_line = (100 if bold_all else 0) + (10 if italic_all else 0) + (1 if underline_all else 0)
    else:
        fs_line = 0

    return cs_line + fs_line

# ===============================
# 4. Compatibility wrappers
# ===============================

def getText(line):
    """Alias cũ: Text của line"""
    return getLineText(line)

def getCoords(line):
    """Alias cũ: Coord của line, giữ tuple (x0, x1, xm, y0, y1)"""
    return PP.getLineCoord(line)

def getFirstWord(line):
    """Giữ API cũ: trả {Text, Style, FontSize} của từ đầu"""
    return {
        "Text": PP.getWordText(line, 0),
        "Style": getWordStyle(line, 0),
        "FontSize": PP.getWordFontSize(line, 0),
    }

def getLastWord(line):
    """Giữ API cũ: trả {Text, Style, FontSize} của từ cuối"""
    return {
        "Text": PP.getWordText(line, -1),
        "Style": getWordStyle(line, -1),
        "FontSize": PP.getWordFontSize(line, -1),
    }


# ===============================
# 5. Marker / Style (line-level) giữ nguyên tinh thần cũ
# ===============================

def getMarker(text, patterns):
    info = extract_marker(text, patterns)
    marker_text = info.get("marker_text")
    marker_type = None
    if marker_text:
        # Giữ sửa lỗi xử lý dấu '+'
        marker_text_cleaned = re.sub(r'([A-Za-z0-9ĐÊÔƠƯđêôơư])\+(?=\W|$)', r'\1', marker_text)
        marker_type = format_marker(marker_text_cleaned, patterns)
    return marker_text, marker_type

def getFontSize(line):
    """
    Mean FontSize trên spans (logic cũ) — vẫn giữ cho compatibility nếu còn chỗ gọi.
    """
    spans = line.get("spans", [])
    if spans:
        valid_spans = [s for s in spans if s.get("text", "").strip()]
        if valid_spans:
            sizes = [s.get("size", 12.0) for s in valid_spans]
        else:
            sizes = [s.get("size", 12.0) for s in spans]
        avg = sum(sizes) / len(sizes)
        return round(avg * 2) / 2
    return 12.0


# ===============================
# 6. Tổng hợp toàn văn bản (giữ API cũ + dùng hàm mới bên trong)
# ===============================

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

                    # Marker
                    marker_text, marker_type = getMarker(text, patterns)

                    # Style/FontSize/Coord
                    line_obj = {"text": text, "spans": l["spans"]}
                    style = getLineStyle(line_obj)
                    fontsize = PP.getLineFontSize(line_obj)
                    x0, x1, xm, y0, y1 = PP.getLineCoord(line_obj)

                    # Words
                    words_obj = {
                        "First": getFirstWord(line_obj),
                        "Last":  getLastWord(line_obj)
                    }

                    line_dict = {
                        "Line": len(lines) + 1,
                        "Text": text,
                        "MarkerText": marker_text,
                        "MarkerType": marker_type,
                        "Style": style,
                        "FontSize": fontsize,
                        "Words": words_obj,
                        "Coords": {"X0": x0, "X1": x1, "XM": xm, "Y0": y0, "Y1": y1}
                    }
                    lines.append(line_dict)
    return {"general": general, "lines": lines}


# ===============================
# 7. Các hàm set*
# ===============================

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

def setTextStatus(baseJson):
    lines = baseJson["lines"]
    pageGeneralSize = baseJson["general"]["pageGeneralSize"]
    xStart, yStart, xEnd, yEnd, xMid, yMid = PP.setPageCoords(lines, pageGeneralSize)
    regionWidth, regionHeight = PP.setPageRegionSize(xStart, yStart, xEnd, yEnd)
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
        lineWidth, lineHeight = PP.setLineSize(line)
        pos = PP.setPosition(line, lines[i - 1] if i > 0 else None,
                          lines[i + 1] if i < len(lines) - 1 else None,
                          xStart, xEnd, xMid)
        pos_dict = {"Left": pos[0], "Right": pos[1], "Mid": pos[2], "Top": pos[3], "Bot": pos[4]}

        line_dict = {
            **line,
            "LineWidth": lineWidth,
            "LineHeight": lineHeight,
            "Position": pos_dict,
            "Align": PP.setAlign(pos_dict, regionWidth)
        }
        new_lines.append(line_dict)

    return {"general": new_general, "lines": new_lines}


# ===============================
# 8. Các hàm del/reset
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

def normalizeFinal(jsonDict):
    for line in jsonDict.get("lines", []):
        # xử lý Text và MarkerText
        if "Text" in line:
            line["Text"] = TP.strip_extra_spaces(line["Text"])
        if "MarkerText" in line and line["MarkerText"]:
            line["MarkerText"] = TP.strip_extra_spaces(line["MarkerText"])

        # xử lý word-level
        words = line.get("Words", {})
        for key in ["First", "Last"]:
            if key in words and "Text" in words[key]:
                words[key]["Text"] = TP.strip_extra_spaces(words[key]["Text"])
    return jsonDict


# ===============================
# 9. Hàm chính extractData
# ===============================

def extractData(path, exceptions_path, markers_path, status_path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File {path} không tồn tại")
    pdf_path = path
    temp_file = None

    try:
        # ===== 1. Load JSON theo format đồng bộ =====
        exceptions = loadHardcodes(
            exceptions_path,
            wanted=["common_words", "proper_names", "abbreviations"]
        )
        markers = loadHardcodes(
            markers_path,
            wanted=["keywords", "markers"]
        )
        status = loadHardcodes(status_path)

        # ===== 2. Biên dịch markers =====
        keywords = markers.get("keywords", [])
        title_keywords = '|'.join(re.escape(k[0].upper() + k[1:].lower()) for k in keywords)
        upper_keywords = '|'.join(re.escape(k.upper()) for k in keywords)
        all_keywords = f"{title_keywords}|{upper_keywords}"

        compiled_markers = []
        for item in markers.get("markers", []):
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

        patterns = {
            "markers": compiled_markers,
            "keywords_set": set(k.lower() for k in keywords)
        }

        # ===== 3. Xử lý PDF =====
        baseJson = getTextStatus(pdf_path, exceptions, patterns)
        baseJson["lines"] = normalizeRomans(baseJson["lines"])

        modifiedJson = setTextStatus(baseJson)
        cleanJson = resetPosition(modifiedJson)
        finalJson = delStatus(cleanJson, ["Coords"])
        finalJson = normalizeFinal(finalJson)

        # ===== 4. Bổ sung tên riêng động =====
        proper_names_auto = collect_proper_names(finalJson["lines"], min_count=10)

        proper_names_existing = [p["text"] if isinstance(p, dict) else str(p)
                                 for p in exceptions.get("proper_names", [])]

        exceptions["proper_names"] = list(set(proper_names_existing) | proper_names_auto)

        return finalJson

    finally:
        if temp_file:
            os.remove(temp_file.name)