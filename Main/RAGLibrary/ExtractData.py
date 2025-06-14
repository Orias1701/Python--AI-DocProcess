from difflib import SequenceMatcher
import re
import json
from collections import Counter
import fitz
from docx2pdf import convert
import tempfile
import os

# Tải dữ liệu ngoại lệ từ file JSON
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
        raise Exception(f"Lỗi khi tải ngoại lệ: {e}")

# Tải các mẫu từ các file JSON
def load_patterns(markers_path="markers.json", status_path="status.json"):
    try:
        with open(markers_path, 'r', encoding='utf-8') as f:
            markers_data = json.load(f)
        with open(status_path, 'r', encoding='utf-8') as f:
            status_data = json.load(f)
        
        keywords = markers_data.get("keywords", [])
        if not keywords:
            raise KeyError("Danh sách từ khóa không được rỗng trong markers.json")
        
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
        raise Exception(f"Lỗi khi tải mẫu: {e}")

# Kiểm tra xem một chuỗi có kết thúc câu hợp lệ không
def sentence_end(text, patterns):
    valid_end = patterns["sentence_ends"]["punctuation"].search(text[-1])
    valid_brackets = any(text.startswith(pair[0]) and text.endswith(pair[1]) for pair in patterns["sentence_ends"]["valid_brackets"])
    return bool(valid_end or valid_brackets)

# Trích xuất đánh dấu từ văn bản
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

# Định dạng đánh dấu
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

# Kiểm tra trạng thái ngoặc trong văn bản (Hoàn thiện: none - chưa hoàn thiện: Mở, Đóng, Cả hai)
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

# Xác định Case Style
def get_CaseStyle(text, exceptions):
    """Xác định kiểu chữ của văn bản dựa trên các từ không thuộc danh sách ngoại lệ."""
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

# Lấy thông tin kiểu chữ và nội dung của từ đầu tiên và cuối cùng
def get_word_style_and_content(text, spans, exceptions, is_pdf=True):
    """Trích xuất thông tin kiểu chữ và nội dung của từ đầu và cuối trong một dòng văn bản."""
    words = text.strip().split()
    if not words:
        return {"content": "", "style": "000", "CaseStyle": "mixed", "width": 0}, {"content": "", "style": "000", "CaseStyle": "mixed"}
    
    first_word = words[0].rstrip(".")
    last_word = words[-1].rstrip(".,!?")
    first_style, last_style = "000", "000"
    first_content, last_content = first_word, last_word
    first_case, last_case = get_CaseStyle(first_word, exceptions), get_CaseStyle(last_word, exceptions)
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
        {"content": first_content, "style": first_style, "CaseStyle": first_case, "width": first_width},
        {"content": last_content, "style": last_style, "CaseStyle": last_case}
    )

# Lấy tọa độ của dòng văn bản
def get_line_coordinates(spans):
    """Trích xuất tọa độ của dòng văn bản từ các thông tin spans."""
    x0, x1, y0, y1 = None, None, None, None
    for span in spans:
        span_text = span["text"].strip()
        normalized_span = span_text.replace("\xa0", " ").strip()
        if not normalized_span:
            continue
        span_x0, span_y0, span_x1, span_y1 = span["bbox"]     
        if x0 is None and len(normalized_span) > 0:
            x0 = span_x0
            y0 = span_y0           
        if len(normalized_span) > 0:
            x1 = span_x1
            y1 = span_y1     
        if x0 is not None and x1 is not None:
            break

    return {
        "x0": round(x0, 1) if x0 is not None else 0,
        "x1": round(x1, 1) if x1 is not None else 0,
        "y0": round(y0, 1) if y0 is not None else 0,
        "y1": round(y1, 1) if y1 is not None else 0
    }

# Lấy tọa độ chung dựa trên giá trị phổ biến
def get_common_coordinate(values, threshold, fallback=None, page_width=None):

    # Quy trình xử lý:
    # 1. Nếu danh sách values rỗng, hàm sẽ trả về 0.
    # 2. Sử dụng Counter để đếm số lần xuất hiện của mỗi giá trị trong danh sách.
    # 3. Xác định phần tử phổ biến nhất:
    #     - Nếu phần tử phổ biến nhất này xuất hiện với tỷ lệ (số lượng xuất hiện / tổng số phần tử) lớn hơn threshold, hàm trả về giá trị đó.
    # 4. Nếu không thoả mãn điều kiện threshold và cả fallback và page_width được cung cấp, thực hiện xử lý bổ sung:
    #     - Duyệt qua các giá trị i trong khoảng từ page_width * 0.76 đến page_width, với bước nhảy bằng page_width * 0.06.
    #     - Với mỗi i, đếm số lượng các giá trị trong values nằm trong khoảng (i - page_width * 0.06, i].
    #     - Xác định vị trí i (best_i) có số lượng giá trị cao nhất.
    #     - Nếu tồn tại giá trị nào trong values mà nhỏ hơn best_i, trả về giá trị lớn nhất trong các giá trị đó.
    # 5. Nếu không có trường hợp nào thỏa mãn, hàm trả về 0.

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

