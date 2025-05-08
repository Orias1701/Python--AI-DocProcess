import os
import json
import torch
from typing import Any, Dict

""" PREPROCESS TEXT """

def preprocess_text(text):
    import re
    if isinstance(text, list):
        return [preprocess_text(t) for t in text]
    if isinstance(text, str):
        text = text.strip()
        text = re.sub(r'[^\w\s\(\)\.\,\;\:\-–]', '', text)
        text = re.sub(r'[ ]{2,}', ' ', text)
        return text
    return text

""" PREPROCESS DATA """

def preprocess_data(data):
    if isinstance(data, dict):
        return {key: preprocess_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [preprocess_data(item) for item in data]
    else:
        return preprocess_text(data)
    
""" LOAD SCHEMA """

def load_schema(schema_path: str) -> Dict[str, str]:
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Schema file not found: {schema_path}")
        return {}
    except json.JSONDecodeError:
        print(f"Invalid schema file: {schema_path}")
        return {}
    
""" FLATTEN JSON """

def flatten_json(data: Any, prefix: str = "", schema: Dict[str, str] = None) -> Dict[str, Any]:

    flat = {}
    
    if schema is None:
        schema = {}

    # Nếu dữ liệu là dict
    if isinstance(data, dict):
        for key, value in data.items():
            # Tạo tiền tố mới cho key
            new_prefix = f"{prefix}{key}" if prefix else key

            # Nếu là dict hoặc list, làm phẳng
            if isinstance(value, (dict, list)):
                flat.update(flatten_json(value, f"{new_prefix}.", schema))
            else:
                # Nếu là kiểu dữ liệu cơ bản, thêm vào dict
                flat[new_prefix] = value

    # Nếu là một danh sách và không rỗng
    elif isinstance(data, list) and data:
        # Lưu danh sách vào dictionary với key là tiền tố (bỏ dấu '.')
        flat[prefix.rstrip('.')] = data

    return flat

""" CREATE EMBEDDDING """

def create_embedding(device, model, texts, batch_size=32, batches: bool = False):
    print(f"Type of texts: {type(texts)}")
    print(f"Sample texts: {texts[:2] if isinstance(texts, list) else texts}")
    print(f"Device: {device}, Batch size: {batch_size}")
    try:
        embeddings = model.encode(
            sentences=texts,
            batch_size=batch_size,
            convert_to_tensor=True,
            device=device,
            show_progress_bar = batches
        )
        return embeddings
    except RuntimeError as e:
        if "CUDA out of memory" in str(e):
            print("VRAM overflow. Switching to CPU.")
            model.to("cpu")
            return model.encode(
                sentences=texts,
                batch_size=batch_size,
                convert_to_tensor=True,
                device="cpu",
                show_progress_bar = batches
            )
        raise e
    

""" CREATE EMBEDDDINGS """

def create_embeddings(MERGE, data: Any, schema: Dict[str, str], model, device: torch.device, merge: str = "no_Merge", batches: bool = False) -> Dict[str, Any]:
    flat_data = flatten_json(data, schema=schema)
    embeddings = {}
    
    if MERGE == "Merge":
        # Gộp tất cả các trường
        merged_texts = []
        for key, value in flat_data.items():
            if schema.get(key) in ["string", "array"]:
                if isinstance(value, str) and value.strip():
                    merged_texts.append(preprocess_text(value))
                elif isinstance(value, list):
                    text = "\n".join([preprocess_text(str(item)) for item in value if str(item).strip()])
                    if text.strip():
                        merged_texts.append(text)
        if merged_texts:
            # Tạo embedding
            merged_text = "\n".join(merged_texts)
            if merged_text.strip():
                # Sửa lời gọi create_embedding
                embedding = create_embedding(device, model, merged_text, batch_size=32, batches = batches).to(device)
                embeddings["merged_embedding"] = embedding
    else:
        # Embedding riêng lẻ
        for key, value in flat_data.items():
            if schema.get(key) in ["string", "array"]:
                if isinstance(value, str) and value.strip():
                    # Sửa lời gọi create_embedding
                    embedding = create_embedding(device, model, preprocess_text(value), batch_size=32, batches = batches).to(device)
                    embeddings[f"{key} Embedding"] = embedding
                elif isinstance(value, list):
                    text = "\n".join([preprocess_text(str(item)) for item in value if str(item).strip()])
                    if text.strip():
                        # Sửa lời gọi create_embedding
                        embedding = create_embedding(device, model, text, batch_size=32, batches = batches).to(device)
                        embeddings[f"{key} Embedding"] = embedding

    # Kết hợp dữ liệu gốc và embedding
    if MERGE == "Merge":
        result = [{} for _ in range(len(data))] if isinstance(data, list) else {}
    else:
        result = data.copy()

    for embed_key, embed_value in embeddings.items():
        if MERGE == "Merge":
            result["Merged_text"] = merged_text
            result["Merged_embedding"] = embed_value.tolist()
        else:
            keys = embed_key.split(" Embedding")[0].split('.')
            current = result
            for i, k in enumerate(keys[:-1]):
                current = current.setdefault(k, {})
            current[keys[-1] + " Embedding"] = embed_value.tolist()
    return result

""" JSON EMBEDDDING """

def json_embeddings(
                    MERGE: str,
                    json_file_path: str, 
                    torch_path: str, 
                    schema_path: str, 
                    model, 
                    device: torch.device, 
                    DATA_KEY: str, 
                    EMBE_KEY: str,
                    batches: bool = False) -> None:
    
    # Kiểm tra nếu file embedding đã tồn tại
    if os.path.exists(torch_path):
        print(f"\nEmbedding loaded from {torch_path}\n")
        return

    print(f"\nCreating embeddings for JSON data...\n")
    try:
        # Đọc schema
        schema = load_schema(schema_path)
        if not schema:
            raise ValueError("Schema is empty or invalid")

        # Đọc file JSON
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data_pairs = json.load(f)

        if not isinstance(data_pairs, list):
            data_pairs = [data_pairs]

        # Xử lý từng bộ JSON
        output_data = []
        for data in data_pairs:
            # Tiền xử lý văn bản
            flat_data = flatten_json(data)
            for key, value in flat_data.items():
                if isinstance(value, (str, list)):
                    flat_data[key] = preprocess_text(value)
            
            # Khôi phục cấu trúc gốc với dữ liệu đã tiền xử lý
            processed_data = data.copy()
            for key, value in flat_data.items():
                keys = key.split('.')
                current = processed_data
                for k in keys[:-1]:
                    current = current[k]
                current[keys[-1]] = value

            # Tạo embedding
            result = create_embeddings(MERGE, processed_data, schema, model, device, batches)
            output_data.append(result)

        # Lưu embedding riêng vào file .pt
        embeddings_only = []
        # datas_only =[]
        for item in output_data:
            flat_item = flatten_json(item)
            if MERGE == "Merge":
                # data_dict = {k: v for k, v in flat_item.items() if not k == "Merged_embedding"}
                embed_dict = {k: v for k, v in flat_item.items() if k == "Merged_embedding"}
            else:
                # data_dict = {k: v for k, v in flat_item.items() if not k.endswith("Embedding")}
                embed_dict = {k: v for k, v in flat_item.items() if k.endswith("Embedding")}
            # datas_only.append(data_dict)
            embeddings_only.append(embed_dict)


        torch.save({
            f"{DATA_KEY}": output_data,
            f"{EMBE_KEY}": embeddings_only
        }, torch_path)

        print(f"Embedding tensor saved to {torch_path}")

    except Exception as e:
        print(f"Error processing JSON with embeddings: {e}")
        raise
