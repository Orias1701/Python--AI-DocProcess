import re
import os
from docx import Document
import fitz

def sentence_end(text):
    brackets = ["()", "''", '""', "[]", "{}", "«»", "“”", "‘’"]
    valid_brackets = any(text.startswith(pair[0]) and text.endswith(pair[1]) for pair in brackets)
    valid_end = text.endswith(('.', '!', '?', ':', ';'))
    return valid_end or valid_brackets

def markers(text):
    return bool(re.match(r'^([-+*•●◦○] )|([0-9a-zA-Z\-\+\*ivxIVX]+[.)\]:] )|(\(\d+\) )|(\(\w+\) )|([0-9]+\s+-\s+[0-9]+ )', text))

def unclosed(text):
    stack = []
    brackets = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'", "«": "»", "“": "”", "‘": "’"}
    for char in text:
        if char in brackets.keys():
            stack.append(char)
        elif char in brackets.values():
            if stack and brackets[stack[-1]] == char:
                stack.pop()
            else:
                return False
    return bool(stack)

def get_case_style(text, exceptions):
    words = [word for word in text.split() if word.lower() not in exceptions and word.strip()]
    if not words:
        return None
    
    is_upper = all(word.isupper() for word in words if word.isalpha() or any(c.isalpha() for c in word))
    is_lower = all(word.islower() for word in words if word.isalpha() or any(c.isalpha() for c in word))
    is_title = all(word[0].isupper() and word[1:].islower() if len(word) > 1 else word[0].isupper() 
                   for word in words if word.isalpha() or any(c.isalpha() for c in word))
    
    if is_upper:
        return "upper"
    if is_lower:
        return "lower"
    if is_title:
        return "title"
    return "mixed"

def merge_text(para, new_para):
    exceptions = {
        "a", "an", "the", "and", "but", "or", "nor", "for", "so", "yet",
        "at", "by", "in", "of", "on", "to", "from", "with", "as",
        "into", "like", "over", "under", "up", "down", "out", "upon", "onto",  
        "amid", "among", "between", "before", "after", "against"
    }
    
    # Kiểm tra kiểu case của hai đoạn
    para_case = get_case_style(para, exceptions)
    new_para_case = get_case_style(new_para, exceptions)
    
    # Điều kiện không gộp: kiểu case khác nhau, new_para không bắt đầu bằng chữ hoa, và không có marker
    different_case = (para_case is not None and new_para_case is not None and 
                      para_case != new_para_case and 
                      new_para and new_para[0].isupper())
    
    # Điều kiện gộp gốc
    should_merge = (
        (not (new_para.isupper() ^ para.isupper()) and 
         not markers(new_para) and 
         (not new_para[0].isupper() or not sentence_end(para))) or 
        unclosed(para)
    )
    
    # Kết hợp điều kiện: không gộp nếu different_case là True
    return should_merge and not different_case
def extracted(path):
    # Trích xuất văn bản từ file (.docx, .doc, .pdf) và tổ chức thành các đoạn.
    file_ext = os.path.splitext(path)[1].lower()
    text_data = []

    if file_ext == ".docx":
        doc = Document(path)
        paragraph = ""
        for para in doc.paragraphs:
            for line in para.text.split("\n"):
                cleaned_text = ' '.join(line.strip().split())
                if cleaned_text:
                    if paragraph and merge_text(paragraph, cleaned_text):
                        paragraph += " " + cleaned_text
                    else:
                        if paragraph:
                            text_data.append({"text": paragraph})
                        paragraph = cleaned_text
        if paragraph:
            text_data.append({"text": paragraph})

    elif file_ext == ".pdf":
        doc = fitz.open(path)
        paragraph = ""
        for page in doc:
            blocks = sorted(page.get_text("blocks"), key=lambda b: (b[1], b[0]))
            for block in blocks:
                for line in block[4].split("\n"):
                    cleaned_text = " ".join(line.strip().split())
                    if cleaned_text:
                        if paragraph and merge_text(paragraph, cleaned_text):
                            paragraph += " " + cleaned_text
                        else:
                            if paragraph:
                                text_data.append({"text": paragraph})
                            paragraph = cleaned_text
        if paragraph:
            text_data.append({"text": paragraph})

    return text_data