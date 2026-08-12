from backend.hybrid_retriever import HybridRetriever

def test_safehome_retrieval():
    retriever = HybridRetriever(chroma_path="./chroma_db")
    query = "SafeHome preliminary use case"
    
    print(f"\n================ TEST QUERY: '{query}' ================\n")
    output = retriever.retrieve(query=query, subject="BCS501", top_k=5)
    
    print("--- 1. VECTOR RESULTS ---")
    for r in output["vector_results"]:
        print(f"ID: {r['chunk_id']} | File: {r['source_file']} | Score: {r['score']:.4f}")
        print(f"Snippet: {r['text'][:120]}...\n")
        
    print("--- 2. LEXICAL (KEYWORD) RESULTS ---")
    for r in output["lexical_results"]:
        print(f"ID: {r['chunk_id']} | File: {r['source_file']} | Score: {r['score']:.4f}")
        print(f"Snippet: {r['text'][:120]}...\n")
        
    print("--- 3. FINAL MERGED RESULTS ---")
    for r in output["final_merged_results"]:
        print(f"ID: {r['chunk_id']} | File: {r['source_file']} | Score: {r['score']:.4f}")
        print(f"Snippet: {r['text'][:150]}...\n")

if __name__ == "__main__":
    test_safehome_retrieval()