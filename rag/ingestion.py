"""Load and chunk the FinAssist AI knowledge base for embedding."""

from dataclasses import dataclass
from pathlib import Path

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

KB_DIR = Path(__file__).parent.parent / "knowledge_base"

HEADERS_TO_SPLIT_ON = [("#", "h1"), ("##", "h2")]
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


@dataclass
class Chunk:
    id: str
    text: str
    source: str


def load_and_chunk() -> list[Chunk]:
    """Load every knowledge_base/*.md file and split it into overlapping chunks.

    Splitting is header-aware first (so a chunk doesn't straddle unrelated
    policy sections), then size-capped, so retrieval returns focused,
    citable passages rather than whole documents.
    """
    header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=HEADERS_TO_SPLIT_ON)
    size_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    chunks: list[Chunk] = []
    for md_path in sorted(KB_DIR.glob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        for header_doc in header_splitter.split_text(text):
            for sub_text in size_splitter.split_text(header_doc.page_content):
                if not sub_text.strip():
                    continue
                chunks.append(
                    Chunk(id=f"{md_path.stem}-{len(chunks)}", text=sub_text, source=md_path.name)
                )

    return chunks
