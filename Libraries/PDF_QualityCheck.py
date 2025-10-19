import fitz
import re
from typing import Tuple, Dict, Union

class PDFQualityChecker:
    """
    Bộ lọc chất lượng PDF cơ bản trước khi xử lý.
    Đánh giá lỗi font, lỗi encode, ký tự hỏng, OCR kém, v.v.
    """

    def __init__(self, 
                 max_invalid_ratio: float = 0.2,
                 max_whitespace_ratio: float = 0.2,
                 max_short_line_ratio: float = 0.3,
                 min_total_chars: int = 300):
        self.max_invalid_ratio = max_invalid_ratio
        self.max_whitespace_ratio = max_whitespace_ratio
        self.max_short_line_ratio = max_short_line_ratio
        self.min_total_chars = min_total_chars

        # Regex nhận diện ký tự hợp lệ (chữ, số, dấu tiếng Việt, ký hiệu cơ bản)
        self.valid_char_pattern = re.compile(r"[A-Za-zÀ-ỹĐđ0-9.,:;!?()\"'’”“–\-_\s]")

    # ============================================================
    # 1️⃣  HÀM CHÍNH
    # ============================================================
    def evaluate(self, pdf: Union[str, fitz.Document]) -> Tuple[bool, Dict]:
        """
        Đánh giá chất lượng PDF.
        - pdf: đường dẫn (str) hoặc fitz.Document đã mở
        - trả (is_good, metrics)
        """
        # ---- Chuẩn hóa input ----
        if isinstance(pdf, str):
            try:
                doc = fitz.open(pdf)
            except Exception as e:
                return False, {"status": f"❌ Không mở được file: {e}"}
        elif isinstance(pdf, fitz.Document):
            doc = pdf
        else:
            raise TypeError("pdf phải là str hoặc fitz.Document")

        # ---- Bắt đầu thống kê ----
        text_all = ""
        short_lines = 0
        all_lines = 0

        for page in doc:
            text = page.get_text("text") or ""
            if not text.strip():
                continue
            lines = text.splitlines()
            for line in lines:
                if not line.strip():
                    continue
                all_lines += 1
                if len(line.strip()) < 10:
                    short_lines += 1
            text_all += text + "\n"

        total_chars = len(text_all)
        if total_chars < self.min_total_chars:
            return False, {
                "status": "❌ File quá ngắn hoặc không có text layer",
                "total_chars": total_chars,
            }

        # ---- Tính tỷ lệ lỗi ----
        valid_chars = sum(1 for ch in text_all if self.valid_char_pattern.match(ch))
        invalid_chars = total_chars - valid_chars
        invalid_ratio = invalid_chars / total_chars

        whitespace_excess = len(re.findall(r" {3,}", text_all))
        whitespace_ratio = whitespace_excess / total_chars

        short_line_ratio = short_lines / max(all_lines, 1)

        # ---- Đưa ra kết luận ----
        is_good = (
            invalid_ratio <= self.max_invalid_ratio
            and whitespace_ratio <= self.max_whitespace_ratio
            and short_line_ratio <= self.max_short_line_ratio
        )

        if not is_good:
            if invalid_ratio > self.max_invalid_ratio:
                status = "❌ Nhiều ký tự lỗi / encode sai"
            elif whitespace_ratio > self.max_whitespace_ratio:
                status = "❌ Nhiều khoảng trắng thừa"
            elif short_line_ratio > self.max_short_line_ratio:
                status = "⚠️ OCR hoặc mất ký tự"
            else:
                status = "❌ Văn bản lỗi nặng"
        else:
            status = "✅ Đạt yêu cầu"

        metrics = {
            "status": status,
            "total_chars": total_chars,
            "invalid_ratio": round(invalid_ratio, 3),
            "whitespace_ratio": round(whitespace_ratio, 3),
            "short_line_ratio": round(short_line_ratio, 3),
        }
        return is_good, metrics
