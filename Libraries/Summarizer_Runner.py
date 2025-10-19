import torch
from typing import List, Dict
from . import Json_ChunkUnder


class RecursiveSummarizer:
    """
    Bộ tóm tắt học thuật tiếng Việt theo hướng:
    Extractive (chunk semantic) + Abstractive (recursive summarization)
    """

    def __init__(
        self,
        tokenizer,
        summarizer,
        sum_device: str,
        chunk_builder: Json_ChunkUnder.ChunkUndertheseaBuilder,
        max_length: int = 256,
        min_length: int = 64,
        max_depth: int = 5
    ):
        """
        tokenizer: AutoTokenizer đã load sẵn.
        summarizer: AutoModelForSeq2SeqLM (ViT5 / BartPho / mT5)
        sum_device: 'cuda' hoặc 'cpu'
        chunk_builder: ChunkUndertheseaBuilder instance.
        """
        self.tokenizer = tokenizer
        self.model = summarizer
        self.device = sum_device
        self.chunk_builder = chunk_builder
        self.max_length = max_length
        self.min_length = min_length
        self.max_depth = max_depth

    # ============================================================
    # 1️⃣ Hàm tóm tắt 1 đoạn
    # ============================================================
    def summarize_single(self, text: str) -> str:
        """
        Tóm tắt 1 đoạn đơn bằng mô hình abstractive (ViT5/BartPho).
        """
        if not text or len(text.strip()) == 0:
            return ""

        if "vit5" in str(self.model.__class__).lower():
            input_text = f"vietnews: {text.strip()} </s>"
        else:
            input_text = text.strip()

        try:
            inputs = self.tokenizer(
                input_text,
                return_tensors="pt",
                truncation=True,
                max_length=1024
            ).to(self.device)

            with torch.no_grad():
                summary_ids = self.model.generate(
                    **inputs,
                    max_length=self.max_length,
                    min_length=self.min_length,
                    num_beams=4,
                    no_repeat_ngram_size=3,
                    early_stopping=True
                )

            summary = self.tokenizer.decode(summary_ids[0], skip_special_tokens=True)
            return summary.strip()

        except torch.cuda.OutOfMemoryError:
            print("⚠️ GPU OOM – fallback sang CPU.")
            self.model = self.model.to("cpu")
            inputs = inputs.to("cpu")

            with torch.no_grad():
                summary_ids = self.model.generate(
                    **inputs,
                    max_length=self.max_length,
                    min_length=self.min_length,
                    num_beams=4
                )

            return self.tokenizer.decode(summary_ids[0], skip_special_tokens=True).strip()

        except Exception as e:
            print(f"❌ Lỗi khi tóm tắt đoạn: {e}")
            return ""

    # ============================================================
    # 2️⃣ Đệ quy tóm tắt văn bản dài
    # ============================================================
    def summarize_recursive(self, text: str, depth: int = 0, minInput: int = 256, maxInput: int = 1024) -> str:
        """
        Đệ quy tóm tắt văn bản dài:
        - <256 từ: giữ nguyên
        - <1024 từ: tóm tắt trực tiếp
        - >=1024 từ: chia chunk + tóm tắt từng phần → gộp → đệ quy
        """
        word_count = len(text.split())
        indent = "  " * depth
        print(f"{indent}🔹 Level {depth}: {word_count} từ")

        # 1️⃣ Văn bản ngắn
        if word_count < minInput:
            return self.summarize_single(text)

        else:
            chunks = self.chunk_builder.build(text)
            summaries = []

            for item in chunks:
                content = item.get("Content", "")
                print(content)
                idx = item.get("Index", "?")
                wc = len(content.split())

                if wc < 20:
                    print(f"{indent}⚠️ Bỏ qua chunk {idx} (quá ngắn)")
                    continue

                print(f"{indent}🔸 Chunk {idx}: {wc} từ")
                sub_summary = self.summarize_single(content)
                if sub_summary:
                    summaries.append(sub_summary)

            merged_summary = "\n".join(summaries)
            merged_len = len(merged_summary.split())
            print(f"{indent}🔁 Gộp {len(summaries)} summary → {merged_len} từ")

            # Đệ quy nếu vẫn dài
            if merged_len > 1024 and depth < self.max_depth:
                return self.summarize_recursive(merged_summary, depth + 1)
            else:
                return merged_summary

    # ============================================================
    # 3️⃣ Hàm chính cho người dùng
    # ============================================================
    def summarize(self, full_text: str, minInput: int = 256, maxInput: int = 1024) -> Dict[str, str]:
        """
        Giao diện chính:
        - Nhận text dài
        - Tự động chia chunk, tóm tắt, gộp
        - Trả về dict gồm summary và thống kê
        """
        original_len = len(full_text.split())
        summary = self.summarize_recursive(full_text, depth = 0, minInput = minInput, maxInput = maxInput)

        summary_len = len(summary.split())
        ratio = round(summary_len / original_len, 3) if original_len else 0

        print(f"\n✨ FINAL SUMMARY ({summary_len}/{original_len} từ, r={ratio}) ✨")
        return {
            "summary_text": summary,
            "original_words": original_len,
            "summary_words": summary_len,
            "compression_ratio": ratio
        }
