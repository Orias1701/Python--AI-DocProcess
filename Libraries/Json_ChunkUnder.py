import re
import numpy as np
from underthesea import sent_tokenize


class ChunkUndertheseaBuilder:
    """
    Tách và gộp các đoạn văn bản tiếng Việt theo ngữ nghĩa,
    tạo ra các chunk có độ dài 400–900 từ.
    """

    def __init__(self,
                 embedder,
                 min_words: int = 512,
                 max_words: int = 1024,
                 sim_threshold: float = 0.7):
        """
        embedder: đối tượng SentenceTransformer đã load sẵn.
        min_words, max_words: giới hạn kích thước chunk.
        sim_threshold: ngưỡng cosine similarity để ngắt đoạn.
        """
        if embedder is None:
            raise ValueError("❌")
        self.embedder = embedder
        self.min_words = min_words
        self.max_words = max_words
        self.sim_threshold = sim_threshold

    # ============================================================
    # 1️⃣ Tách câu bằng underthesea
    # ============================================================
    def _split_sentences(self, text: str):
        """Tách câu tiếng Việt ổn định bằng underthesea."""
        sentences = sent_tokenize(text)
        return [s.strip() for s in sentences if len(s.strip()) > 2]

    # ============================================================
    # 2️⃣ Gộp câu thành các chunk ngữ nghĩa
    # ============================================================
    def _split_chunks(self, sentences):
        """Gộp các câu thành chunk theo ngữ nghĩa."""
        if not sentences:
            return []

        embeddings = self.embedder.encode(sentences, convert_to_numpy=True, show_progress_bar=False)
        chunks, current_chunk, current_len = [], [], 0

        for i, sent in enumerate(sentences):
            wc = len(sent.split())

            if not current_chunk:
                current_chunk.append(sent)
                current_len = wc
                continue

            sim = np.dot(embeddings[i - 1], embeddings[i]) / (
                np.linalg.norm(embeddings[i - 1]) * np.linalg.norm(embeddings[i])
            )

            too_long = current_len + wc > self.max_words
            too_short = current_len < self.min_words

            topic_changed = sim < self.sim_threshold

            if too_long or (not too_short and topic_changed):
                chunks.append(" ".join(current_chunk))
                current_chunk = [sent]
                current_len = wc
            else:
                current_chunk.append(sent)
                current_len += wc

        if current_chunk:
            chunks.append(" ".join(current_chunk))
        return chunks

    # ============================================================
    # 3️⃣ Hàm chính build()
    # ============================================================
    def build(self, full_text: str, merge = True):
        """Trả về list chứa {Index, Content} cho từng chunk."""
        sentences = self._split_sentences(full_text)
        if merge:
            chunks = self._split_chunks(sentences)
        else:
            chunks = sentences
        output = [{"Index": i, "Content": chunk} for i, chunk in enumerate(chunks, start=1)]
        return output
