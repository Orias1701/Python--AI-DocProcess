import re
import os
import fitz
import json
from collections import Counter
from docx2pdf import convert
import tempfile

def load_exceptions(file_path="exceptions.json"):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {
                "common_words": set(data.get("common_words", [])),
                "proper_names": [item["text"] for item in data.get("proper_names", [])],
                "abbreviations": set(item["text"].lower() for item in data.get("abbreviations", []))
            }
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        raise Exception(f"Error loading exceptions: {e}")

def load_patterns(markers_path="markers.json", status_path="status.json"):
    try:
        with open(markers_path, 'r', encoding='utf-8') as f:
            markers_data = json.load(f)
        with open(status_path, 'r', encoding='utf-8') as f:
            status_data = json.load(f)
        
        keywords = markers_data.get("keywords", [])
        if not keywords:
            raise KeyError("Keywords list cannot be empty in markers.json")
            
        lower_keywords = '|'.join(re.escape(k) for k in keywords)
        title_keywords = '|'.join(re.escape(k[0].upper() + k[1:].lower()) for k in keywords)
        upper_keywords = '|'.join(re.escape(k.upper()) for k in keywords)
        all_keywords = f"({lower_keywords}|{title_keywords}|{upper_keywords})"
        
        compiled_markers = []
        for item in markers_data.get("markers", []):
            pattern_str = item["pattern"].replace("{keywords}", all_keywords)
            compiled_markers.append({
                "pattern": re.compile(pattern_str),
                "description": item.get("description", ""),
                "type": item.get("type", "")
            })
        
        return {
            "markers": compiled_markers,
            "brackets": {
                "open": re.compile(status_data["brackets"]["open"]),
                "close": re.compile(status_data["brackets"]["close"]),
                "pairs": status_data["brackets"]["pairs"]
            },
            "sentence_ends": {
                "punctuation": re.compile(status_data["sentence_ends"]["punctuation"]),
                "valid_brackets": status_data["sentence_ends"]["valid_brackets"]
            }
        }
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        raise Exception(f"Error loading patterns: {e}")

def sentence_end(text, patterns):
    valid_end = patterns["sentence_ends"]["punctuation"].search(text[-1])
    valid_brackets = any(text.startswith(pair[0]) and text.endswith(pair[1]) for pair in patterns["sentence_ends"]["valid_brackets"])
    return bool(valid_end or valid_brackets)

