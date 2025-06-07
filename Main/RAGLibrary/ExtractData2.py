import re
import os
from docx import Document
import fitz
import json
from collections import Counter
from docx.oxml.ns import qn
from docx.shared import Pt

# Load proper names and abbreviations from JSON file
def load_exceptions(file_path="exceptions.json"):
    """Load common words, proper names, and abbreviations from a JSON file.
    
    Args:
        file_path (str): Path to the JSON file containing exceptions.
    
    Returns:
        dict: Dictionary with 'common_words' (set of strings), 'proper_names' and 'abbreviations' (sets of (text, case_style) tuples).
    
    Raises:
        FileNotFoundError: If JSON file does not exist.
        json.JSONDecodeError: If JSON file is malformed.
    """
    def determine_case_style(text):
        """Determine case style of a word (title or upper)."""
        if text.isupper():
            return "upper"
        if text and text[0].isupper() and all(c.islower() or not c.isalpha() for c in text[1:]):
            return "title"
        return "title"  # Default to title for proper names/abbreviations
    
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Exceptions file {file_path} not found")
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            common_words = set(data.get("common_words", []))
            proper_names = [
                (item["text"], item.get("case_style", determine_case_style(item["text"])))
                for item in data.get("proper_names", [])
            ]
            abbreviations = [
                (item["text"], item.get("case_style", determine_case_style(item["text"])))
                for item in data.get("abbreviations", [])
            ]
            return {
                "common_words": common_words,
                "proper_names": set(proper_names),
                "abbreviations": set(abbreviations)
            }
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"Error loading exceptions: {e}. Using default set.")
        return {
            "common_words": {
                "a", "an", "the", "and", "but", "or", "nor", "for", "so", "yet",
                "at", "by", "in", "of", "on", "to", "from", "with", "as",
                "into", "like", "over", "under", "up", "down", "out", "upon", "onto",
                "amid", "among", "between", "before", "after", "against"
            },
            "proper_names": {
                ("Việt Nam", "title"), ("Hà Nội", "title"), ("ASEAN", "upper")
            },
            "abbreviations": {
                ("VN", "upper"), ("TP.HCM", "title")
            }
        }

def sentence_end(text):
    """Check if text ends with a sentence-ending punctuation or valid brackets."""
    brackets = ["()", "''", '""', "[]", "{}", "«»", "“”", "‘’"]
    valid_brackets = any(text.startswith(pair[0]) and text.endswith(pair[1]) for pair in brackets)
    valid_end = text.endswith(('.', '!', '?', ':', ';'))
    return valid_end or valid_brackets

def markers(text):
    """Check if text starts with a list marker (bullet, number, etc.)."""
    return bool(re.match(r'^([-+*•●◦○] )|([0-9a-zA-Z\-\+\*ivxIVX]+[.)\]:] )|(\(\d+\) )|(\(\w+\) )|([0-9]+\s+-\s+[0-9]+ )', text))

def bracket_status(text):
    """Check bracket status in text using regex for efficiency."""
    if re.search(r'[\(\[\{«“‘].*[\)\]\}»”’]', text):
        return "none"
    if re.search(r'[\(\[\{«“‘]', text):
        return "open"
    if re.search(r'[\)\]\}»”’]', text):
        return "close"
    return "none"

def get_case_style(text, exceptions):
    """Determine the case style of text (upper, title, or mixed), excluding common words, proper names, and abbreviations.
    
    Args:
        text (str): The text to analyze.
        exceptions (dict): Dictionary with 'common_words' (set of strings), 'proper_names' and 'abbreviations' (sets of (text, case_style) tuples).
    
    Returns:
        str: Case style ('upper', 'title', or 'mixed').
    """
    # Extract text from exceptions
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
    """Calculate the width of the first word using coordinates (PDF) or font size (DOCX).
    
    Args:
        text (str): The text to analyze.
        spans (list): List of span dictionaries from PDF text block (for PDF).
        font_size (float): Font size for DOCX fallback.
        is_pdf (bool): Whether the document is a PDF.
    
    Returns:
        float: Width of the first word in points, rounded to 1 decimal place.
    """
    words = text.strip().split()
    if not words:
        return 0
    first_word = words[0].rstrip(".")  # Remove trailing punctuation for width calculation
    
    if is_pdf and spans:
        for span in spans:
            span_text = span["text"].strip()
            # Normalize span text and first word for Vietnamese characters
            normalized_span = span_text.replace("\xa0", " ").strip()
            normalized_first_word = first_word.replace("\xa0", " ").strip()
            
            # Check if span starts with the first word
            if normalized_span == normalized_first_word or normalized_span.startswith(normalized_first_word + " "):
                x0, _, x1, _ = span["bbox"]
                width = x1 - x0
                # If span contains more than the first word, estimate width proportionally
                if normalized_span != normalized_first_word:
                    char_count = len(normalized_span)
                    first_word_len = len(normalized_first_word)
                    width = width * (first_word_len / char_count)
                return round(width, 1)
            # Handle case where first word is part of a larger span
            elif normalized_first_word in normalized_span and normalized_span.index(normalized_first_word) == 0:
                x0, _, x1, _ = span["bbox"]
                char_count = len(normalized_span)
                first_word_len = len(normalized_first_word)
                width = (x1 - x0) * (first_word_len / char_count)
                return round(width, 1)
        print(f"Warning: No span found for first word '{first_word}' in PDF. Using fallback.")
    # Fallback for DOCX or when spans are not found
    char_width = font_size * 0.4  # Adjusted for Vietnamese fonts
    return round(len(first_word) * char_width, 1)

