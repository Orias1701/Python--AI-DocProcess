import re
import os
from docx import Document
import fitz
import json
from collections import Counter
from docx.oxml.ns import qn
from docx.shared import Pt

def load_exceptions(file_path="exceptions.json"):
    """Tải các từ thông dụng, tên riêng và viết tắt từ file JSON.

    Args:
        file_path (str): Đường dẫn tới file JSON chứa danh sách ngoại lệ.

    Returns:
        dict: Từ điển chứa 'common_words' (tập hợp chuỗi), 'proper_names' và 
              'abbreviations' (tập hợp các tuple (text, case_style)).

    Raises:
        FileNotFoundError: Nếu file JSON không tồn tại.
        json.JSONDecodeError: Nếu file JSON bị lỗi định dạng.
    """
    # Định nghĩa dữ liệu mặc định nếu file JSON không tồn tại hoặc lỗi
    default_exceptions = {
        "common_words": {
            "a", "an", "the", "and", "but", "or", "nor", "for", "so", "yet",
            "at", "by", "in", "of", "on", "to", "from", "with", "as",
            "into", "like", "over", "under", "up", "down", "out", "upon", "onto",
            "amid", "among", "between", "before", "after", "against"
        },
        # Tên riêng: Các địa danh, tổ chức hoặc tên người
        "proper_names": {
            ("Việt Nam", "title"), ("Hà Nội", "title"), ("ASEAN", "upper")
        },
        # Viết tắt: Các từ viết tắt phổ biến
        "abbreviations": {
            ("VN", "upper"), ("TP.HCM", "title")
        }
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Chuyển đổi dữ liệu từ JSON thành cấu trúc mong muốn
            common_words = set(data.get("common_words", []))
            proper_names = [
                (item["text"], item.get("case_style", "title"))
                for item in data.get("proper_names", [])
            ]
            abbreviations = [
                (item["text"], item.get("case_style", "title"))
                for item in data.get("abbreviations", [])
            ]
            return {
                "common_words": common_words,
                "proper_names": set(proper_names),
                "abbreviations": set(abbreviations)
            }
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"Lỗi khi tải file ngoại lệ: {e}. Sử dụng tập hợp mặc định.")
        return default_exceptions

