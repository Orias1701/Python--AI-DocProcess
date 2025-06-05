import os
import json
import torch

def print_json(DATA_KEY: str, EMBE_KEY: str, pt_path: str) -> None:
    """
    In ra bộ dữ liệu đầu tiên từ DATA_KEY và EMBE_KEY trong file .pt.

    Args:
        DATA_KEY: Khóa chứa dữ liệu văn bản (ví dụ: 'contents').
        EMBE_KEY: Khóa chứa dữ liệu embedding (ví dụ: 'embeddings').
        pt_path: Đường dẫn tới file .pt.
    """
    try:
        # Kiểm tra file .pt tồn tại
        if not os.path.exists(pt_path):
            print(f"File không tồn tại: {pt_path}")
            return

        # Tải file .pt
        data = torch.load(pt_path, map_location="cpu", weights_only=False)

        # Hàm xử lý JSON để in dữ liệu dạng cây
        def process_json(obj: any) -> any:
            if isinstance(obj, dict):
                return {k: process_json(v) for k, v in obj.items()}
            elif isinstance(obj, list) and all(isinstance(x, (float, int)) for x in obj):
                return len(obj)  # Thay danh sách số bằng độ dài
            elif isinstance(obj, list):
                return [process_json(item) for item in obj]
            return obj

        # Xử lý DATA_KEY
        if isinstance(data, dict) and f"{DATA_KEY}" in data:
            content = data[f"{DATA_KEY}"]
            if not isinstance(content, list) or not content:
                print(f"Dữ liệu rỗng hoặc không phải danh sách cho '{DATA_KEY}'")
            else:
                first_json = content[0]
                processed_json = process_json(first_json)
                print(f"Bộ dữ liệu đầu tiên từ '{DATA_KEY}':")
                print(json.dumps(processed_json, ensure_ascii=False, indent=2))
        else:
            print(f"Dữ liệu không đúng định dạng: không tìm thấy key '{DATA_KEY}'")

        # Xử lý EMBE_KEY
        if isinstance(data, dict) and f"{EMBE_KEY}" in data:
            embeddings = data[f"{EMBE_KEY}"]
            if not isinstance(embeddings, list) or not embeddings:
                print(f"Dữ liệu rỗng hoặc không phải danh sách cho '{EMBE_KEY}'")
            else:
                first_embedding = embeddings[0]
                if isinstance(first_embedding, torch.Tensor):
                    # Chuyển tensor thành list và lấy thông tin cơ bản
                    embedding_info = {
                        "shape": list(first_embedding.shape),
                        "dtype": str(first_embedding.dtype),
                        "sample_values": first_embedding.flatten()[:5].tolist()  # In 5 giá trị đầu tiên
                    }
                    print(f"\nBộ embedding đầu tiên từ '{EMBE_KEY}':")
                    print(json.dumps(embedding_info, ensure_ascii=False, indent=2))
                else:
                    # Xử lý trường hợp EMBE_KEY không phải tensor
                    processed_embedding = process_json(first_embedding)
                    print(f"\nBộ embedding đầu tiên từ '{EMBE_KEY}':")
                    print(json.dumps(processed_embedding, ensure_ascii=False, indent=2))
        else:
            print(f"Dữ liệu không đúng định dạng: không tìm thấy key '{EMBE_KEY}'")

    except Exception as e:
        print(f"Lỗi khi đọc file .pt: {str(e)}")

# Ví dụ sử dụng
if __name__ == "__main__":
    DATA_KEY = "contents"
    EMBE_KEY = "embeddings"
    pt_path = "path/to/your_file.pt"  # Thay bằng đường dẫn thực tế
    print_json(DATA_KEY, EMBE_KEY, pt_path)