def get_page_size_docx(doc):
    """Get page size from a DOCX document.
    
    Args:
        doc: python-docx Document object.
    
    Returns:
        tuple: (page_width, page_height) in points, or (612, 792) if not available.
    """
    for section in doc.sections:
        page_width = section.page_width.pt if section.page_width else 612
        page_height = section.page_height.pt if section.page_height else 792
        return page_width, page_height
    return 612, 792  # Default to US Letter size (8.5x11 inches at 72 DPI)

def extract_and_analyze(path, exceptions_path):
    """Extract and analyze text properties from a DOCX or PDF file.
    
    Args:
        path (str): Path to the input file (.docx or .pdf).
        exceptions_path (str): Path to the JSON file with exceptions.
    
    Returns:
        dict: Analysis results with general properties and line-by-line data.
    
    Raises:
        FileNotFoundError: If input file or exceptions file does not exist.
        ValueError: If file format is unsupported.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"File {path} does not exist")
    file_ext = os.path.splitext(path)[1].lower()
    if file_ext not in [".docx", ".pdf"]:
        raise ValueError("Unsupported file format. Only .docx and .pdf are supported.")
    
    exceptions = load_exceptions(exceptions_path)
    lines_data = []
    page_data = []
    line_widths = []  # Store line widths for calculating ExtraSpace
    
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
                
                # Get font and style properties
                font_size = para.runs[0].font.size.pt if para.runs and para.runs[0].font.size else 12
                bold = any(run.bold for run in para.runs if run.text.strip() and run.bold is not None)
                italic = any(run.italic for run in para.runs if run.text.strip() and run.italic is not None)
                underline = any(run.underline for run in para.runs if run.text.strip() and run.underline is not None)
                
                # Get paragraph margins and spacing
                margin_left = para.paragraph_format.left_indent.pt if para.paragraph_format.left_indent else 0
                margin_right = para.paragraph_format.right_indent.pt if para.paragraph_format.right_indent else 0
                line_spacing = para.paragraph_format.line_spacing if para.paragraph_format.line_spacing else 1.15
                space_before = para.paragraph_format.space_before.pt if para.paragraph_format.space_before else 0
                space_after = para.paragraph_format.space_after.pt if para.paragraph_format.space_after else 0
                
                # Simulate y-position
                current_top = 0 if prev_bottom is None else prev_bottom + space_before
                current_bottom = current_top + (font_size or 12)
                margin_top = current_top if prev_bottom is None else current_top - prev_bottom
                margin_bottom = space_after
                
                # Calculate line width
                line_width = round(page_width - margin_left - margin_right, 1)
                line_widths.append(line_width)
                
                # Round numerical values
                font_size = round(font_size, 1)
                line_height = round(line_spacing * font_size if font_size else 1.15 * 12, 1)
                margin_top = round(margin_top, 1)
                margin_bottom = round(margin_bottom, 1)
                margin_left = round(margin_left, 1)
                margin_right = round(margin_right, 1)
                
                # Initialize page data
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
                    "HasMarker": markers(cleaned_text),
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
                    "BracketStatus": bracket_status(cleaned_text),
                    "FirstWordWidth": get_first_word_width(cleaned_text, font_size=font_size, is_pdf=False),
                    "LineWidth": line_width
                })
                prev_bottom = current_bottom
                page_data[page_num]["last_bottom"] = current_bottom
        
        # Adjust margin_bottom for last line of each page
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
                    
                    # Extract layout info
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
                    
                    # Calculate line width
                    line_width = round(x1 - x0, 1)
                    line_widths.append(line_width)
                    
                    # Font and style info
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
                    
                    # Round numerical values
                    font_size = round(font_size, 1)
                    line_height = round(line_spacing * font_size, 1)
                    margin_top = round(margin_top, 1)
                    margin_bottom = round(margin_bottom, 1)
                    margin_left = round(margin_left, 1)
                    margin_right = round(margin_right, 1)
                    
                    first_word_width = get_first_word_width(cleaned_text, spans=spans, is_pdf=True)
                    if first_word_width > line_width:
                        print(f"Warning: FirstWordWidth ({first_word_width}) exceeds LineWidth ({line_width}) for text: {cleaned_text}")
                        first_word_width = min(first_word_width, line_width)
                    
                    line_positions.append({"top": y0, "bottom": y1})
                    lines_data.append({
                        "Line": len(lines_data) + 1,
                        "Text": cleaned_text,
                        "HasMarker": markers(cleaned_text),
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
                        "BracketStatus": bracket_status(cleaned_text),
                        "FirstWordWidth": first_word_width,
                        "LineWidth": line_width
                    })
                    prev_bottom = y1
                    page_info["last_bottom"] = y1
            page_data.append(page_info)
            
            # Adjust margin_bottom for last line of page
            if line_positions:
                last_line_idx = len(lines_data) - 1 - len([b for b in blocks if b[4].strip()])
                if last_line_idx >= 0:
                    lines_data[last_line_idx]["MarginBottom"] = round(page_height - page_info["last_bottom"], 1)
    
    # Calculate general properties
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
    
    # Calculate ExtraSpace for each line
    for line in lines_data:
        line["ExtraSpace"] = round(general["common_line_width"] - line["LineWidth"], 1) if general["common_line_width"] > 0 else 0
    
    return {
        "general": general,
        "lines": lines_data
    }