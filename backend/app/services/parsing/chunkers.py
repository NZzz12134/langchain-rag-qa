"""分类型分块策略：PDF 按页、表格按行聚合、MD 按标题节、DOCX/TXT 通用递归切分。"""
import hashlib
from typing import Iterator

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

PDF_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=500, chunk_overlap=50,
    separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
)
TEXT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=700, chunk_overlap=100,
    separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
)
MD_SECTION_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=500, chunk_overlap=50,
    separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
)

# 表格行聚合：约 20 行/块，上限 2000 字符
TABLE_ROW_BATCH = 20
TABLE_CHAR_LIMIT = 2000


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _token_count(content: str) -> int:
    """粗略 token 估算：中文按字、英文按词。"""
    return len(content)


def chunk_documents(file_type: str, docs: list[Document]) -> Iterator[dict]:
    """产出 chunk dict：{content, page_number, row_start, row_end, heading_path, token_count, content_hash}"""
    if file_type == "pdf":
        yield from _chunk_pdf(docs)
    elif file_type in ("xlsx", "csv"):
        yield from _chunk_tabular(docs)
    elif file_type == "md":
        yield from _chunk_md(docs)
    else:  # docx / txt / url
        for doc in docs:
            for piece in TEXT_SPLITTER.split_text(doc.page_content):
                yield _make_chunk(
                    content=piece,
                    page_number=doc.metadata.get("page"),
                    heading_path=None,
                )


def _chunk_pdf(docs: list[Document]) -> Iterator[dict]:
    """按页切分，短页合并到相邻页（避免碎片）。"""
    buffer = ""
    buffer_page = None
    for doc in docs:
        page = doc.metadata.get("page")
        pieces = PDF_SPLITTER.split_text(doc.page_content)
        if not pieces:
            continue
        first, rest = pieces[0], pieces[1:]
        if buffer and len(buffer) + len(first) < PDF_SPLITTER._chunk_size:
            buffer += "\n" + first
        else:
            if buffer:
                yield _make_chunk(buffer, buffer_page, None)
            buffer = first
            buffer_page = page
        for piece in rest:
            if buffer:
                yield _make_chunk(buffer, buffer_page, None)
            buffer = piece
            buffer_page = page
    if buffer:
        yield _make_chunk(buffer, buffer_page, None)


def _chunk_tabular(docs: list[Document]) -> Iterator[dict]:
    """行聚合：每批行拼成一块，元数据 row_start/row_end。"""
    batch: list[Document] = []
    batch_len = 0

    def flush():
        nonlocal batch, batch_len
        if batch:
            content = "\n".join(d.page_content for d in batch)
            yield _make_chunk(
                content=content,
                row_start=batch[0].metadata.get("row"),
                row_end=batch[-1].metadata.get("row"),
            )
        batch, batch_len = [], 0

    for doc in docs:
        text = doc.page_content
        if batch and (len(batch) >= TABLE_ROW_BATCH or batch_len + len(text) > TABLE_CHAR_LIMIT):
            yield from flush()
        batch.append(doc)
        batch_len += len(text)
    yield from flush()


def _chunk_md(docs: list[Document]) -> Iterator[dict]:
    for doc in docs:
        heading = doc.metadata.get("heading_path")
        for piece in MD_SECTION_SPLITTER.split_text(doc.page_content):
            yield _make_chunk(piece, None, heading)


def _make_chunk(
    content: str, page_number: int | None = None, heading_path: str | None = None,
    row_start: int | None = None, row_end: int | None = None,
) -> dict:
    return {
        "content": content,
        "page_number": page_number,
        "row_start": row_start,
        "row_end": row_end,
        "heading_path": heading_path,
        "token_count": _token_count(content),
        "content_hash": _content_hash(content),
    }
