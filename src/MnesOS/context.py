import re
import math
from typing import Dict, List, Tuple

class VectorLoreStore:
    """
    A Vector RAG system for lore retrieval.
    Chunks Markdown content and uses a local vector similarity search (TF-IDF based for sandbox purity).
    """
    
    def __init__(self, lore_content: str):
        self.chunks: List[str] = self._chunk_lore(lore_content)
        self.vocab: Dict[str, int] = {}
        self.vectors: List[List[float]] = []
        self._build_index()

    def _chunk_lore(self, content: str) -> List[str]:
        """Segments lore into meaningful chunks based on headers."""
        pattern = r'(^#{1,3}\s+.*$)'
        parts = re.split(pattern, content, flags=re.MULTILINE)
        
        chunks = []
        for i in range(1, len(parts), 2):
            header = parts[i].strip()
            body = parts[i+1].strip() if i+1 < len(parts) else ""
            chunks.append(f"{header}\n{body}")
        return chunks

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r'\w+', text.lower())

    def _get_vector(self, tokens: List[str]) -> List[float]:
        """Simple frequency-based vectorization."""
        vec = [0.0] * len(self.vocab)
        for t in tokens:
            if t in self.vocab:
                vec[self.vocab[t]] += 1.0
        
        # Normalize
        magnitude = math.sqrt(sum(v*v for v in vec))
        if magnitude > 0:
            vec = [v / magnitude for v in vec]
        return vec

    def _build_index(self):
        """Creates the vocabulary and chunk vectors."""
        # Build Vocab
        word_idx = 0
        for chunk in self.chunks:
            for token in self._tokenize(chunk):
                if token not in self.vocab:
                    self.vocab[token] = word_idx
                    word_idx += 1
        
        # Build vectors
        for chunk in self.chunks:
            self.vectors.append(self._get_vector(self._tokenize(chunk)))

    def query(self, query_text: str, top_k: int = 2) -> str:
        """Retrieves top_k relevant lore chunks using Cosine Similarity."""
        query_vec = self._get_vector(self._tokenize(query_text))
        
        scores: List[Tuple[float, int]] = []
        for i, doc_vec in enumerate(self.vectors):
            # Cosine Similarity (dot product since vectors are normalized)
            score = sum(q * d for q, d in zip(query_vec, doc_vec))
            scores.append((score, i))
        
        # Sort by score descending
        scores.sort(key=lambda x: x[0], reverse=True)
        
        results = [self.chunks[idx] for score, idx in scores[:top_k] if score > 0]
        return "\n\n---\n\n".join(results)

    @classmethod
    def from_file(cls, filepath: str):
        with open(filepath, 'r') as f:
            return cls(f.read())
