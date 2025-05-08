import json

# COUNT WORDS
def count_words(text):
    """
    Đếm số từ trong một chuỗi văn bản.

    Args:
        text (str): Chuỗi văn bản cần đếm số từ.

    Returns:
        int: Số từ trong chuỗi văn bản.
    """
    return len(text.split())

# CHUNKING IF WORD LIMIT EXCEEDED
def semantic_chunking(text, max_words, nlp):
    """
    Chia văn bản thành các đoạn nhỏ dựa trên giới hạn số từ, sử dụng phân tích ngữ nghĩa.

    Args:
        text (str): Văn bản cần chia thành các đoạn.
        max_words (int): Số từ tối đa cho mỗi đoạn.
        nlp (callable): Đối tượng xử lý ngôn ngữ tự nhiên (ví dụ: spaCy model).

    Returns:
        list: Danh sách các đoạn văn bản đã chia.
    """
    doc = nlp(text)
    chunks, current_chunk = [], []
    word_count = 0
    
    for sent in doc.sents:
        sentence = sent.text.strip()
        sentence_length = count_words(sentence)  # Gọi count_words
        
        if word_count + sentence_length > max_words and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            word_count = 0
            
        current_chunk.append(sentence)
        word_count += sentence_length
        
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    return chunks

# MAIN PROCESSING FUNCTION
def process_json(chunks_base, json_file_path, Contents, word_limit, markers, nlp):
    """
    Xử lý dữ liệu JSON, chia các đoạn văn bản dài thành các đoạn nhỏ hơn nếu vượt quá giới hạn từ.

    Args:
        chunks_base (str): Đường dẫn đến file JSON đầu vào.
        json_file_path (str): Đường dẫn đến file JSON đầu ra.
        word_limit (int): Số từ tối đa cho mỗi đoạn văn bản.
        markers (callable): Hàm kiểm tra xem đoạn văn có chứa dấu hiệu đặc biệt hay không.
        nlp (callable): Đối tượng xử lý ngôn ngữ tự nhiên (ví dụ: spaCy model).

    Returns:
        None: Kết quả được lưu vào file JSON đầu ra.
    """
    with open(chunks_base, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    processed_data = []
    
    for idx, chunk in enumerate(data):
        if Contents in chunk and isinstance(chunk[Contents], list):
            new_content = []
            
            for para_idx, paragraph in enumerate(chunk[Contents]):
                word_count = count_words(paragraph)
                
                if word_count > word_limit and not markers(paragraph):
                    chunked_paragraphs = semantic_chunking(paragraph, max_words=word_limit, nlp=nlp)
                    new_content.extend(chunked_paragraphs)
                    print(f"{idx+1:04} / {len(data):04}: {len(chunked_paragraphs):02} segments.")
                else:
                    new_content.append(paragraph)
                    
            chunk[Contents] = new_content
            
        processed_data.append(chunk)
        
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(processed_data, f, indent=4, ensure_ascii=False)
        print(f"{idx+1:04} / {len(data):04}: Saved!\n")
    
    print(f"Final data saved to {json_file_path}.")