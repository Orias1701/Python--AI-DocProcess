from typing import Any, Dict, List
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

""" RESPOND """

"""
Lọc kết quả rerank và sinh câu trả lời tự nhiên bằng Gemini 1.5 Pro.

Args:
    query: Câu hỏi dạng văn bản
    results: Danh sách kết quả từ rerank_results ({'text', 'rerank_score', 'faiss_score', 'key'})
    respond_model: Tên mô hình Gemini (mặc định gemini-2.0-flash-exp)
    device: Thiết bị PyTorch (cuda hoặc cpu, chỉ để tương thích)
    score_threshold: Ngưỡng rerank_score để lọc
    max_results: Số kết quả tối đa để tổng hợp
    gemini_api_key: API key của Google AI Studio

Returns:
    Tuple: (câu trả lời tự nhiên, danh sách kết quả được lọc)
"""

def respond_naturally(
    user_question: str,
    context: str,
    prompt: List[Dict[str, Any]],
    respond_model: str = "gemini-2.0-flash-exp",
    score_threshold: float = 0.85,
    max_results: int = 3,
    doc: bool = True,
    gemini_api_key: str = None,
) -> tuple[str, List[Dict[str, Any]]]:
    
    try:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel(respond_model)

        if (doc):
            # # Sort kết quả
            # filtered_results = [
            #     r for r in results
            #     if r["rerank_score"] > score_threshold and len(r["text"]) > 50
            # ][:max_results]
            
            # context = "\n".join([r["text"] for r in filtered_results])
            prompt = (
                f"{prompt} \n"
                f"Tài liệu: {context} \n \n"
                f"Trả lời cầu hỏi của tôi: {user_question}"
            )
        else:
            prompt = (
                f"{prompt} \n"
                f"Trả lời cầu hỏi của tôi: {user_question}"
            )
        
        # Sinh câu trả lời
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 512,
                "temperature": 0.3,
                "top_p": 0.9
            }
        )
        
        # Xử lý response
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, "content") and candidate.content.parts:
                response_text = candidate.content.parts[0].text.strip()
            else:
                raise ValueError("Không tìm thấy nội dung trong candidate của Gemini API.")
        else:
            raise ValueError("Response không có candidates.")

        return response_text
    
    except ResourceExhausted as e:
        error_msg = f"Vượt giới hạn API"
        print(error_msg)
        return ("Vượt giới hạn API, vui lòng thử lại sau.", [])