def load_patterns(file_path="patterns.json"):
    """Tải các mẫu đánh dấu, ngoặc và dấu kết thúc câu từ file JSON.

    Args:
        file_path (str): Đường dẫn tới file JSON chứa các mẫu.

    Returns:
        dict: Từ điển chứa các mẫu regex đã biên dịch và cấu hình.

    Raises:
        FileNotFoundError: Nếu file JSON không tồn tại.
        json.JSONDecodeError: Nếu file JSON bị lỗi định dạng.
    """
    # Định nghĩa các mẫu mặc định
    default_patterns = {
        # Các mẫu đánh dấu đầu dòng hoặc mục
        "markers": [
            {"pattern": "[-+*•●◦○] ", "description": "Dấu đầu dòng"},
            {"pattern": "[0-9a-zA-Z\\-+*ivxIVX]+[.)\\]:] ", "description": "Danh sách số hoặc chữ"},
            {"pattern": "\\(\\d+\\) ", "description": "Số trong ngoặc"},
            {"pattern": "\\(\\w+\\) ", "description": "Chữ hoặc từ trong ngoặc"},
            {"pattern": "[0-9]+\\s+-\\s+[0-9]+ ", "description": "Khoảng số"},
            {"pattern": "^(Chapter|Section|Part|Điều)\\s+[0-9]+|^(Chapter|Section|Part|Điều)\\s+[MDCLXVI]+|^(Chapter|Section|Part|Điều)\\s+[A-Z]", 
             "description": "Chương/Mục/Phần/Điều với số, số La Mã hoặc chữ cái"}
        ],
        # Các mẫu ngoặc
        "brackets": {
            "open": "[\\(\\[\\{«“‘]",  # Ngoặc mở
            "close": "[\\)\\]\\}»”’]",  # Ngoặc đóng
            "pairs": ["()", "''", "\"\"", "[]", "{}", "«»", "“”", "‘’"]  # Cặp ngoặc hợp lệ
        },
        # Các mẫu kết thúc câu
        "sentence_ends": {
            "punctuation": "[.!?:;]",  # Dấu chấm câu kết thúc
            "valid_brackets": ["()", "''", "\"\"", "[]", "{}", "«»", "“”", "‘’"]  # Cặp ngoặc kết thúc hợp lệ
        }
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Biên dịch các mẫu đánh dấu
            markers = [
                {"pattern": re.compile(item["pattern"], re.IGNORECASE), "description": item.get("description", "")}
                for item in data.get("markers", default_patterns["markers"])
            ]
            # Biên dịch các mẫu ngoặc
            brackets = {
                "open": re.compile(data["brackets"].get("open", default_patterns["brackets"]["open"])),
                "close": re.compile(data["brackets"].get("close", default_patterns["brackets"]["close"])),
                "pairs": data["brackets"].get("pairs", default_patterns["brackets"]["pairs"])
            }
            # Biên dịch các mẫu kết thúc câu
            sentence_ends = {
                "punctuation": re.compile(data["sentence_ends"].get("punctuation", default_patterns["sentence_ends"]["punctuation"])),
                "valid_brackets": data["sentence_ends"].get("valid_brackets", default_patterns["sentence_ends"]["valid_brackets"])
            }
            return {
                "markers": markers,
                "brackets": brackets,
                "sentence_ends": sentence_ends
            }
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"Lỗi khi tải file mẫu: {e}. Sử dụng mẫu mặc định.")
        # Biên dịch các mẫu mặc định
        return {
            "markers": [
                {"pattern": re.compile(item["pattern"], re.IGNORECASE), "description": item["description"]}
                for item in default_patterns["markers"]
            ],
            "brackets": {
                "open": re.compile(default_patterns["brackets"]["open"]),
                "close": re.compile(default_patterns["brackets"]["close"]),
                "pairs": default_patterns["brackets"]["pairs"]
            },
            "sentence_ends": {
                "punctuation": re.compile(default_patterns["sentence_ends"]["punctuation"]),
                "valid_brackets": default_patterns["sentence_ends"]["valid_brackets"]
            }
        }

def sentence_end(text, patterns=None):
    """Kiểm tra xem văn bản có kết thúc bằng dấu chấm câu hoặc cặp ngoặc hợp lệ không.

    Args:
        text (str): Văn bản cần kiểm tra.
        patterns (dict, optional): Từ điển chứa các mẫu regex.

    Returns:
        bool: True nếu văn bản kết thúc hợp lệ, False nếu không.
    """
    if patterns is None:
        patterns = load_patterns()
    valid_end = patterns["sentence_ends"]["punctuation"].search(text[-1])
    valid_brackets = any(text.startswith(pair[0]) and text.endswith(pair[1]) for pair in patterns["sentence_ends"]["valid_brackets"])
    return bool(valid_end or valid_brackets)

def markers(text, patterns=None):
    """Kiểm tra xem văn bản có bắt đầu bằng đánh dấu danh sách (dấu đầu dòng, số, v.v.) không.

    Args:
        text (str): Văn bản cần kiểm tra.
        patterns (dict, optional): Từ điển chứa các mẫu regex.

    Returns:
        bool: True nếu văn bản bắt đầu bằng đánh dấu, False nếu không.
    """
    if patterns is None:
        patterns = load_patterns()
    return any(pattern["pattern"].match(text) for pattern in patterns["markers"])

