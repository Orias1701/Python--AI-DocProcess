import os
import json
import torch

""" CHECK EMBEDDDING CONTRUCTION """


def print_json(DATA_KEY: str, pt_path: str) -> None:
    try:
        if not os.path.exists(pt_path):
            print(f"File không tồn tại: {pt_path}")
            return

        data = torch.load(pt_path, map_location="cpu", weights_only=False)

        if isinstance(data, dict) and f"{DATA_KEY}" in data:
            content = data[f"{DATA_KEY}"]
        else:
            print(f"Dữ liệu không đúng định dạng: không tìm thấy key '{DATA_KEY}'")
            return

        if not isinstance(content, list) or not content:
            print("Dữ liệu rỗng hoặc không phải danh sách")
            return

        first_json = content[0]

        def process_json(obj: any) -> any:
            if isinstance(obj, dict):
                return {k: process_json(v) for k, v in obj.items()}
            elif isinstance(obj, list) and all(isinstance(x, (float, int)) for x in obj):
                return len(obj)
            elif isinstance(obj, list):
                return [process_json(item) for item in obj]
            return obj

        processed_json = process_json(first_json)

        print(json.dumps(processed_json, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"Lỗi khi đọc file .pt: {str(e)}")
