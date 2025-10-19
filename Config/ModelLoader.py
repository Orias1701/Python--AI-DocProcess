# ============================================================
# Config/ModelLoader.py  —  Official, unified, complete
# - Manage Encoder/Chunker (SentenceTransformer) and Summarizer (Seq2Seq)
# - Auto-download to local cache when missing
# - GPU/CPU selection with CUDA checks
# - Consistent class-based API
# ============================================================

import os
import torch
from typing import List, Tuple, Optional, Dict, Any

from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM


class ModelLoader:
    """
    Unified model manager:
      - Encoder (SentenceTransformer)
      - Chunker (SentenceTransformer)
      - Summarizer (Seq2Seq: T5/BART/vit5)
    Provides:
      - load_encoder(name, cache)
      - load_chunker(name, cache)
      - load_summarizer(name, cache)
      - summarize(text, max_len, min_len)
      - summarize_batch(texts, max_len, min_len)
      - print_devices()
    """

    # -----------------------------
    # Construction / State
    # -----------------------------
    def __init__(self, prefer_cuda: bool = True) -> None:
        self.models: Dict[str, Any] = {}
        self.tokenizers: Dict[str, Any] = {}
        self.devices: Dict[str, torch.device] = {}
        self.prefer_cuda = prefer_cuda

    # -----------------------------
    # Device helpers
    # -----------------------------
    @staticmethod
    def _cuda_check() -> None:
        print("CUDA supported:", torch.cuda.is_available())
        print("Number of GPUs:", torch.cuda.device_count())
        if torch.cuda.is_available():
            print("Current GPU:", torch.cuda.get_device_name(0))
            print("Capability:", torch.cuda.get_device_capability(0))
            print("CUDA version (PyTorch):", torch.version.cuda)
            print("cuDNN version:", torch.backends.cudnn.version())
        else:
            print("⚠️ CUDA not available, using CPU.")

    def _get_device(self) -> torch.device:
        if self.prefer_cuda and torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")

    @staticmethod
    def _ensure_dir(path: Optional[str]) -> None:
        if path:
            os.makedirs(path, exist_ok=True)

    # -----------------------------
    # SentenceTransformer (Encoder/Chunker)
    # -----------------------------
    @staticmethod
    def _ensure_cached_sentence_model(model_name: str, cache_path: str) -> str:
        """
        Ensure SentenceTransformer exists under cache_path.
        Rebuild structure if config missing.
        """
        if not os.path.exists(cache_path):
            print(f"📥 Downloading SentenceTransformer to: {cache_path}")
            model = SentenceTransformer(model_name)
            model.save(cache_path)
            print("✅ Cached SentenceTransformer successfully.")
        else:
            cfg = os.path.join(cache_path, "config_sentence_transformers.json")
            if not os.path.exists(cfg):
                print("⚙️ Rebuilding SentenceTransformer cache structure...")
                tmp = SentenceTransformer(model_name)
                tmp.save(cache_path)
        return cache_path

    def _load_sentence_model(self, model_name: str, cache_path: Optional[str]) -> Tuple[SentenceTransformer, torch.device]:
        device = self._get_device()
        print(f"\n🔍 Loading SentenceTransformer ({model_name}) on {device} ...")
        self._cuda_check()

        if cache_path:
            self._ensure_dir(cache_path)
            self._ensure_cached_sentence_model(model_name, cache_path)
            model = SentenceTransformer(cache_path, device=str(device))
            print(f"📂 Loaded from cache: {cache_path}")
        else:
            model = SentenceTransformer(model_name, device=str(device))

        print("✅ SentenceTransformer ready.")
        return model, device

    # Public APIs for SentenceTransformer
    def load_encoder(self, name: str, cache: Optional[str] = None) -> Tuple[SentenceTransformer, torch.device]:
        model, device = self._load_sentence_model(name, cache)
        self.models["encoder"] = model
        self.devices["encoder"] = device
        return model, device

    def load_chunker(self, name: str, cache: Optional[str] = None) -> Tuple[SentenceTransformer, torch.device]:
        model, device = self._load_sentence_model(name, cache)
        self.models["chunker"] = model
        self.devices["chunker"] = device
        return model, device

    # -----------------------------
    # Summarizer (Seq2Seq: T5/BART/vit5)
    # -----------------------------
    @staticmethod
    def _has_hf_config(cache_dir: str) -> bool:
        return os.path.exists(os.path.join(cache_dir, "config.json"))

    @staticmethod
    def _download_and_cache_summarizer(model_name: str, cache_dir: str) -> None:
        """
        Download HF model + tokenizer and save_pretrained to cache_dir.
        """
        print("⚙️ Cache missing — downloading model from Hugging Face...")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        os.makedirs(cache_dir, exist_ok=True)
        tokenizer.save_pretrained(cache_dir)
        model.save_pretrained(cache_dir)
        print(f"✅ Summarizer cached at: {cache_dir}")

    def _load_summarizer_core(self, model_or_dir: str, device: torch.device) -> Tuple[AutoTokenizer, AutoModelForSeq2SeqLM]:
        tokenizer = AutoTokenizer.from_pretrained(model_or_dir)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_or_dir).to(device)
        return tokenizer, model

    def load_summarizer(self, name: str, cache: Optional[str] = None) -> Tuple[AutoTokenizer, AutoModelForSeq2SeqLM, torch.device]:
        """
        Load Seq2Seq model; auto-download if cache dir missing or invalid.
        """
        device = self._get_device()
        print(f"\n🔍 Initializing summarizer ({name}) on {device} ...")
        self._cuda_check()

        if cache:
            self._ensure_dir(cache)
            if not self._has_hf_config(cache):
                self._download_and_cache_summarizer(name, cache)
            print("📂 Loading summarizer from local cache...")
            tok, mdl = self._load_summarizer_core(cache, device)
        else:
            print("🌐 Loading summarizer directly from Hugging Face (no cache dir provided)...")
            tok, mdl = self._load_summarizer_core(name, device)

        self.tokenizers["summarizer"] = tok
        self.models["summarizer"] = mdl
        self.devices["summarizer"] = device

        print(f"✅ Summarizer ready on {device}")
        return tok, mdl, device

    # -----------------------------
    # Summarization helpers
    # -----------------------------
    @staticmethod
    def _apply_vietnews_prefix(text: str, prefix: str, suffix: str) -> str:
        """
        For VietAI/vit5-vietnews: prefix 'vietnews: ' and suffix ' </s>'
        Safe for general T5-family; harmless for BART-family.
        """
        t = (text or "").strip()
        if not t:
            return ""
        return f"{prefix}{t}{suffix}"

    def summarize(self,
                  text: str,
                  max_len: int = 256,
                  min_len: int = 64,
                  prefix: str = "vietnews: ",
                  suffix: str = " </s>") -> str:
        """
        Summarize a single text with loaded summarizer.
        Raises RuntimeError if summarizer not loaded.
        """
        if "summarizer" not in self.models or "summarizer" not in self.tokenizers:
            raise RuntimeError("❌ Summarizer not loaded. Call load_summarizer() first.")

        model: AutoModelForSeq2SeqLM = self.models["summarizer"]
        tokenizer: AutoTokenizer = self.tokenizers["summarizer"]
        device: torch.device = self.devices["summarizer"]

        prepared = self._apply_vietnews_prefix(text, prefix, suffix)
        if not prepared:
            return ""

        encoding = tokenizer(
            prepared,
            return_tensors="pt",
            truncation=True,
            max_length=1024
        ).to(device)

        with torch.no_grad():
            outputs = model.generate(
                **encoding,
                max_length=max_len,
                min_length=min_len,
                num_beams=4,
                no_repeat_ngram_size=3,
                early_stopping=True
            )

        summary = tokenizer.decode(
            outputs[0],
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True
        )
        return summary

    def summarize_batch(self,
                        texts: List[str],
                        max_len: int = 256,
                        min_len: int = 64,
                        prefix: str = "vietnews: ",
                        suffix: str = " </s>") -> List[str]:
        """
        Batch summarization. Processes in a single forward pass when possible.
        """
        if "summarizer" not in self.models or "summarizer" not in self.tokenizers:
            raise RuntimeError("❌ Summarizer not loaded. Call load_summarizer() first.")

        model: AutoModelForSeq2SeqLM = self.models["summarizer"]
        tokenizer: AutoTokenizer = self.tokenizers["summarizer"]
        device: torch.device = self.devices["summarizer"]

        batch = [self._apply_vietnews_prefix(t, prefix, suffix) for t in texts]
        batch = [b for b in batch if b]  # drop empties
        if not batch:
            return []

        encoding = tokenizer(
            batch,
            return_tensors="pt",
            truncation=True,
            max_length=1024,
            padding=True
        ).to(device)

        summaries: List[str] = []
        with torch.no_grad():
            outputs = model.generate(
                **encoding,
                max_length=max_len,
                min_length=min_len,
                num_beams=4,
                no_repeat_ngram_size=3,
                early_stopping=True
            )
        for i in range(outputs.shape[0]):
            dec = tokenizer.decode(
                outputs[i],
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True
            )
            summaries.append(dec)
        return summaries

    # -----------------------------
    # Diagnostics
    # -----------------------------
    def print_devices(self) -> None:
        print("\n📊 Device summary:")
        for key, dev in self.devices.items():
            print(f"  - {key}: {dev}")