def bracket_status(text, patterns=None):
    """Kiểm tra trạng thái ngoặc trong văn bản, không tính ngoặc trong đánh dấu.

    Args:
        text (str): Văn bản cần phân tích.
        patterns (dict, optional): Từ điển chứa các mẫu regex cho đánh dấu và ngoặc.

    Returns:
        str: Trạng thái ngoặc ('none', 'open', 'close', hoặc 'both').
    """
    if patterns is None:
        patterns = load_patterns()
    
    # Loại bỏ phần đánh dấu nếu có
    non_marker_text = text
    for pattern in patterns["markers"]:
        match = pattern["pattern"].match(text)
        if match:
            non_marker_text = text[len(match.group(0)):]
            break
    
    # Đếm ngoặc mở và đóng trong văn bản không chứa đánh dấu
    open_count = sum(1 for _ in patterns["brackets"]["open"].finditer(non_marker_text))
    close_count = sum(1 for _ in patterns["brackets"]["close"].finditer(non_marker_text))
    
    # Kiểm tra cặp ngoặc hợp lệ (bao gồm cả trường hợp lồng nhau)
    if open_count == close_count and open_count > 0:
        stack = []
        valid = True
        for char in non_marker_text:
            if patterns["brackets"]["open"].match(char):
                stack.append(char)
            elif patterns["brackets"]["close"].match(char):
                if not stack:
                    valid = False
                    break
                # Kiểm tra ngoặc đóng có khớp với ngoặc mở gần nhất
                last_open = stack.pop()
                pair_valid = any(
                    last_open == pair[0] and char == pair[1]
                    for pair in patterns["brackets"]["pairs"]
                )
                if not pair_valid:
                    valid = False
                    break
        if valid and not stack:
            return "none"
    
    # Xác định trạng thái dựa trên số lượng và thứ tự
    if open_count > close_count:
        return "open"
    elif close_count > open_count:
        return "close"
    elif open_count == close_count and open_count > 0:
        # Nếu số lượng bằng nhau nhưng thứ tự không hợp lệ
        for i, char in enumerate(non_marker_text):
            if patterns["brackets"]["close"].match(char):
                if not any(patterns["brackets"]["open"].match(non_marker_text[j]) for j in range(i)):
                    return "both"
        return "none"
    elif open_count > 0 and close_count > 0:
        return "both"
    return "none"

def get_case_style(text, exceptions):
    """Xác định kiểu chữ hoa/thường của văn bản, không tính các từ ngoại lệ.

    Args:
        text (str): Văn bản cần phân tích.
        exceptions (dict): Từ điển chứa các từ ngoại lệ.

    Returns:
        str: Kiểu chữ ('upper', 'title', hoặc 'mixed').
    """
    exception_texts = exceptions["common_words"] | {item[0].lower() for item in exceptions["proper_names"] | exceptions["abbreviations"]}
    words = [word for word in text.split() if word.lower() not in exception_texts and word.strip()]
    
    if not words:
        return "mixed"
    
    has_non_exception = any(word.isalpha() and word.lower() not in exception_texts for word in words)
    if not has_non_exception:
        return "mixed"
    
    is_upper = all(word.isupper() for word in words if word.isalpha() or any(c.isalpha() for c in word))
    is_title = all(word[0].isupper() and word[1:].islower() if len(word) > 1 else word[0].isupper()
                   for word in words if word.isalpha() or any(c.isalpha() for c in word))
    
    if is_upper:
        return "upper"
    if is_title:
        return "title"
    return "mixed"

def get_first_word_width(text, spans=None, font_size=12, is_pdf=False):
    """Tính chiều rộng của từ đầu tiên dựa trên tọa độ (PDF) hoặc kích thước phông (DOCX).

    Args:
        text (str): Văn bản cần phân tích.
        spans (list, optional): Danh sách các span từ khối văn bản PDF.
        font_size (float): Kích thước phông chữ cho DOCX.
        is_pdf (bool): Tài liệu có phải là PDF không.

    Returns:
        float: Chiều rộng của từ đầu tiên (điểm), làm tròn đến 1 chữ số thập phân.
    """
    words = text.strip().split()
    if not words:
        return 0
    first_word = words[0].rstrip(".")  # Loại bỏ dấu câu cuối
    
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
        print(f"Cảnh báo: Không tìm thấy span cho từ đầu tiên '{first_word}' trong PDF. Sử dụng giá trị mặc định.")
    char_width = font_size * 0.4  # Điều chỉnh cho phông tiếng Việt
    return round(len(first_word) * char_width, 1)

def get_page_size_docx(doc):
    """Lấy kích thước trang từ tài liệu DOCX.

    Args:
        doc: Đối tượng Document của python-docx.

    Returns:
        tuple: (page_width, page_height) tính bằng điểm, hoặc (612, 792) nếu không có.
    """
    for section in doc.sections:
        page_width = section.page_width.pt if section.page_width else 612
        page_height = section.page_height.pt if section.page_height else 792
        return page_width, page_height
    return 612, 792  # Mặc định kích thước US Letter (8.5x11 inch ở 72 DPI)

