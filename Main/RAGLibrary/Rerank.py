from typing import Any, Dict, List
from sentence_transformers import CrossEncoder


""" RERANK """

"""
Xếp hạng lại kết quả sử dụng mô hình reranker.

Args:
    query: Câu hỏi dạng văn bản
    results: Danh sách kết quả sơ bộ từ search_faiss_index
    reranker_model: Tên mô hình reranker (RERANK_MODEL từ DEFINE)
    device: Thiết bị PyTorch (cuda hoặc cpu)
    k: Số lượng kết quả trả về sau reranking

Returns:
    Danh sách các kết quả: {"text": văn bản, "rerank_score": điểm reranker, "faiss_score": điểm FAISS}
"""

def rerank_results(
    query: str,
    results: List[Dict[str, Any]],
    reranker_model: str,
    device: str = "cuda",
    k: int = 5,
    batches: bool = False,
) -> List[Dict[str, Any]]:
    try:
        if not results:
            return []
        
        # Tải mô hình reranker
        reranker = CrossEncoder(reranker_model, device=device)
        
        # Tạo cặp [query, text] để rerank
        pairs = [[query, result["text"]] for result in results]
        
        # Tính điểm rerank
        rerank_scores = reranker.predict(pairs, show_progress_bar = batches)
        
        # Gắn điểm rerank vào kết quả
        for i, score in enumerate(rerank_scores):
            results[i]["rerank_score"] = float(score)
        
        # Sắp xếp theo rerank_score và lấy top k
        sorted_results = sorted(results, key=lambda x: x["rerank_score"], reverse=True)[:k]
        
        # Định dạng kết quả cuối
        final_results = [
            {
                "text": result["text"],
                "rerank_score": result["rerank_score"],
                "faiss_score": result["faiss_score"]
            }
            for result in sorted_results
        ]
        
        return final_results
    
    except Exception as e:
        print(f"Error during rerank: {str(e)}")
        raise
