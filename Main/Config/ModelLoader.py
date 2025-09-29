import torch
from transformers import AutoTokenizer, AutoModel
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

def load_auto_model(path_or_name, device):
    try:
        tokenizer = AutoTokenizer.from_pretrained(path_or_name)
        model = AutoModel.from_pretrained(path_or_name).to(device)
        return tokenizer, model
    except (OSError, FileNotFoundError) as e:
        print("❌ Model files missing:", e)
        return None, None
    except RuntimeError as e:
        print("⚠️ GPU issue, fallback to CPU:", e)
        tokenizer = AutoTokenizer.from_pretrained(path_or_name)
        model = AutoModel.from_pretrained(path_or_name).to("cpu")
        return tokenizer, model
    except Exception as e:
        print("❌ Unexpected error:", e)
        raise

def load_sentence_model(path_or_name, device):
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
