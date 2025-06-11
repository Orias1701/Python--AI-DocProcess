from difflib import SequenceMatcher
import re
import json
from collections import Counter
import fitz
from docx2pdf import convert
import tempfile
import os
import math
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
        
        title_keywords = '|'.join(re.escape(k[0].upper() + k[1:].lower()) for k in keywords)
        upper_keywords = '|'.join(re.escape(k.upper()) for k in keywords)
        all_keywords = f"{title_keywords}|{upper_keywords}"

        compiled_markers = []
        for item in markers_data.get("markers", []):
            pattern_str = item["pattern"].replace("{keywords}", all_keywords)
            try:
                compiled_pattern = re.compile(pattern_str)
            except re.error as e:
                print(f"LỖI pattern: {pattern_str}\nError: {e}")
                continue
            compiled_markers.append({
                "pattern": compiled_pattern,
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
            },
            "keywords_set": set(k.lower() for k in keywords)
        }
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        raise Exception(f"Error loading patterns: {e}")

def sentence_end(text, patterns):
    valid_end = patterns["sentence_ends"]["punctuation"].search(text[-1])
    valid_brackets = any(text.startswith(pair[0]) and text.endswith(pair[1]) for pair in patterns["sentence_ends"]["valid_brackets"])
    return bool(valid_end or valid_brackets)

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
    if not marker_text:
        return None
    
    formatted = marker_text
    formatted = re.sub(r'\b[0-9]+\b', '123', formatted)
    formatted = re.sub(r'\b[IVXLC]+\b', 'XVI', formatted)
    parts = re.split(r'(\W+)', formatted)
    formatted_parts = []
    
    for part in parts:
        if re.match(r'\W+', part):
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
    
    formatted = ''.join(formatted_parts)
    
    return formatted

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

def get_word_style_and_content(text, spans, exceptions, is_pdf, x1, x2):
    words = text.strip().split()
    if not words:
        return {"content": "", "style": "000", "case_style": "mixed", "width": 0}, {"content": "", "style": "000", "case_style": "mixed"}
    
    first_word = words[0].rstrip(".")
    last_word = words[-1].rstrip(".,!?")
    first_style, last_style = "000", "000"
    first_content, last_content = first_word, last_word
    first_case, last_case = get_case_style(first_word, exceptions), get_case_style(last_word, exceptions)
    first_width = 0
    
    if is_pdf and spans:
        for span in spans:
            span_text = span["text"].strip()
            normalized_span = span_text.replace("\xa0", " ").strip()
            normalized_first = first_word.replace("\xa0", " ").strip()
            normalized_last = last_word.replace("\xa0", " ").strip()
            
            bold = bool(span["flags"] & 16)
            italic = bool(span["flags"] & 2)
            underline = bool(span["flags"] & 8)
            style = f"{int(bold)}{int(italic)}{int(underline)}"
            span_x0, _, span_x1, _ = span["bbox"]
            
            if normalized_span == normalized_first or normalized_span.startswith(normalized_first + " "):
                first_style = style
                first_content = normalized_span if normalized_span == normalized_first else normalized_first
                first_width = round(span_x1 - span_x0, 1)
                if normalized_span != normalized_first:
                    char_count = len(normalized_span)
                    first_word_len = len(normalized_first)
                    first_width = round(first_width * (first_word_len / char_count), 1) if char_count > 0 else 0
            if normalized_span == normalized_last or normalized_span.endswith(" " + normalized_last):
                last_style = style
                last_content = normalized_span if normalized_span == normalized_last else normalized_last
    
    return (
        {"content": first_content, "style": first_style, "case_style": first_case, "width": first_width},
        {"content": last_content, "style": last_style, "case_style": last_case}
    )

def get_line_coordinates(text, spans, is_pdf):
    # if not text.strip() or not spans or not is_pdf:
    #     return {"x1": 0, "x2": 0, "y1": 0, "y2": 0}
    
    x1, x2, y1, y2 = None, None, None, None
    for span in spans:
        span_text = span["text"].strip()
        normalized_span = span_text.replace("\xa0", " ").strip()
        if not normalized_span:
            continue
        span_x0, span_y0, span_x1, span_y1 = span["bbox"]
        
        if x1 is None and len(normalized_span) > 0:
            x1 = span_x0
            y1 = span_y0
                
        if len(normalized_span) > 0:
            x2 = span_x1
            y2 = span_y1
        
        if x1 is not None and x2 is not None:
            break

    return {
        "x1": round(x1, 1) if x1 is not None else 0,
        "x2": round(x2, 1) if x2 is not None else 0,
        "y1": round(y1, 1) if y1 is not None else 0,
        "y2": round(y2, 1) if y2 is not None else 0
    }

