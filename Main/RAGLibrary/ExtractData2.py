import re
import os
from docx import Document
import fitz

def sentence_end(text):

    # Kiểm tra xem chuỗi văn bản có kết thúc bằng dấu câu hợp lệ hoặc cặp ngoặc hợp lệ hay không.

    brackets = ["()", "''", '""', "[]", "{}", "«»", "“”", "‘’"]
    valid_brackets = any(text.startswith(pair[0]) and text.endswith(pair[1]) for pair in brackets)
    valid_end = text.endswith(('.', '!', '?', ':', ';'))
    return valid_end or valid_brackets

def markers(text):

    # Kiểm tra xem chuỗi văn bản có bắt đầu bằng dấu hiệu danh sách (bullet, số thứ tự, v.v.) hay không.

    return bool(re.match(r'^([-+*•●◦○] )|([0-9a-zA-Z\-\+\*ivxIVX]+[.)\]:] )|(\(\d+\) )|(\(\w+\) )|([0-9]+\s+-\s+[0-9]+ )', text))

def unclosed(text):

    # Kiểm tra xem chuỗi văn bản có chứa ngoặc chưa được đóng hay không.

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

def merge_text(para, new_para):
    
    # Quyết định xem có nên gộp hai đoạn văn bản thành một hay không dựa trên các tiêu chí ngữ nghĩa.

    should_merge = (not (new_para.isupper() ^ para.isupper()) and not markers(new_para) and (not new_para[0].isupper() or not sentence_end(para))) or unclosed(para)
    return should_merge

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