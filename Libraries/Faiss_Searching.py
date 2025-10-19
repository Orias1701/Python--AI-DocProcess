import numpy as np
from typing import Any, Dict, List, Optional
from sentence_transformers import SentenceTransformer, CrossEncoder


class SemanticSearchEngine:

    def __init__(
        self,
        indexer: SentenceTransformer,
        reranker: Optional[CrossEncoder] = None,
        device: str = "cuda",
        normalize: bool = True,
        top_k: int = 20,
        rerank_k: int = 10,
        rerank_batch_size: int = 16,
    ):
        self.device = device
        self.normalize = normalize
        self.top_k = int(top_k)
        self.rerank_k = int(rerank_k)
        self.rerank_batch_size = int(rerank_batch_size)

        # ✅ Nhận trực tiếp model đã load
        if not isinstance(indexer, SentenceTransformer):
            raise TypeError("indexer phải là SentenceTransformer đã load sẵn.")
        self._indexer = indexer

        # Reranker là tùy chọn
        if reranker and not isinstance(reranker, CrossEncoder):
            raise TypeError("reranker phải là CrossEncoder hoặc None.")
        self.reranker = reranker

    # ---------------------------
    # Tiện ích nội bộ
    # ---------------------------
    @staticmethod
    def _l2_normalize(x: np.ndarray, axis: int = 1, eps: float = 1e-12) -> np.ndarray:
        denom = np.linalg.norm(x, axis=axis, keepdims=True)
        denom = np.maximum(denom, eps)
        return x / denom

    @staticmethod
    def _build_idx_maps(Mapping: Dict[str, Any], MapData: Dict[str, Any]):
        """Tạo ánh xạ index→text và index→key"""
        items = MapData.get("items", [])
        idx2text = {int(item["index"]): item.get("text", None) for item in items}
        raw_i2k = Mapping.get("index_to_key", {})
        idx2key = {int(i): k for i, k in raw_i2k.items()}
        return idx2text, idx2key

    # ---------------------------
    # 1️⃣ SEARCH: FAISS vector search
    # ---------------------------
    def search(
        self,
        query: str,
        faissIndex: "faiss.Index",  # type: ignore
        Mapping: Dict[str, Any],
        MapData: Dict[str, Any],
        MapChunk: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
        query_embedding: Optional[np.ndarray] = None,
    ) -> List[Dict[str, Any]]:
        """
        Trả về:
            [{"index":..., "key":..., "text":..., "faiss_score":...}, ...]
        """
        k = int(top_k or self.top_k)

        # 1. Encode truy vấn (hoặc dùng sẵn embedding)
        if query_embedding is None:
            q = self._indexer.encode(
                [query], convert_to_tensor=True, device=str(self.device)
            )
            q = q.detach().cpu().numpy().astype("float32")
        else:
            q = np.asarray(query_embedding, dtype="float32")
            if q.ndim == 1:
                q = q[None, :]

        # 2. Normalize nếu dùng cosine
        if self.normalize:
            q = self._l2_normalize(q)

        # 3. Search FAISS
        scores, ids = faissIndex.search(q, k)
        idx2text, idx2key = self._build_idx_maps(Mapping, MapData)

        # 4. Mapping kết quả
        chunk_map = MapChunk.get("index_to_chunk", {}) if MapChunk else {}
        results = []
        for score, idx in zip(scores[0].tolist(), ids[0].tolist()):
            chunk_ids = chunk_map.get(str(idx), [])
            results.append({
                "index": int(idx),
                "key": idx2key.get(int(idx)),
                "text": idx2text.get(int(idx)),
                "faiss_score": float(score),
                "chunk_ids": chunk_ids,
            })
        return results

    # ---------------------------
    # 2️⃣ RERANK: CrossEncoder rerank
    # ---------------------------
    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: Optional[int] = None,
        show_progress: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Xếp hạng lại kết quả bằng CrossEncoder (nếu có).
        Trả về danh sách top_k kết quả đã rerank.
        """
        if not results:
            return []
        if self.reranker is None:
            raise ValueError("⚠️ Không có reranker được cung cấp khi khởi tạo.")

        k = int(top_k or self.rerank_k)

        pairs = []
        valid_indices = []
        for i, r in enumerate(results):
            text = r.get("text")
            if isinstance(text, str) and text.strip():
                pairs.append([query, text])
                valid_indices.append(i)

        if not pairs:
            return []

        scores = self.reranker.predict(
            pairs, batch_size=self.rerank_batch_size, show_progress_bar=show_progress
        )

        for i, s in zip(valid_indices, scores):
            results[i]["rerank_score"] = float(s)

        reranked = [r for r in results if "rerank_score" in r]
        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:k]
