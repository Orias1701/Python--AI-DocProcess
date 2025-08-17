import json
from typing import Any, Dict

""" DATA TYPE """

def get_standard_type(value: Any) -> str:
    if isinstance(value, int):
        return "number"
    elif isinstance(value, float):
        return "number"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    elif value is None:
        return "null"
    return "unknown"

""" EXTRACT SCHEMA """

def extract_schema(data: Any, prefix: str = "", schema: Dict[str, str] = None) -> Dict[str, str]:
    """Đệ quy phân tích cấu trúc JSON để tạo schema."""
    if schema is None:
        schema = {}
    
    if isinstance(data, dict):
        for key, value in data.items():
            new_prefix = f"{prefix}{key}" if prefix else key
            schema[new_prefix] = get_standard_type(value)
            if isinstance(value, dict):
                extract_schema(value, f"{new_prefix}.", schema)
            elif isinstance(value, list) and value:
                if isinstance(value[0], (dict, list)):
                    extract_schema(value[0], f"{new_prefix}.", schema)
    return schema

""" CREATE SCHEMA"""

def create_schema(json_file_path: str, schema_path: str) -> Dict[str, str]:
    """Tạo schema từ tất cả các bộ JSON, kiểm tra trường đã xét và kiểu dữ liệu trả về."""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Nếu không phải list, chuyển thành list
        if not isinstance(data, list):
            data = [data]
        
        # Kiểm tra nếu JSON rỗng
        if not data:
            raise ValueError("JSON data is empty")

        # Kiểm tra từng phần tử trong list, đảm bảo chúng là dict
        for i, item in enumerate(data, 1):
            if not isinstance(item, dict):
                print(f"Item {i} is not a dict: {type(item)}")

        processed_fields = set()
        full_schema = {}
        
        print("\nChecking fields and their types:")

        # Duyệt qua từng phần tử trong dữ liệu
        for i, item in enumerate(data, 1):
            if not isinstance(item, dict):
                print(f"Skipping item {i}: Not a dict ({type(item)})")
                continue

            # Trích xuất schema từ phần tử hiện tại
            schema = extract_schema(item)

            # Duyệt qua các trường trong schema
            for key, value in schema.items():
                # Nếu trường chưa có trong tập hợp thì lưu vào processed_fields
                if key not in processed_fields:
                    print(f"New: {key:15} item {i}: Type = {value}")
                    processed_fields.add(key)
                    
                # Cập nhật schema đầy đủ
                if key not in full_schema:
                    full_schema[key] = value

                # Xử lý trường hợp mixed với null
                elif full_schema[key] != value:
                    if value == "null":
                        # Nếu giá trị hiện tại là null, giữ nguyên kiểu cũ
                        print(f"Field '{key}' has null value in item {i}, keeping type: {full_schema[key]}")
                    elif full_schema[key] == "null":
                        # Nếu kiểu cũ là null, lấy kiểu mới (không phải null)
                        print(f"Field '{key}' has non-null value in item {i}, updating type to: {value}")
                        full_schema[key] = value
                    elif full_schema[key] != "mixed":
                        # Nếu không phải null và có sự khác biệt, đánh dấu là mixed
                        print(f"Warning: Field '{key}' has multiple types: {full_schema[key]} and {value}")
                        full_schema[key] = "mixed"
                           
        with open(schema_path, 'w', encoding='utf-8') as f:
            json.dump(full_schema, f, ensure_ascii=False, indent=2)
        
        print("Generated schema:")
        print(json.dumps(full_schema, ensure_ascii=False, indent=2))
        return full_schema
    
    except Exception as e:
        print(f"Error creating schema: {e}")
        return {}