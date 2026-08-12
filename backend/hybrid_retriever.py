import os
import chromadb
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any, Optional

class HybridRetriever:
    def __init__(self, chroma_path: str = "./chroma_db", collection_name: str = "vtu_docs"):
        """
        Initializes the hybrid retriever by connecting to the existing ChromaDB
        and building a BM25 index over the extracted chunk texts.
        """
        self.client = chromadb.PersistentClient(path=chroma_path)
        try:
            self.collection = self.client.get_collection(name=collection_name)
        except Exception:
            self.collection = self.client.create_collection(name=collection_name)
        
        self.documents: List[str] = []
        self.metadatas: List[Dict[str, Any]] = []
        self.ids: List[str] = []
        self.bm25: Optional[BM25Okapi] = None
        
        self._load_corpus()

    def _load_corpus(self):
        """Loads all documents and metadatas from ChromaDB to build the BM25 lexical index."""
        data = self.collection.get(include=["documents", "metadatas", "ids"])
        self.documents = data.get("documents", [])
        self.metadatas = data.get("metadatas", [])
        self.ids = data.get("ids", [])
        
        tokenized_corpus = [doc.lower().split() for doc in self.documents]
        if tokenized_corpus:
            self.bm25 = BM25Okapi(tokenized_corpus)

    def retrieve(self, query: str, subject: str = "BCS501", top_k: int = 5) -> Dict[str, Any]:
        """
        Performs hybrid retrieval combining Lexical (BM25) and Semantic (ChromaDB Vector) search.
        Returns detailed debugging info including separate results and final merged chunks.
        """
        keyword_results = []
        vector_results = []

        # 1. Lexical / Keyword Search (BM25)
        if self.bm25 and self.documents:
            tokenized_query = query.lower().split()
            bm25_scores = self.bm25.get_scores(tokenized_query)
            top_bm25_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:top_k * 2]
            
            for idx in top_bm25_indices:
                meta = self.metadatas[idx] if idx < len(self.metadatas) else {}
                chunk_subject = meta.get("subject", subject)
                
                # Apply subject filter
                if subject and chunk_subject != subject:
                    continue
                    
                keyword_results.append({
                    "chunk_id": self.ids[idx] if idx < len(self.ids) else f"chunk_{idx}",
                    "source_file": meta.get("source_file", "unknown"),
                    "chunk_index": meta.get("chunk_index", idx),
                    "module": meta.get("module", "N/A"),
                    "subject": chunk_subject,
                    "text": self.documents[idx],
                    "score": float(bm25_scores[idx])
                })

        # 2. Semantic / Vector Search (ChromaDB)
        try:
            where_filter = {"subject": subject} if subject else None
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k * 2,
                where=where_filter
            )
            if results and results["documents"] and results["documents"][0]:
                docs = results["documents"][0]
                metas = results["metadatas"][0]
                ids = results["ids"][0]
                distances = results.get("distances", [[0.0] * len(docs)])[0]
                
                for i, doc in enumerate(docs):
                    meta = metas[i] if i < len(metas) else {}
                    vector_results.append({
                        "chunk_id": ids[i] if i < len(ids) else f"vec_{i}",
                        "source_file": meta.get("source_file", "unknown"),
                        "chunk_index": meta.get("chunk_index", i),
                        "module": meta.get("module", "N/A"),
                        "subject": meta.get("subject", subject),
                        "text": doc,
                        "score": float(1.0 - (distances[i] if i < len(distances) else 0.0))
                    })
        except Exception as e:
            print(f"Vector search warning: {e}")

        # 3. Combine, Deduplicate, and Rank using Reciprocal Rank Fusion (RRF) or interleaved scores
        seen_ids = set()
        combined = []

        # Interleave keyword and vector results to ensure exact matches surface alongside semantic intent
        max_len = max(len(keyword_results), len(vector_results))
        for i in range(max_len):
            if i < len(keyword_results):
                item = keyword_results[i]
                if item["chunk_id"] not in seen_ids:
                    seen_ids.add(item["chunk_id"])
                    combined.append(item)
            if i < len(vector_results):
                item = vector_results[i]
                if item["chunk_id"] not in seen_ids:
                    seen_ids.add(item["chunk_id"])
                    combined.append(item)

        final_chunks = combined[:top_k]

        return {
            "query": query,
            "vector_results": vector_results[:top_k],
            "lexical_results": keyword_results[:top_k],
            "final_merged_results": final_chunks
        }