def markers(text, patterns):
    for marker in patterns["markers"]:
        match = marker["pattern"].match(text)
        if match:
            marker_text = match.group(0).rstrip()  # Keep original, remove trailing space
            marker_type = marker["type"]
            
            bullet = ""
            keyword = ""
            position = ""
            endmark = ""
            
            # Extract components based on marker type
            if "{bullet}" in marker_type:
                bullet = match.group(1)
                if len(match.groups()) >= 2 and match.group(2):
                    bullet += match.group(2)  # Add space if present
            
            if "{keyword}" in marker_type:
                keyword = match.group(1)  # Original keyword with case
                if "{position}" in marker_type and len(match.groups()) > 1 and match.start(2) > len(match.group(1)):
                    keyword += " "  # Add space if position follows
            
            if "{position}" in marker_type:
                pos_group = 1 if "{keyword}" not in marker_type else 2
                if len(match.groups()) >= pos_group and match.group(pos_group):
                    pos = match.group(pos_group)
                    space = ""
                    # Check for space
                    if len(match.groups()) > pos_group:
                        space = match.group(len(match.groups())) if match.group(len(match.groups())) else ""
                    elif text.startswith(match.group(0)) and len(text) > len(match.group(0)) and text[len(match.group(0))] == " ":
                        space = " "
                    if re.match(r"[0-9]+", pos):
                        position = "123"
                    elif re.match(r"[a-z]+", pos):
                        position = "abc"
                    elif re.match(r"[A-Z]+", pos):
                        position = "ABC"
                    elif re.match(r"[IVXLC]+", pos):
                        position = "XVI"
                    elif re.match(r"[0-9]+\\.([0-9]+\\.)+[0-9]*", pos):
                        position = "1.2.3"
                    elif re.match(r"[a-z]+\\.([a-z]+\\.)+[a-z]*", pos):
                        position = "a.b.c"
                    elif re.match(r"[A-Z]+\\.([A-Z]+\\.)+[A-Z]*", pos):
                        position = "A.B.C"
                    elif re.match(r"[IVXLC]+\\.([IVXLC]+\\.)+[IVXLC]*", pos):
                        position = "I.II.III"
                    position += space
            
            if "{endmark}" in marker_type:
                endmark_group = 2 if "{keyword}" not in marker_type else 3
                if len(match.groups()) >= endmark_group:
                    endmark = match.group(endmark_group) if match.group(endmark_group) else ""
            
            # Special cases (e.g., (a), "123")
            if marker_type.startswith("(") or marker_type.startswith("\"") or marker_type.startswith("'") or marker_type.startswith("{"):
                if len(match.groups()) >= 1 and match.group(1):
                    pos = match.group(1)
                    space = match.group(2) if len(match.groups()) >= 2 and match.group(2) else ""
                    if re.match(r"[0-9]+", pos):
                        position = "123"
                    elif re.match(r"[a-z]+", pos):
                        position = "abc"
                    elif re.match(r"[A-Z]+", pos):
                        position = "ABC"
                    else:
                        position = "XVI"
                    if marker_type.startswith("("):
                        endmark = ")"
                        formatted_marker = f"({position}){space}"
                        marker_text = f"({pos}){space}"
                    elif marker_type.startswith("\""):
                        endmark = "\""
                        formatted_marker = f"\"{position}\"{space}"
                        marker_text = f"\"{pos}\"{space}"
                    elif marker_type.startswith("'"):
                        endmark = "'"
                        formatted_marker = f"'{position}'{space}"
                        marker_text = f"'{pos}'{space}"
                    else:  # {XVI}
                        endmark = "}"
                        formatted_marker = f"{{{position}}}{space}"
                        marker_text = f"{{{pos}}}{space}"
            else:
                formatted_marker = f"{bullet}{keyword}{position}{endmark}"
            
            if not (bullet or keyword or position):
                continue  # Try next pattern if no valid components
            
            return {
                "has_marker": True,
                "marker_text": marker_text,
                "formatted_marker": formatted_marker
            }
    
    return {
        "has_marker": False,
        "marker_text": "none",
        "formatted_marker": "none"
    }

def bracket_status(text, patterns):
    non_marker_text = text
    for pattern in patterns["markers"]:
        match = pattern["pattern"].match(text)
        if match:
            non_marker_text = text[len(match.group(0)):]
            break
    
    open_count = sum(1 for _ in patterns["brackets"]["open"].finditer(non_marker_text))
    close_count = sum(1 for _ in patterns["brackets"]["close"].finditer(non_marker_text))
    
    if open_count == close_count and open_count > 0:
        stack = []
        for char in non_marker_text:
            if patterns["brackets"]["open"].match(char):
                stack.append(char)
            elif patterns["brackets"]["close"].match(char):
                if not stack:
                    return "both"
                last_open = stack.pop()
                if not any(last_open == pair[0] and char == pair[1] for pair in patterns["brackets"]["pairs"]):
                    return "both"
        if not stack:
            return "none"
    
    if open_count > close_count:
        return "open"
    elif close_count > open_count:
        return "close"
    elif open_count > 0 and close_count > 0:
        return "both"
    return "none"

def get_case_style(text, exceptions):
    exception_texts = exceptions["common_words"] | set(exceptions["proper_names"]) | exceptions["abbreviations"]
    words = [word for word in text.split() if word.lower() not in exception_texts and word.strip()]
    
    if not words:
        return "mixed"
    
    has_non_exception = any(word.isalpha() and word.lower() not in exception_texts for word in words)
    if not has_non_exception:
        return "mixed"
    
    is_upper = all(word.isupper() for word in words if word.isalpha() or any(c.isalpha() for c in word))
    is_title = all(word[0].isupper() and word[1:].islower() if len(word) > 1 else word[0].isupper()
                   for word in words if word.isalpha() or any(c.isalpha() for c in word))
    
    return "upper" if is_upper else "title" if is_title else "mixed"

