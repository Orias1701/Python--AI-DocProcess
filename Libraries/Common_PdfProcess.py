from . import Common_MyUtils as MyUtils

# ===============================
# 1. General
# ===============================

def fontFlags(span):
    """Trả về tuple booleans (bold, italic, underline) từ span.flags"""
    flags = span.get("flags", 0)
    b = bool(flags & 16)
    i = bool(flags & 2)
    u = bool(flags & 8)
    return b, i, u

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
    
def setPosition(line, prev_line, next_line, xStart, xEnd, xMid):
    left = round(line["Coords"]["X0"] - xStart, 1)
    right = round(xEnd - line["Coords"]["X1"], 1)
    mid = round(line["Coords"]["XM"] - xMid, 1)
    top = round(line["Coords"]["Y1"] - prev_line["Coords"]["Y1"], 1) if prev_line else 0
    bot = round(next_line["Coords"]["Y1"] - line["Coords"]["Y1"], 1) if next_line else 0
    return (left, right, mid, top, bot)


# ===============================
# 2. Words
# ===============================

def extractWords(line):
    """Trả về list [(word, span)] theo thứ tự trong line; giữ nguyên dấu câu."""
    spans = line.get("spans", [])
    full_text = line.get("text", "")
    if not spans or not full_text.strip():
        return []

    # chỉ giữ spans có chữ thật
    valid_spans = [s for s in spans if s.get("text", "").strip()]
    if not valid_spans:
        valid_spans = spans

    words = []
    for s in valid_spans:
        for raw in s.get("text", "").split():
            words.append((raw, s))
    return words

def getWordText(line, index: int):
    """Lấy Text của từ tại vị trí index (hỗ trợ index âm)."""
    words = extractWords(line)
    if -len(words) <= index < len(words):
        return words[index][0]
    return ""

def getWordFontSize(line, index: int):
    """Lấy FontSize của từ tại vị trí index."""
    words = extractWords(line)
    if -len(words) <= index < len(words):
        _, span = words[index]
        return round(span.get("size", 12.0), 1)
    return 0.0

def getWordCoord(line, index: int):
    """Lấy tọa độ (x0, x1, xm, y0, y1) của từ tại vị trí index (dựa bbox của span chứa từ)."""
    words = extractWords(line)
    if -len(words) <= index < len(words):
        _, span = words[index]
        x0, y0, x1, y1 = span["bbox"]
        x0, y0, x1, y1 = round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)
        return (x0, x1, y0, y1)
    return (0, 0, 0, 0)


# ===============================
# 3. Lines
# ===============================

def getLineFontSize(line):
    """FontSize của line = mean FontSize các từ (làm tròn 0.5)."""
    words = extractWords(line)
    if not words:
        return 12.0
    sizes = [span.get("size", 12.0) for _, span in words]
    avg = sum(sizes) / len(sizes)
    return round(avg * 2) / 2

def getLineCoord(line):
    """
    Coord của line:
      - x0 = x0 của từ đầu tiên
      - x1 = x1 của từ cuối cùng
      - y0 = min(y0) các từ
      - y1 = max(y1) các từ
      - xm = (x0 + x1) / 2
    """
    words = extractWords(line)
    if not words:
        return (0, 0, 0, 0, 0)

    coords = []
    for _, span in words:
        x0, y0, x1, y1 = span["bbox"]
        coords.append((round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)))

    x0 = coords[0][0]
    x1 = coords[-1][2]
    y0 = min(c[1] for c in coords)
    y1 = max(c[3] for c in coords)
    xm = round((x0 + x1) / 2, 1)
    return (x0, x1, xm, y0, y1)

def setLineSize(line):
    x0, x1, y0, y1 = line["Coords"]["X0"], line["Coords"]["X1"], line["Coords"]["Y0"], line["Coords"]["Y1"]
    return (round(x1 - x0, 1), round(y1 - y0, 1))


# ===============================
# 4. Page
# ===============================

def setPageCoords(lines, pageGeneralSize):
    x0s = [round(l["Coords"]["X0"], 1) for l in lines]
    x1s = [round(l["Coords"]["X1"], 1) for l in lines]
    y0s = [round(l["Coords"]["Y0"], 1) for l in lines]
    y1s = [round(l["Coords"]["Y1"], 1) for l in lines]

    xStart = MyUtils.most_common(x0s)
    page_width = pageGeneralSize[1]
    threshold = page_width * 0.75
    x1_candidates = [x for x in x1s if x >= threshold]
    xEnd = MyUtils.most_common(x1_candidates) if x1_candidates else max(x1s)

    yStart = min(y0s)
    yEnd = max(y1s)
    xMid = round((xStart + xEnd) / 2, 1)
    yMid = round((yStart + yEnd) / 2, 1)

    return (xStart, yStart, xEnd, yEnd, xMid, yMid)

def setPageRegionSize(xStart, yStart, xEnd, yEnd):
    return (round(xEnd - xStart, 1), round(yEnd - yStart, 1))