def extract_and_analyze(path, exceptions_path="exceptions.json", patterns_path="patterns.json"):
    """Trích xuất và phân tích thuộc tính văn bản từ file DOCX hoặc PDF.

    Args:
        path (str): Đường dẫn tới file đầu vào (.docx hoặc .pdf).
        exceptions_path (str): Đường dẫn tới file JSON chứa ngoại lệ.
        patterns_path (str): Đường dẫn tới file JSON chứa mẫu.

    Returns:
        dict: Kết quả phân tích với thuộc tính chung và dữ liệu từng dòng.

    Raises:
        FileNotFoundError: Nếu file đầu vào hoặc file ngoại lệ không tồn tại.
        ValueError: Nếu định dạng file không được hỗ trợ.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"File {path} không tồn tại")
    file_ext = os.path.splitext(path)[1].lower()
    if file_ext not in [".docx", ".pdf"]:
        raise ValueError("Định dạng file không được hỗ trợ. Chỉ hỗ trợ .docx và .pdf.")
    
    exceptions = load_exceptions(exceptions_path)
    patterns = load_patterns(patterns_path)
    lines_data = []
    page_data = []
    line_widths = []
    
    if file_ext == ".docx":
        doc = Document(path)
        page_width, page_height = get_page_size_docx(doc)
        prev_bottom = None
        page_num = 0
        line_positions = []
        
        for i, para in enumerate(doc.paragraphs):
            for line in para.text.split("\n"):
                cleaned_text = ' '.join(line.strip().split())
                if not cleaned_text:
                    continue
                
                # Lấy thuộc tính phông chữ và kiểu
                font_size = para.runs[0].font.size.pt if para.runs and para.runs[0].font.size else 12
                bold = any(run.bold for run in para.runs if run.text.strip() and run.bold is not None)
                italic = any(run.italic for run in para.runs if run.text.strip() and run.italic is not None)
                underline = any(run.underline for run in para.runs if run.text.strip() and run.underline is not None)
                
                # Lấy lề và khoảng cách đoạn
                margin_left = para.paragraph_format.left_indent.pt if para.paragraph_format.left_indent else 0
                margin_right = para.paragraph_format.right_indent.pt if para.paragraph_format.right_indent else 0
                line_spacing = para.paragraph_format.line_spacing if para.paragraph_format.line_spacing else 1.15
                space_before = para.paragraph_format.space_before.pt if para.paragraph_format.space_before else 0
                space_after = para.paragraph_format.space_after.pt if para.paragraph_format.space_after else 0
                
                # Mô phỏng vị trí y
                current_top = 0 if prev_bottom is None else prev_bottom + space_before
                current_bottom = current_top + (font_size or 12)
                margin_top = current_top if prev_bottom is None else current_top - prev_bottom
                margin_bottom = space_after
                
                # Tính chiều rộng dòng
                line_width = round(page_width - margin_left - margin_right, 1)
                line_widths.append(line_width)
                
                # Làm tròn các giá trị số
                font_size = round(font_size, 1)
                line_height = round(line_spacing * font_size if font_size else 1.15 * 12, 1)
                margin_top = round(margin_top, 1)
                margin_bottom = round(margin_bottom, 1)
                margin_left = round(margin_left, 1)
                margin_right = round(margin_right, 1)
                
                # Khởi tạo dữ liệu trang
                if prev_bottom is None:
                    page_data.append({
                        "top": margin_top,
                        "bottoms": [],
                        "lefts": [margin_left],
                        "rights": [margin_right],
                        "last_bottom": None
                    })
                else:
                    page_data[page_num]["lefts"].append(margin_left)
                    page_data[page_num]["rights"].append(margin_right)
                    page_data[page_num]["bottoms"].append(margin_bottom)
                
                line_positions.append({"top": current_top, "bottom": current_bottom})
                lines_data.append({
                    "Line": len(lines_data) + 1,
                    "Text": cleaned_text,
                    "HasMarker": markers(cleaned_text, patterns),
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
                    "FirstWordWidth": get_first_word_width(cleaned_text, font_size=font_size, is_pdf=False),
                    "LineWidth": line_width
                })
                prev_bottom = current_bottom
                page_data[page_num]["last_bottom"] = current_bottom
        
        # Điều chỉnh lề dưới cho dòng cuối mỗi trang
        if page_data and lines_data:
            page_data[page_num]["bottoms"][-1] = round(page_height - page_data[page_num]["last_bottom"], 1)

    elif file_ext == ".pdf":
        doc = fitz.open(path)
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
                    
                    # Trích xuất thông tin bố cục
                    x0, y0, x1, y1 = block[:4]
                    margin_left = x0 - page.rect.x0
                    margin_right = page_width - x1
                    margin_top = y0 - page.rect.y0 if prev_bottom is None else y0 - prev_bottom
                    margin_bottom = page_height - y1
                    
                    if prev_bottom is None:
                        page_info["top"] = y0 - page.rect.y0
                    page_info["lefts"].append(margin_left)
                    page_info["rights"].append(margin_right)
                    page_info["bottoms"].append(margin_bottom)
                    
                    # Tính chiều rộng dòng
                    line_width = round(x1 - x0, 1)
                    line_widths.append(line_width)
                    
                    # Thông tin phông chữ và kiểu
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
                    
                    # Làm tròn các giá trị số
                    font_size = round(font_size, 1)
                    line_height = round(line_spacing * font_size, 1)
                    margin_top = round(margin_top, 1)
                    margin_bottom = round(margin_bottom, 1)
                    margin_left = round(margin_left, 1)
                    margin_right = round(margin_right, 1)
                    
                    first_word_width = get_first_word_width(cleaned_text, spans=spans, is_pdf=True)
                    if first_word_width > line_width:
                        print(f"Cảnh báo: FirstWordWidth ({first_word_width}) vượt quá LineWidth ({line_width}) cho văn bản: {cleaned_text}")
                        first_word_width = line_width
                    
                    line_positions.append({"text": cleaned_text, "top": y0, "bottom": y1})
                    lines_data.append({
                        "Line": len(lines_data) + 1,
                        "Text": cleaned_text,
                        "HasMarker": markers(cleaned_text, patterns),
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
            
            # Điều chỉnh lề dưới cho dòng cuối của trang
            if line_positions:
                last_line_idx = len(lines_data) - 1
                lines_data[last_line_idx]["MarginBottom"] = round(page_height - page_info["last_bottom"], 0)
    
    # Tính các thuộc tính chung
    top_margins = [p["top"] for p in page_data if p["top"] is not None]
    bottom_margins = [p["bottoms"][-1] for p in page_data if p["bottoms"]]
    left_margins = [m for p in page_data for m in p["lefts"]]
    right_margins = [m for p in page_data for m in p["rights"]]
    
    right_align = Counter(right_margins).most_common(1)[0][0] if right_margins and Counter(right_margins).most_common(1)[0][1] > 1 else min(right_margins) if right_margins else 0
    common_line_width = Counter(line_widths).most_common(1)[0][0] if line_widths else 0
    
    general = {
        "top_align": round(Counter(top_margins).most_common(1)[0][0], 1) if top_margins else 0,
        "bottom_align": round(Counter(bottom_margins).most_common(1)[0][0], 1) if bottom_margins else 0,
        "left_align": round(Counter(left_margins).most_common(1)[0][0], 1) if left_margins else 0,
        "right_align": round(right_align, 1),
        "general_font_size": round(Counter([l["FontSize"] for l in lines_data]).most_common(1)[0][0], 1) if lines_data else 12.0,
        "general_line_height": round(Counter([l["LineHeight"] for l in lines_data]).most_common(1)[0][0], 1) if lines_data else 13.8,
        "common_line_width": round(common_line_width, 1)
    }
    
    # Tính khoảng dư cho mỗi dòng
    for line in lines_data:
        line["ExtraSpace"] = round(general["common_line_width"] - line["LineWidth"], 1) if general["common_line_width"] > 0 else 0
    
    return {
        "general": general,
        "lines": lines_data
    }