def get_first_word_width(text, spans=None, font_size=12, is_pdf=False):
    words = text.strip().split()
    if not words:
        return 0
    first_word = words[0].rstrip(".")
    
    if is_pdf and spans:
        for span in spans:
            span_text = span["text"].strip()
            normalized_span = span_text.replace("\xa0", " ").strip()
            normalized_first_word = first_word.replace("\xa0", " ").strip()
            
            if normalized_span == normalized_first_word or normalized_span.startswith(normalized_first_word + " "):
                x0, _, x1, _ = span["bbox"]
                width = x1 - x0
                if normalized_span != normalized_first_word:
                    char_count = len(normalized_span)
                    first_word_len = len(normalized_first_word)
                    width = width * (first_word_len / char_count)
                return round(width, 1)
            elif normalized_first_word in normalized_span and normalized_span.index(normalized_first_word) == 0:
                x0, _, x1, _ = span["bbox"]
                char_count = len(normalized_span)
                first_word_len = len(normalized_first_word)
                width = (x1 - x0) * (first_word_len / char_count)
                return round(width, 1)
        print(f"Warning: No span found for first word '{first_word}' in PDF. Using default.")
    return round(len(first_word) * font_size * 0.4, 1)

def extract_and_analyze(path, exceptions_path="exceptions.json", markers_path="markers.json", status_path="status.json"):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File {path} does not exist")
    file_ext = os.path.splitext(path)[1].lower()
    if file_ext not in [".docx", ".pdf"]:
        raise ValueError("Unsupported file format. Only .docx and .pdf are supported.")

    pdf_path = path
    temp_file = None
    if file_ext == ".docx":
        temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        convert(path, temp_file.name)
        pdf_path = temp_file.name

    try:
        exceptions = load_exceptions(exceptions_path)
        patterns = load_patterns(markers_path, status_path)
        lines_data = []
        page_data = []
        line_widths = []
        all_x0, all_y0, all_x1, all_y1 = [], [], [], []

        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc):
            page_width = page.rect.width
            page_height = page.rect.height
            blocks = sorted(page.get_text("blocks"), key=lambda b: (b[1], b[0]))
            prev_bottom = None
            page_info = {"top": None, "bottoms": [], "lefts": [], "rights": [], "last_bottom": None}
            line_positions = []

            for block in blocks:
                for line in block[4].split("\n"):
                    cleaned_text = " ".join(line.strip().split())
                    if not cleaned_text:
                        continue

                    x0, y0, x1, y1 = block[:4]
                    all_x0.append(x0)
                    all_y0.append(y0)
                    all_x1.append(x1)
                    all_y1.append(y1)

                    margin_left = x0 - page.rect.x0
                    margin_right = page_width - x1
                    margin_top = y0 - page.rect.y0 if prev_bottom is None else y0 - prev_bottom
                    margin_bottom = page_height - y1

                    if prev_bottom is None:
                        page_info["top"] = y0 - page.rect.y0
                    page_info["lefts"].append(margin_left)
                    page_info["rights"].append(margin_right)
                    page_info["bottoms"].append(margin_bottom)

                    line_width = round(x1 - x0, 1)
                    line_widths.append(line_width)

                    text_dict = page.get_text("dict")
                    font_size = 12
                    line_spacing = 1.15
                    bold, italic, underline = False, False, False
                    spans = []
                    for b in text_dict["blocks"]:
                        if "lines" in b:
                            for l in b["lines"]:
                                if cleaned_text in l["spans"][0]["text"]:
                                    spans = l["spans"]
                                    font_size = l["spans"][0]["size"]
                                    line_spacing = 1.15
                                    bold = bool(l["spans"][0]["flags"] & 16)
                                    italic = bool(l["spans"][0]["flags"] & 2)
                                    underline = bool(l["spans"][0]["flags"] & 8)
                                    break
                        if spans:
                            break

                    font_size = round(font_size, 1)
                    line_height = round(line_spacing * font_size, 1)
                    margin_top = round(margin_top, 1)
                    margin_bottom = round(margin_bottom, 1)
                    margin_left = round(margin_left, 1)
                    margin_right = round(margin_right, 1)

                    first_word_width = get_first_word_width(cleaned_text, spans=spans, is_pdf=True)
                    if first_word_width > line_width:
                        print(f"Warning: FirstWordWidth ({first_word_width}) exceeds LineWidth ({line_width}) for text: {cleaned_text}")
                        first_word_width = line_width

                    marker_info = markers(cleaned_text, patterns)
                    line_positions.append({"text": cleaned_text, "top": y0, "bottom": y1})
                    lines_data.append({
                        "Line": len(lines_data) + 1,
                        "Text": cleaned_text,
                        "Marker": marker_info["formatted_marker"],
                        "MarkerText": marker_info["marker_text"],
                        "CaseStyle": get_case_style(cleaned_text, exceptions),
                        "IsBold": bold,
                        "IsItalic": italic,
                        "IsUnderline": underline,
                        "FontSize": font_size,
                        "LineHeight": line_height,
                        "MarginTop": margin_top,
                        "MarginBottom": margin_bottom,
                        "MarginLeft": margin_left,
                        "MarginRight": margin_right,
                        "BracketStatus": bracket_status(cleaned_text, patterns),
                        "FirstWordWidth": first_word_width,
                        "LineWidth": line_width
                    })
                    prev_bottom = y0
                    page_info["last_bottom"] = y1
            page_data.append(page_info)

            if line_positions:
                last_line_idx = len(lines_data) - 1
                lines_data[last_line_idx]["MarginBottom"] = round(page_height - page_info["last_bottom"], 0)

        region_x0 = min(all_x0) if all_x0 else 0
        region_y0 = min(all_y0) if all_y0 else 0
        region_x1 = max(all_x1) if all_x1 else 0
        region_y1 = max(all_y1) if all_y1 else 0
        region_width = round(region_x1 - region_x0, 1) if all_x0 and all_x1 else 0
        region_height = round(region_y1 - region_y0, 1) if all_y0 and all_y1 else 0

        left_margins = [p["lefts"] for p in page_data if p["lefts"]]
        right_margins = [p["rights"] for p in page_data if p["rights"]]
        top_margins = [p["top"] for p in page_data if p["top"] is not None]
        bottom_margins = [p["bottoms"][-1] for p in page_data if p["bottoms"]]

        left_align = round(min([min(m) for m in left_margins]) if left_margins else 0, 1)
        right_align = round(min([min(m) for m in right_margins]) if right_margins else 0, 1)
        top_align = round(min(top_margins) if top_margins else 0, 1)
        bottom_align = round(min(bottom_margins) if bottom_margins else 0, 1)

        common_font_size = round(Counter([l["FontSize"] for l in lines_data]).most_common(1)[0][0], 1) if lines_data else 12.0
        common_line_height = round(Counter([l["LineHeight"] for l in lines_data]).most_common(1)[0][0], 1) if lines_data else 13.8

        total_lines = len(lines_data)
        marker_threshold = total_lines * 0.01
        marker_counts = Counter(l["Marker"] for l in lines_data if l["Marker"] != "none")
        common_markers = [marker for marker, count in marker_counts.items() if count > marker_threshold]

        general = {
            "page_height": round(page_height, 1),
            "page_width": round(page_width, 1),
            "region_height": region_height,
            "region_width": region_width,
            "region_start": [round(region_x0, 1), round(region_y0, 1)],
            "region_end": [round(region_x1, 1), round(region_y1, 1)],
            "region_align": {
                "left": left_align,
                "right": right_align,
                "top": top_align,
                "bottom": bottom_align
            },
            "common_font_size": common_font_size,
            "common_line_height": common_line_height,
            "common_markers": common_markers,
            "common_line_width": round(Counter(line_widths).most_common(1)[0][0], 1) if line_widths else 0
        }

        for line in lines_data:
            line["ExtraSpace"] = round(general["common_line_width"] - line["LineWidth"], 1) if general["common_line_width"] > 0 else 0

        return {"general": general, "lines": lines_data}

    finally:
        if temp_file:
            doc.close()
            os.remove(temp_file.name)