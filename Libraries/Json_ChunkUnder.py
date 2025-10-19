import re
import numpy as np
import torch
from underthesea import sent_tokenize


class ChunkUndertheseaBuilder:
    """
    Bộ tách văn bản tiếng Việt thông minh:
      1️⃣ Lọc trước (Extractive): chỉ giữ các câu có ý chính
      2️⃣ Gộp sau (Semantic): nhóm các câu trọng tâm theo ngữ nghĩa
    """

    def __init__(self,
                 embedder,
                 device: str = "cpu",
                 min_words: int = 256,
                 max_words: int = 768,
                 sim_threshold: float = 0.7,
                 key_sent_ratio: float = 0.4):
        if embedder is None:
            raise ValueError("❌ Cần truyền mô hình embedder đã load sẵn.")
        self.embedder = embedder
        self.device = device
        self.min_words = min_words
        self.max_words = max_words
        self.sim_threshold = sim_threshold
        self.key_sent_ratio = key_sent_ratio

    # ============================================================
    # 1️⃣ Tách câu
    # ============================================================
    def _split_sentences(self, text: str):
        """Tách câu tiếng Việt (fallback nếu underthesea lỗi)."""
        text = re.sub(r"[\x00-\x1f]+", " ", text)
        try:
            sents = sent_tokenize(text)
        except Exception:
            sents = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sents if len(s.strip()) > 2]

    # ============================================================
    # 2️⃣ Encode an toàn (GPU/CPU fallback)
    # ============================================================
    def _encode(self, sentences):
        try:
            return self.embedder.encode(
                sentences,
                convert_to_numpy=True,
                show_progress_bar=False,
                device=str(self.device)
            )
        except TypeError:
            return self.embedder.encode(sentences, convert_to_numpy=True, show_progress_bar=False)
        except RuntimeError as e:
            if "CUDA" in str(e):
                print("⚠️ GPU OOM, fallback sang CPU.")
                return self.embedder.encode(
                    sentences, convert_to_numpy=True, show_progress_bar=False, device="cpu"
                )
            raise e

    # ============================================================
    # 3️⃣ Lọc ý chính trước (EXTRACTIVE)
    # ============================================================
    def _extractive_filter(self, sentences):
        """Chọn ra top-k câu đại diện nội dung nhất."""
        if len(sentences) <= 3:
            return sentences

        embeddings = self._encode(sentences)
        mean_vec = np.mean(embeddings, axis=0)
        sims = np.dot(embeddings, mean_vec) / (
            np.linalg.norm(embeddings, axis=1) * np.linalg.norm(mean_vec)
        )

        # Chọn top-k câu có similarity cao nhất
        k = max(1, int(len(sentences) * self.key_sent_ratio))
        idx = np.argsort(-sims)[:k]
        idx.sort()  # giữ thứ tự gốc
        selected = [sentences[i] for i in idx]
        return selected

    # ============================================================
    # 4️⃣ Gộp các câu trọng tâm theo ngữ nghĩa
    # ============================================================
    def _semantic_group(self, sentences):
        """Gộp các câu đã lọc theo mức tương đồng ngữ nghĩa."""
        if not sentences:
            return []

        embeddings = self._encode(sentences)
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

        chunks, cur_chunk, cur_len = [], [], 0
        for i, sent in enumerate(sentences):
            wc = len(sent.split())
            if not cur_chunk:
                cur_chunk.append(sent)
                cur_len = wc
                continue

            sim = np.dot(embeddings[i - 1], embeddings[i])
            too_long = cur_len + wc > self.max_words
            too_short = cur_len < self.min_words
            topic_changed = sim < self.sim_threshold

            if too_long or (not too_short and topic_changed):
                chunks.append(" ".join(cur_chunk))
                cur_chunk = [sent]
                cur_len = wc
            else:
                cur_chunk.append(sent)
                cur_len += wc

        if cur_chunk:
            chunks.append(" ".join(cur_chunk))
        return chunks

    # ============================================================
    # 5️⃣ Hàm chính build()
    # ============================================================
    def build(self, full_text: str):
        """
        Trả về list chứa {Index, Content} cho từng chunk.
        Quy trình:
            - Lọc câu trọng tâm trước
            - Gộp các câu đã lọc theo ngữ nghĩa
        """
        all_sentences = self._split_sentences(full_text)
        print(f"📄 Tổng số câu: {len(all_sentences)}")

        # --- Bước 1: lọc ý chính ---
        filtered = self._extractive_filter(all_sentences)
        print(f"✨ Giữ lại {len(filtered)} câu (~{len(filtered)/len(all_sentences):.0%}) sau extractive filter")

        # --- Bước 2: gộp thành các đoạn ngữ nghĩa ---
        chunks = self._semantic_group(filtered)
        results = [{"Index": i, "Content": chunk} for i, chunk in enumerate(chunks, start=1)]

        print(f"🔹 Tạo {len(results)} chunk ngữ nghĩa từ {len(filtered)} câu trọng tâm.")
        return results
