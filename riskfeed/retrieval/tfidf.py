from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# Document chunk
@dataclass
class DocChunk:
    source_id: str
    title: str
    text: str
    uri: str


# Read markdown files from the knowledge base
def _read_markdown_files(kb_dir: Path) -> List[Tuple[str, str]]:
    """
    Returns list of (filename, content).
    """
    items = []
    if not kb_dir.exists():
        return items

    for p in kb_dir.glob("*.md"):
        content = p.read_text(encoding="utf-8", errors="ignore")
        items.append((p.name, content))
    return items


# Chunk text into smaller pieces
def _chunk_text(text: str, *, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """
    Simple chunking so long docs can be retrieved in parts.

    Why chunking:
    - Retrieval works better when documents aren't too large.
    - Later, this matches how vector databases store chunks.
    """
    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


# TF-IDF retriever
class TfidfRetriever:
    """
    Offline TF-IDF retriever over local Markdown docs.
    """

    def __init__(self, kb_dir: Path):
        self.kb_dir = kb_dir
        self.chunks: List[DocChunk] = []
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = None

        self._build()

    def _build(self) -> None:
        files = _read_markdown_files(self.kb_dir)
        chunks: List[DocChunk] = []

        for fname, content in files:
            title = fname.replace(".md", "").replace("_", " ").title()
            uri = f"local://knowledge_base/{fname}"

            # Try to use first markdown header as title if present
            lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
            if lines and lines[0].startswith("#"):
                title = lines[0].lstrip("#").strip() or title

            for i, chunk in enumerate(_chunk_text(content)):
                source_id = f"{fname}#chunk_{i:02d}"
                chunks.append(DocChunk(source_id=source_id, title=title, text=chunk, uri=uri))

        self.chunks = chunks

        # Build TF-IDF index
        corpus = [c.text for c in self.chunks]
        if corpus:
            self.matrix = self.vectorizer.fit_transform(corpus)
        else:
            self.matrix = None

    def retrieve(self, query: str, *, top_k: int = 3, min_score: float = 0.12) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Returns (citations, meta).
        """
        query = (query or "").strip()
        if not query or self.matrix is None or not self.chunks:
            return [], {"hits": 0, "scores": []}

        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self.matrix).flatten()

        scored = list(enumerate(sims))
        scored.sort(key=lambda x: x[1], reverse=True)

        citations: List[Dict[str, Any]] = []
        scores_out: List[float] = []

        for idx, score in scored[:top_k]:
            if score < min_score:
                continue
            ch = self.chunks[idx]
            snippet = ch.text.strip().replace("\n", " ")
            snippet = snippet[:200] + ("…" if len(snippet) > 200 else "")
            citations.append(
                {
                    "source_id": ch.source_id,
                    "title": ch.title,
                    "snippet": snippet,
                    "uri": ch.uri,
                }
            )
            scores_out.append(float(score))

        return citations, {"hits": len(citations), "scores": scores_out}


# Knowledge base directory
KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"
RETRIEVER = TfidfRetriever(KB_DIR)