# Tính tương đồng giữa hai chuỗi
def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

# Kiểm tra số La Mã
def is_roman(s):
    return bool(re.fullmatch(r'[IVXLC]+', s))

# Chuyển sang Int
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
    
# Trích xuất và phân tích dữ liệu từ file PDF hoặc DOCX
def extract_data(path, exceptions_path="exceptions.json", markers_path="markers.json", status_path="status.json"):

    # Trích xuất và phân tích dữ liệu từ file PDF hoặc DOCX để thu thập thông tin từng dòng và tổng hợp thông tin chung của tài liệu.
    # Quá trình thực hiện của hàm:
    # 1. Kiểm tra sự tồn tại của file theo đường dẫn được cung cấp và xác định định dạng file (chỉ hỗ trợ ".docx" và ".pdf").
    # 2. Nếu file là DOCX, chuyển đổi sang PDF tạm thời để xử lý.
    # 3. Nạp các cấu hình ngoại lệ và mẫu đánh dấu từ các file JSON (exceptions, markers, status).
    # 4. Mở file PDF và duyệt qua từng trang:
    #     - Sắp xếp các khối văn bản theo vị trí.
    #     - Lấy thông tin dạng dictionary của trang để dễ so sánh và truy xuất các dòng văn bản.
    #     - Với mỗi dòng trong các khối, thực hiện:
    #       a. Làm sạch và chuẩn hóa định dạng văn bản.
    #       b. Xác định các font-style (in đậm, in nghiêng, gạch dưới) dựa trên cờ (flags) của các "span".
    #       c. Tìm kiếm chính xác hoặc bằng thuật toán so sánh chuỗi (similarity) để lấy thông tin chi tiết của dòng (vị trí, kích thước, danh sách spans).
    #       d. Trích xuất các thông tin như thông tin đánh dấu (marker), kiểu chữ (case style), trạng thái dấu ngoặc, từ đầu và cuối dòng, kích cỡ font, khoảng cách giữa các tọa độ.
    # 5. Thu thập các tọa độ quan trọng (tọa độ dòng bắt đầu, kết thúc, lề trái, chiều rộng dòng) của tất cả các dòng trên trang.
    # 6. Tính toán các số liệu tổng hợp của toàn bộ tài liệu:
    #     - Xác định tọa độ chung (xstart, ystart, xend, yend) dựa trên tần suất xuất hiện của các giá trị.
    #     - Tính toán chiều rộng và chiều cao vùng chứa văn bản.
    #     - Xác định các thông số font và chiều cao dòng phổ biến nhất.
    #     - Tổng hợp thông tin các đánh dấu chung (dựa trên tần suất xuất hiện).
    # 7. Đánh nhóm các dòng dựa trên định dạng đánh dấu và thực hiện xử lý riêng nếu các đánh dấu có định dạng số La Mã không tuần tự.
    # 8. Cập nhật thông tin của từng dòng (lề trái, khoảng cách dư, chiều rộng dòng thực tế, điều chỉnh các thông số nếu cần).
    # Tham số:
    #      path (str): Đường dẫn đến file PDF hoặc DOCX cần phân tích.
    #      exceptions_path (str, optional): Đường dẫn đến file JSON chứa các ngoại lệ, mặc định là "exceptions.json".
    #      markers_path (str, optional): Đường dẫn đến file JSON chứa các mẫu đánh dấu, mặc định là "markers.json".
    #      status_path (str, optional): Đường dẫn đến file JSON chứa trạng thái, mặc định là "status.json".
    # Trả về:
    #      dict: Một dictionary có cấu trúc gồm:
    #              - "general": Thông tin tổng hợp của tài liệu như kích thước trang, tọa độ vùng chứa, font và line height phổ biến, các mẫu đánh dấu chung,...
    #              - "lines": Danh sách các dictionary, mỗi dictionary chứa thông tin chi tiết của từng dòng (văn bản, định dạng, vị trí, kích thước, thông tin marker, kiểu chữ của từ đầu và từ cuối, ...).

    if not os.path.exists(path):
        raise FileNotFoundError(f"File {path} không tồn tại")
    file_ext = os.path.splitext(path)[1].lower()
    if file_ext not in [".docx", ".pdf"]:
        raise ValueError("Định dạng file không được hỗ trợ. Chỉ hỗ trợ .docx và .pdf.")

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
        all_x0, all_y0, all_x1, all_y1 = [], [], [], []
        first_line_y0_per_page = {}
        last_line_y1_per_page = {}

        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc):
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
                        if best_score > 0.8:
                            spans = best_spans
                            bold = all(span["flags"] & 16 for span in spans)
                            italic = all(span["flags"] & 2 for span in spans)
                            underline = all(span["flags"] & 8 for span in spans)
                            found = True

                    if not spans:
                        for b in text_dict["blocks"]:
                            if "lines" in b:
                                for l in b["lines"]:
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

                    font_size = round(spans[0]["size"], 1) if spans else 12
                    style = f"{int(bold)}{int(italic)}{int(underline)}"
                    coords = get_line_coordinates(spans)
                    x0, x1, y0, y1 = coords["x0"], coords["x1"], coords["y0"], coords["y1"]
                    
                    all_x0.append(x0)
                    all_y0.append(y0)
                    all_x1.append(x1)
                    all_y1.append(y1)

                    if line_index_in_page == 0:
                        first_line_y0_per_page[page_num] = y0
                    last_line_y1_per_page[page_num] = y1

                    marker_info = extract_marker(cleaned_text, patterns)
                    marker_text = marker_info["marker_text"]
                    marker_format = format_marker(marker_text, patterns)
                    first_word, last_word = get_word_style_and_content(cleaned_text, spans, exceptions, is_pdf=True)

                    lines_data.append({
                        "Line": len(lines_data) + 1,
                        "Text": cleaned_text,
                        "MarkerText": marker_text,
                        "MarkerFormat": marker_format,
                        "CaseStyle": get_CaseStyle(cleaned_text, exceptions),
                        "BracketStatus": bracket_status(cleaned_text, patterns),
                        "Style": style,
                        "FirstWord": first_word,
                        "LastWord": last_word,
                        "FontSize": font_size,
                        "LineHeight": round(y1 - y0, 1),
                        "LineWidth": round(x1 - x0, 1),
                        "MarginLeft": 0,
                        "ExtraSpace": 0,
                        "X0": x0,
                        "X1": x1,
                        "XM": round((x0 + x1)/2, 1)
                    })
                    line_index_in_page += 1

        total_lines = len(lines_data)
        total_pages = len(doc)
        
        x0_counter = Counter(all_x0)
        xstart = get_common_coordinate([x for x, count in x0_counter.items() if count / total_lines > 0.05], threshold=0.05)

        y0_counter = Counter(first_line_y0_per_page.values())
        ystart = get_common_coordinate([y for y, count in y0_counter.items() if count / total_pages > 0.15], threshold=0.15)

        x1_counter = Counter(all_x1)
        xend = get_common_coordinate([x for x, count in x1_counter.items() if count / total_lines > 0.05], threshold=0.05, fallback=True, page_width=doc[0].rect.width if doc else 0)
        
        yend = max(last_line_y1_per_page.values()) if last_line_y1_per_page else 0

        region_width = round(xend - xstart, 1) if xstart and xend else 0
        region_height = round(yend - ystart, 1) if ystart and yend else 0

        for line in lines_data:
            line["MarginLeft"] = round(line["X0"] - xstart, 1) if xstart else 0
            line["LineWidth"] = round(line["X1"] - line["X0"], 1)
            if line["LineWidth"] <= 0:
                print(f"{line['Line']}: Width = {line['LineWidth']}: {line['Text']}")
                line["LineWidth"] = 0
            
            line["ExtraSpace"] = round(xend - line["X1"], 1) if xend else 0
            if line["ExtraSpace"] < 0:
                line["ExtraSpace"] = 0
            
            if line["FirstWord"]["width"] > line["LineWidth"]:
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
            "region_height": region_height,
            "region_width": region_width,
            "common_font_size": common_font_size,
            "common_line_height": common_line_height,
            "common_line_width": round(Counter([l["LineWidth"] for l in lines_data]).most_common(1)[0][0], 1) if lines_data else 0,
            "common_markers": common_markers
        }

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