def get_common_coordinate(values, threshold, fallback=None, page_width=None):
    if not values:
        return 0
    counter = Counter(values)
    total = len(values)
    common = counter.most_common(1)
    if common and common[0][1] / total > threshold:
        return common[0][0]
    if fallback is not None and page_width is not None:
        max_count = 0
        best_i = 0
        for i in range(int(page_width * 0.76), int(page_width) + 1, int(page_width * 0.06)):
            count = sum(1 for x in values if i - page_width * 0.06 < x <= i)
            if count > max_count:
                max_count = count
                best_i = i
        if max_count > 0:
            return max(x for x in values if x < best_i) if any(x < best_i for x in values) else 0
    return 0

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def get_bbox_by_chars(page, target_text):
    chars = []
    for block in page.get_text("dict")["blocks"]:
        if "lines" in block:
            for line in block["lines"]:
                for span in line["spans"]:
                    chars.extend(span.get("chars", []))
    # Ghép toàn bộ text lại và chuẩn hóa
    full_text = "".join(c["c"] for c in chars)
    # Chuẩn hóa: thay \n, \r, tab, nhiều space thành 1 space
    import re
    norm_full_text = re.sub(r'[\n\r\t]+', ' ', full_text)
    norm_full_text = re.sub(r' +', ' ', norm_full_text).strip()
    norm_target = re.sub(r'[\n\r\t]+', ' ', target_text)
    norm_target = re.sub(r' +', ' ', norm_target).strip()
    idx = norm_full_text.find(norm_target)
    if idx != -1:
        # Tìm vị trí ký tự đầu/cuối thực sự trong mảng chars
        # Cần ánh xạ lại vì đã chuẩn hóa, nên dùng phương pháp so khớp từng phần
        raw_idx = None
        raw_end = None
        for i in range(len(full_text)):
            sub = full_text[i:i+len(target_text)]
            sub_norm = re.sub(r'[\n\r\t]+', ' ', sub)
            sub_norm = re.sub(r' +', ' ', sub_norm).strip()
            if sub_norm == norm_target:
                raw_idx = i
                raw_end = i + len(target_text) - 1
                break
        if raw_idx is not None:
            char_start = chars[raw_idx]
            char_end = chars[raw_end]
            x1, y1 = char_start["bbox"][0], char_start["bbox"][1]
            x2, y2 = char_end["bbox"][2], char_end["bbox"][3]
            return x1, y1, x2, y2
    return 0, 0, 0, 0

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
        all_x1, all_y1, all_x2, all_y2 = [], [], [], []
        first_line_y1_per_page = {}
        last_line_y2_per_page = {}

        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc):
            page_width = page.rect.width
            page_height = page.rect.height
            blocks = sorted(page.get_text("blocks"), key=lambda b: (b[1], b[0]))
            if not blocks:
                continue

            text_dict = page.get_text("dict")
            line_index_in_page = 0

            for block in blocks:
                for line in block[4].split("\n"):
                    cleaned_text = " ".join(line.strip().split())
                    if not cleaned_text:
                        continue

                    spans = []
                    bold, italic, underline = False, False, False
                    found = False

                    # 1. Ưu tiên khớp tuyệt đối
                    for b in text_dict["blocks"]:
                        if "lines" in b:
                            for l in b["lines"]:
                                line_text = "".join(span["text"] for span in l["spans"]).strip()
                                if cleaned_text == line_text:
                                    spans = l["spans"]
                                    bold = all(span["flags"] & 16 for span in l["spans"])
                                    italic = all(span["flags"] & 2 for span in l["spans"])
                                    underline = all(span["flags"] & 8 for span in l["spans"])
                                    found = True
                                    break
                        if found:
                            break

                    # 2. Nếu không được, thử fuzzy matching
                    if not spans:
                        best_spans = []
                        best_score = 0.0
                        for b in text_dict["blocks"]:
                            if "lines" in b:
                                for l in b["lines"]:
                                    line_text = "".join(span["text"] for span in l["spans"]).strip()
                                    score = similar(cleaned_text, line_text)
                                    if score > best_score:
                                        best_score = score
                                        best_spans = l["spans"]
                        if best_score > 0.8:  # Ngưỡng có thể điều chỉnh
                            spans = best_spans
                            bold = all(span["flags"] & 16 for span in spans)
                            italic = all(span["flags"] & 2 for span in spans)
                            underline = all(span["flags"] & 8 for span in spans)
                            found = True

                    # 3. Nếu vẫn không được, thử ghép spans liên tiếp trong block
                    if not spans:
                        for b in text_dict["blocks"]:
                            if "lines" in b:
                                for l in b["lines"]:
                                    # Duyệt từng vị trí bắt đầu
                                    for i in range(len(l["spans"])):
                                        concat = ""
                                        temp_spans = []
                                        for j in range(i, len(l["spans"])):
                                            concat += l["spans"][j]["text"]
                                            temp_spans.append(l["spans"][j])
                                            if similar(cleaned_text, concat.strip()) > 0.8:
                                                spans = temp_spans
                                                bold = all(span["flags"] & 16 for span in spans)
                                                italic = all(span["flags"] & 2 for span in spans)
                                                underline = all(span["flags"] & 8 for span in spans)
                                                found = True
                                                break
                                        if found:
                                            break
                                    if found:
                                        break
                            if found:
                                break

                    if not spans:
                        print(f"Không tìm được spans cho dòng: {cleaned_text}")
                        x1, y1, x2, y2 = get_bbox_by_chars(page, cleaned_text)
                        # Nếu lấy được bbox, cập nhật vào kết quả
                        if x1 != 0 or x2 != 0 or y1 != 0 or y2 != 0:
                            coords = {"x1": x1, "x2": x2, "y1": y1, "y2": y2}
                        else:
                            coords = get_line_coordinates(cleaned_text, spans, is_pdf=True)
                    else:
                        coords = get_line_coordinates(cleaned_text, spans, is_pdf=True)

                    x1, x2, y1, y2 = coords["x1"], coords["x2"], coords["y1"], coords["y2"]

                    font_size = round(spans[0]["size"], 1) if spans else 12
                    style = f"{int(bold)}{int(italic)}{int(underline)}"
                    coords = get_line_coordinates(cleaned_text, spans, is_pdf=True)
                    x1, x2, y1, y2 = coords["x1"], coords["x2"], coords["y1"], coords["y2"]
                    
                    all_x1.append(x1)
                    all_y1.append(y1)
                    all_x2.append(x2)
                    all_y2.append(y2)

                    if line_index_in_page == 0:
                        first_line_y1_per_page[page_num] = y1
                    last_line_y2_per_page[page_num] = y2

                    marker_info = extract_marker(cleaned_text, patterns)
                    marker_text = marker_info["marker_text"]
                    marker_format = format_marker(marker_text, patterns)
                    first_word, last_word = get_word_style_and_content(cleaned_text, spans, exceptions, is_pdf=True, x1=x1, x2=x2)

                    lines_data.append({
                        "Line": len(lines_data) + 1,
                        "Text": cleaned_text,
                        "MarkerText": marker_text,
                        "MarkerFormat": marker_format,
                        "CaseStyle": get_case_style(cleaned_text, exceptions),
                        "BracketStatus": bracket_status(cleaned_text, patterns),
                        "Style": style,
                        "FirstWord": first_word,
                        "LastWord": last_word,
                        "FontSize": font_size,
                        "LineHeight": round(y2 - y1, 1),
                        "LineWidth": round(x2 - x1, 1),
                        "MarginLeft": 0,  # Placeholder
                        "ExtraSpace": 0,   # Placeholder
                        "X1": x1,
                        "X2": x2,
                        "Y1": y1,
                        "Y2": y2
                    })
                    line_index_in_page += 1

        # Calculate region coordinates
        total_lines = len(lines_data)
        total_pages = len(doc)
        
        # Xstart: Min of common X1 (frequency > 5% of texts)
        x1_counter = Counter(all_x1)
        xstart = get_common_coordinate([x for x, count in x1_counter.items() if count / total_lines > 0.05], threshold=0.05)

        # Ystart: Min of common Y1 (frequency > 15% of pages) of first lines per page
        y1_counter = Counter(first_line_y1_per_page.values())
        ystart = get_common_coordinate([y for y, count in y1_counter.items() if count / total_pages > 0.15], threshold=0.15)

        # Xend: Max of common X2 (frequency > 5% of texts) or fallback method
        x2_counter = Counter(all_x2)
        xend = get_common_coordinate([x for x, count in x2_counter.items() if count / total_lines > 0.05], threshold=0.05, 
                                     fallback=True, page_width=doc[0].rect.width if doc else 0)
        
        # Yend: Min of Y2 of last lines per page
        yend = max(last_line_y2_per_page.values()) if last_line_y2_per_page else 0

        region_width = round(xend - xstart, 1) if xstart and xend else 0
        region_height = round(yend - ystart, 1) if ystart and yend else 0

        # Update line metrics
        for line in lines_data:
            if line["X2"] == 0:
                print(f"Warning: X2 is 0 for text: {line['Text']}")
            line["MarginLeft"] = round(line["X1"] - xstart, 1) if xstart else 0
            
            line["LineWidth"] = round(line["X2"] - line["X1"], 1)
            if line["LineWidth"] < 0:
                print(f"Warning: Negative LineWidth ({line['LineWidth']}) for text: {line['Text']}")
                line["LineWidth"] = 0
            
            line["ExtraSpace"] = round(xend - line["X2"], 1) if xend else 0
            if line["ExtraSpace"] < 0:
                line["ExtraSpace"] = 0
            
            if line["FirstWord"]["width"] > line["LineWidth"]:
                print(f"Warning: FirstWordWidth ({line['FirstWord']['width']}) exceeds LineWidth ({line['LineWidth']}) for text: {line['Text']}")
                line["FirstWord"]["width"] = line["LineWidth"]

        common_font_size = round(Counter([l["FontSize"] for l in lines_data]).most_common(1)[0][0], 1) if lines_data else 12.0
        common_line_height = round(Counter([l["LineHeight"] for l in lines_data]).most_common(1)[0][0], 1) if lines_data else 13.8

        total_lines = len(lines_data)
        marker_threshold = total_lines * 0.003
        marker_counts = Counter(l["MarkerFormat"] for l in lines_data if l["MarkerFormat"] is not None)
        common_markers = [marker for marker, count in marker_counts.items() if count > marker_threshold]

        general = {
            "page_height": round(doc[0].rect.height, 1) if doc else 0,
            "page_width": round(doc[0].rect.width, 1) if doc else 0,
            "xstart": xstart,
            "ystart": ystart,
            "xend": xend,
            "yend": yend,
            "region_height": region_height,
            "region_width": region_width,
            "common_font_size": common_font_size,
            "common_line_height": common_line_height,
            "common_line_width": round(Counter([l["LineWidth"] for l in lines_data]).most_common(1)[0][0], 1) if lines_data else 0,
            "common_markers": common_markers
        }

        def is_roman(s):
            return bool(re.fullmatch(r'[IVXLC]+', s))

        def roman_to_int(s):
            roman_numerals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}
            result = 0
            prev = 0
            for c in reversed(s):
                val = roman_numerals.get(c, 0)
                if val < prev:
                    result -= val
                else:
                    result += val
                    prev = val
            return result

        from collections import defaultdict
        format_groups = defaultdict(list)
        for idx, line in enumerate(lines_data):
            fmt = line.get("MarkerFormat")
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
            else:
                roman_numbers = [roman_to_int(rm[1]) for rm in roman_markers]
                if sorted(roman_numbers) == list(range(min(roman_numbers), max(roman_numbers)+1)):
                    continue
                else:
                    for idx, _ in roman_markers:
                        lines_data[idx]["MarkerFormat"] = re.sub(r'\b[IVXLC]+\b', "ABC", lines_data[idx]["MarkerFormat"])

        marker_counts = Counter(l["MarkerFormat"] for l in lines_data if l["MarkerFormat"] is not None)
        general["common_markers"] = [marker for marker, count in marker_counts.items() if count > marker_threshold]

        return {"general": general, "lines": lines_data}

    finally:
        if temp_file:
            doc.close()
            os.remove(temp_file.name)