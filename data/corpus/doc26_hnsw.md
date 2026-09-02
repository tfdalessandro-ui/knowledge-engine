# HNSW

Hierarchical Navigable Small World (HNSW) is a graph-based algorithm for approximate nearest-neighbor search over vector embeddings. It builds a multi-layer graph where higher layers have fewer, longer-range links, letting a search start coarse and refine down to the target layer -- giving sub-linear query time at the cost of exact recall. It is the index structure FAISS uses for the P2 hybrid search phase of this project.
