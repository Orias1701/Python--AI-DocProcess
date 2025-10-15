import os
import shutil
import torch
from sentence_transformers import SentenceTransformer

def CudaCheck():
    print("CUDA supported:", torch.cuda.is_available())
    print("Number of GPUs:", torch.cuda.device_count())
    if torch.cuda.is_available():
        print("Current GPU name:", torch.cuda.get_device_name(0))
        print("CUDA device capability:", torch.cuda.get_device_capability(0))
        print("CUDA version (PyTorch):", torch.version.cuda)
        print("cuDNN version:", torch.backends.cudnn.version())
    else:
        print("CUDA not available.")


def load_sentence_model(path_or_name, device):
    """Load model SentenceTransformer with fallback CPU if GPU error."""
    try:
        return SentenceTransformer(path_or_name, device=str(device))
    except (OSError, FileNotFoundError) as e:
        print("❌ Model files missing:", e)
        return None
    except RuntimeError as e:
        print("⚠️ GPU issue, fallback to CPU:", e)
        return SentenceTransformer(path_or_name, device="cpu")
    except Exception as e:
        print("❌ Unexpected error:", e)
        raise


def ensure_cached_model(model_name: str, cached_path: str):
    """
    Tải model từ HuggingFace nếu cache chưa có.
    Chuẩn hoá thành cấu trúc SentenceTransformers hợp lệ.
    """
    if not os.path.exists(cached_path):
        print(f"📥 Downloading and caching model to {cached_path} ...")
        model = SentenceTransformer(model_name)
        model.save(cached_path)
        print("✅ Model cached successfully.")
    else:
        # Kiểm tra xem cấu trúc có hợp lệ chưa
        cfg_file = os.path.join(cached_path, "config_sentence_transformers.json")
        if not os.path.exists(cfg_file):
            print("⚙️ Rebuilding SentenceTransformers structure in cache...")
            tmp_model = SentenceTransformer(model_name)
            tmp_model.save(cached_path)
    return cached_path


def init_sentence_model(EMBEDD_MODEL: str, cached_path: str = None):
    """
    Gộp toàn bộ logic:
    - Kiểm tra CUDA và chọn device
    - Ưu tiên load model từ cached_path (tạo nếu chưa có)
    - Tự fallback CPU nếu GPU không khả dụng
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("\n🔍 Checking CUDA and GPU status...")
    CudaCheck()

    # Nếu có cache path → đảm bảo hợp lệ
    if cached_path:
        os.makedirs(cached_path, exist_ok=True)
        ensure_cached_model(EMBEDD_MODEL, cached_path)
        print(f"ℹ️ Sentence Transformer cached at: {cached_path}")
        model = load_sentence_model(cached_path, device)
    else:
        print(f"ℹ️ Sentence Transformer: {EMBEDD_MODEL}")
        model = load_sentence_model(EMBEDD_MODEL, device)

    print(f"✅ Using device: {device}")
    return model, device
