import re
import json
from collections import Counter
import fitz
from docx2pdf import convert
import tempfile
import os

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
        
        # Sửa lại all_keywords, bỏ dấu ) thừa
        title_keywords = '|'.join(re.escape(k[0].upper() + k[1:].lower()) for k in keywords)
        upper_keywords = '|'.join(re.escape(k.upper()) for k in keywords)
        all_keywords = f"{title_keywords}|{upper_keywords}"

        compiled_markers = []
        for item in markers_data.get("markers", []):
            pattern_str = item["pattern"].replace("{keywords}", all_keywords)
            # print("Pattern thực tế:", pattern_str)  # In ra pattern thực tế
            try:
                compiled_pattern = re.compile(pattern_str)
            except re.error as e:
                print(f"LỖI pattern: {pattern_str}\nError: {e}")
                continue  # Bỏ qua pattern lỗi
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
    """
    Extracts marker text from the input string using optimized logic.
    Args:
        text (str): Input text to analyze.
        patterns (dict): Dictionary containing compiled regex patterns from markers.json.
    Returns:
        dict: Dictionary with 'marker_text' (str).
    """
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
    Formats the marker text according to specified rules by analyzing content within MarkerText.
    Args:
        marker_text (str): The extracted marker text.
        patterns (dict): Dictionary containing keywords set for checking.
    Returns:
        str: Formatted marker text or None if marker_text is None.
    """
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
        line_widths = []
        all_x0, all_y0, all_x1, all_y1 = [], [], [], []

        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc):
            page_width = page.rect.width
            page_height = page.rect.height
            blocks = sorted(page.get_text("blocks"), key=lambda b: (b[1], b[0]))

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

                    first_word_width = get_first_word_width(cleaned_text, spans=spans, is_pdf=True)
                    if first_word_width > line_width:
                        print(f"Warning: FirstWordWidth ({first_word_width}) exceeds LineWidth ({line_width}) for text: {cleaned_text}")
                        first_word_width = line_width

                    marker_info = extract_marker(cleaned_text, patterns)
                    marker_text = marker_info["marker_text"]
                    marker_format = format_marker(marker_text, patterns)
                    lines_data.append({
                        "Line": len(lines_data) + 1,
                        "Text": cleaned_text,
                        "MarkerText": marker_text,
                        "MarkerFormat": marker_format,
                        "CaseStyle": get_case_style(cleaned_text, exceptions),
                        "BracketStatus": bracket_status(cleaned_text, patterns),
                        "IsBold": bold,
                        "IsItalic": italic,
                        "IsUnderline": underline,
                        "FontSize": font_size,
                        "LineHeight": line_height,
                        "LineWidth": line_width,
                        "FirstWordWidth": first_word_width
                    })

        region_x0 = min(all_x0) if all_x0 else 0
        region_y0 = min(all_y0) if all_y0 else 0
        region_x1 = max(all_x1) if all_x1 else 0
        region_y1 = max(all_y1) if all_y1 else 0
        region_width = round(region_x1 - region_x0, 1) if all_x0 and all_x1 else 0
        region_height = round(region_y1 - region_y0, 1) if all_y0 and all_y1 else 0

        common_font_size = round(Counter([l["FontSize"] for l in lines_data]).most_common(1)[0][0], 1) if lines_data else 12.0
        common_line_height = round(Counter([l["LineHeight"] for l in lines_data]).most_common(1)[0][0], 1) if lines_data else 13.8

        total_lines = len(lines_data)
        marker_threshold = total_lines * 0.003
        marker_counts = Counter(l["MarkerFormat"] for l in lines_data if l["MarkerFormat"] is not None)
        common_markers = [marker for marker, count in marker_counts.items() if count > marker_threshold]

        general = {
            "page_height": round(page_height, 1),
            "page_width": round(page_width, 1),
            "region_height": region_height,
            "region_width": region_width,
            "common_font_size": common_font_size,
            "common_line_height": common_line_height,
            "common_line_width": round(Counter(line_widths).most_common(1)[0][0], 1) if line_widths else 0,
            "common_markers": common_markers
        }

        for line in lines_data:
            line["ExtraSpace"] = round(general["common_line_width"] - line["LineWidth"], 1) if general["common_line_width"] > 0 else 0

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

        # Gom nhóm các phần tử theo MarkerFormat
        from collections import defaultdict
        format_groups = defaultdict(list)
        for idx, line in enumerate(lines_data):
            fmt = line.get("MarkerFormat")
            marker = line.get("MarkerText")
            if fmt and marker:
                format_groups[fmt].append((idx, marker))

        # Xét từng nhóm format
        for fmt, group in format_groups.items():
            # Lấy danh sách các marker là 1 chuỗi La Mã
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

        # Cập nhật lại common_markers sau khi xử lý La Mã
        marker_counts = Counter(l["MarkerFormat"] for l in lines_data if l["MarkerFormat"] is not None)
        general["common_markers"] = [marker for marker, count in marker_counts.items() if count > marker_threshold]

        return {"general": general, "lines": lines_data}

    finally:
        if temp_file:
            doc.close()
            os.remove(temp_file.name)