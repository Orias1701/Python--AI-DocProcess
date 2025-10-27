"""
FastAPI gateway for your appCalled pipeline.

✅ Giữ nguyên pipeline gốc (appCalled.py)
✅ Tương thích Hugging Face Spaces (Docker)
✅ Có Bearer token, Swagger UI (/docs)
✅ Endpoint: /, /health, /process_pdf, /search, /summarize
"""

import os
import time
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# -------------------------
# 🔒 Bearer token (optional)
# -------------------------
API_SECRET = os.getenv("API_SECRET", "").strip()

def require_bearer(authorization: Optional[str] = Header(None)):
    """Kiểm tra Bearer token nếu bật API_SECRET."""
    if not API_SECRET:
        return  # Không bật xác thực
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != API_SECRET:
        raise HTTPException(status_code=403, detail="Invalid token")

# -------------------------
# 🧩 Import project modules
# -------------------------
try:
    import appCalled as APP_CALLED
    print("✅ Đã load appCalled.")
except Exception as e:
    APP_CALLED = None
    print(f"⚠️ Không thể import appCalled: {e}")

# -------------------------
# 🚀 Init FastAPI
# -------------------------
app = FastAPI(
    title="Document AI API (FastAPI)",
    version="2.0.0",
    description="API xử lý PDF: trích xuất, tóm tắt, tìm kiếm, phân loại.",
)

# Cho phép gọi API từ web client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# 🏠 Root endpoint (tránh 404 trên Spaces)
# -------------------------
@app.get("/")
def root():
    """Trang chào mừng / kiểm tra trạng thái."""
    return {
        "message": "📘 Document AI API đang chạy.",
        "status": "ok",
        "docs": "/docs",
        "endpoints": ["/process_pdf", "/search", "/summarize", "/health"],
    }

# -------------------------
# 🩺 /health
# -------------------------
@app.get("/health")
def health(_=Depends(require_bearer)):
    """Kiểm tra trạng thái hoạt động."""
    return {
        "status": "ok",
        "time": time.time(),
        "appCalled": bool(APP_CALLED),
        "has_fileProcess": hasattr(APP_CALLED, "fileProcess") if APP_CALLED else False,
    }

# -------------------------
# 📘 /process_pdf
# -------------------------
@app.post("/process_pdf")
async def process_pdf(file: UploadFile = File(...), _=Depends(require_bearer)):
    """Nhận file PDF → chạy appCalled.fileProcess → trả về summary + category."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file PDF.")

    pdf_bytes = await file.read()

    if not APP_CALLED or not hasattr(APP_CALLED, "fileProcess"):
        raise HTTPException(status_code=500, detail="Không tìm thấy appCalled.fileProcess().")

    try:
        result = APP_CALLED.fileProcess(pdf_bytes)
        return {
            "status": "success",
            "checkstatus": result.get("checkstatus"),
            "summary": result.get("summary"),
            "category": result.get("category"),
            "top_candidates": result.get("reranked", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý PDF: {str(e)}")

# -------------------------
# 🔍 /search
# -------------------------
class SearchIn(BaseModel):
    query: str
    k: int = 10

@app.post("/search")
def search(body: SearchIn, _=Depends(require_bearer)):
    """Tìm kiếm bằng FAISS + Rerank từ appCalled.runSearch()."""
    q = (body.query or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="query không được để trống")

    if not APP_CALLED or not hasattr(APP_CALLED, "runSearch"):
        raise HTTPException(status_code=500, detail="Không tìm thấy appCalled.runSearch().")

    try:
        results = APP_CALLED.runSearch(q)
        if isinstance(results, list):
            formatted = results[:body.k]
        elif isinstance(results, dict) and "results" in results:
            formatted = results["results"][:body.k]
        else:
            formatted = [str(results)]
        return {"status": "success", "results": formatted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tìm kiếm: {str(e)}")

# -------------------------
# 🧠 /summarize
# -------------------------
class SummIn(BaseModel):
    text: str
    minInput: int = 256
    maxInput: int = 1024

@app.post("/summarize")
def summarize_text(body: SummIn, _=Depends(require_bearer)):
    """Tóm tắt văn bản bằng appCalled.summarizer_engine."""
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text không được để trống")

    if not APP_CALLED or not hasattr(APP_CALLED, "summarizer_engine"):
        raise HTTPException(status_code=500, detail="Không tìm thấy appCalled.summarizer_engine.")

    try:
        summarized = APP_CALLED.summarizer_engine.summarize(
            text, minInput=body.minInput, maxInput=body.maxInput
        )
        return {"status": "success", "summary": summarized.get("summary_text", "")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tóm tắt: {str(e)}")
