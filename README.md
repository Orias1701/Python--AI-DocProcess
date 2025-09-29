# Hệ thống Chatbot RAG Quy chế Đào tạo

## 1. Mục tiêu

Hệ thống này xây dựng pipeline xử lý PDF quy chế đào tạo để trích xuất, chuẩn hoá và phân cấp dữ liệu, sau đó sinh embedding và nạp vào FAISS cho chatbot  **RAG (Retrieval-Augmented Generation)**

---

## 2. Kiến trúc tổng quan

Pipeline gồm 3 tầng:

1. **Tiền xử lý văn bản (A0–B4)**
   * Từ PDF → Lines → Paragraphs → Structures → Chunks.
2. **Schema & Embedding (C1–C3)**
   * Sinh schema → tạo embedding → kiểm tra dữ liệu.
3. **Vector Index (D0)**
   * Chuyển đổi `.pt` embedding → FAISS Index + mapping.

---

## 3. Thành phần & Chức năng

### A. Tiền xử lý

* **A0_MyUtils** : Utils đọc/ghi JSON, CSV, Excel; chuẩn hóa text; flatten JSON.
* **A1_TextProcess** : xử lý tiếng Việt, viết tắt, La Mã.
* **A2_PdfProcess** : phân tích font, style, vị trí từ / dòng / trang.
* **B1_ExtractData** : trích xuất lines từ PDF, gắn Marker, Style, Align.
* **B2_MergeData** : gộp lines thành paragraphs theo luật (FontSize, Style, khoảng cách, Align).
* **B3_GetStructures** : phân tích Marker để tạo cấu trúc Levels và Contents.
* **B4_ChunkMaster** : xây dựng Chunks theo cấu trúc, đầu ra `chunks.json`.

**Kết quả:** dữ liệu chunks phân cấp (Index, Levels, Contents) sẵn sàng cho embedding.

---

### B. Schema & Embedding

**C1_CreateSchema**:

* Sinh schema từ JSON (key phẳng `a.b.c`).
* Hỗ trợ chính sách list `"first"` hoặc `"union"`.
* Kiểu dữ liệu: number, string, boolean, array, object, null, mixed.

**C2_Embedding**:

* Sinh embedding từ JSON theo schema.
* Flatten dữ liệu, chọn field hợp lệ.
* Batch encode bằng model.
* Xuất `.pt` chứa `{DATA: [...], EMBEDDINGS: [...]}`.

**C3_CheckStruct**:

* Kiểm tra file `.pt`.
* In thử để ktra.

---

### C. FAISS

* **D0_FaissConvert**:

  * Đọc file `.pt`, trích xuất embedding + data.
  * Tạo FAISS Index (IndexFlatIP).
  * Xuất:
    * `index.faiss`: chỉ mục - Index.
    * `mapping.json`: ánh xạ key → index.
    * `data.json`: dữ liệu gốc - Key + data.

---

## 4. Quy trình

1. **Extract & Chunk**
   * PDF → `lines.json` → `merged.json` → `struct.json` → `chunks.json`.
2. **Schema & Embedding**
   * Tạo schema từ chunks: `schema.json`.
   * Sinh embedding: `chunks.pt`.
3. **Kiểm tra embedding**
   * Dùng `C3_CheckStruct` để in và xác minh dữ liệu trong `chunks.pt`.
4. **Chuyển sang FAISS**
   * Chạy `D0_FaissConvert` để tạo FAISS Index + mapping.

---

## 5. Output

| Bước    | Output    | Nội dung                          |
| --------- | --------- | ---------------------------------- |
| Extract   | `json`  | Text, marker, style, align         |
| Merge     | `json`  | Paragraphs                         |
| Structu   | `json`  | Cấu trúc Levels                  |
| Chunk     | `json`  | Chunks phân cấp                  |
| Schema    | `json`  | Kiểu dữ liệu                    |
| Embedding | `pt`    | Data + embeddings                  |
| FAISS     | `faiss` | Chỉ mục tìm kiếm               |
| Mapping   | `json`  | Ánh xạ key-index, dữ liệu gốc |

---

## 6. Tích hợp RAG

1. **Nhận Queries:** Yêu cầu người dùng nhập câu hỏi.
2. **Embedding:** Chuyển Query thành vector.
3. **Search:** So sánh tích vô hướng Query - index, tìm top 10
4. **Rerank:** Dùng Rerank models để sắp xếp lại theo tương đồng ngữ nghĩa
5. **Respond:** Dùng LLM để trả lời tự nhiên dưa trên kết quả Rerank

---
