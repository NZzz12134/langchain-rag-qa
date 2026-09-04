"""六类文档加载器：返回 LangChain Document 列表，元数据保留来源结构。

约定元数据：page（PDF 页码）/ row（Excel、CSV 行号）/ heading_path（MD 标题链）
"""
import html
import io
import logging
import re
from pathlib import Path

import chardet
import html2text
import pandas as pd
from bs4 import BeautifulSoup
from docx2txt import process as docx2txt_process
from langchain_community.document_loaders import AsyncHtmlLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document
from pypdf import PdfReader

logger = logging.getLogger(__name__)


def _read_text_with_encoding(path: Path) -> str:
    raw = path.read_bytes()
    detected = chardet.detect(raw)
    encoding = detected.get("encoding") or "utf-8"
    # chardet 对中文常误报 gb2312/gbk，统一按 gbk 族处理
    if encoding and encoding.lower().replace("-", "") in ("gb2312", "gbk", "gb18030"):
        encoding = "gb18030"
    try:
        return raw.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        return raw.decode("utf-8", errors="replace")


def load_pdf(path: Path) -> list[Document]:
    """逐页加载，每页一个 Document（page 元数据），分块在 chunkers 中按页处理。

    失败原因面向用户：扫描版（无文字层）、加密、损坏都给出明确中文提示。
    """
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise ValueError("PDF 文件无法读取：文件可能已损坏或格式不受支持") from exc

    if reader.is_encrypted:
        raise ValueError("该 PDF 已加密，请先解除密码保护后再上传")

    docs = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            docs.append(Document(page_content=text, metadata={"page": i + 1}))

    if not docs:
        has_images = any(len(page.images or []) > 0 for page in reader.pages)
        if has_images:
            raise ValueError(
                "该 PDF 为扫描版/图片型，没有可提取的文字层。请提供文字版 PDF，或先将扫描件做 OCR 转换"
            )
        raise ValueError("该 PDF 中没有可提取的文字内容")
    return docs


def load_docx(path: Path) -> list[Document]:
    text = docx2txt_process(str(path)) or ""
    # docx2txt 忽略表格：用 python-docx 补齐表格文本
    try:
        from docx import Document as DocxDocument

        d = DocxDocument(str(path))
        table_texts = []
        for table in d.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells]
                table_texts.append(" | ".join(cells))
        if table_texts:
            text += "\n\n[表格]\n" + "\n".join(table_texts)
    except ImportError:
        logger.warning("python-docx not installed, docx tables skipped")
    return [Document(page_content=text)] if text.strip() else []


def load_xlsx(path: Path) -> list[Document]:
    """Excel：每个 sheet 的每一行序列化为 '列名: 值' 文本，行号进元数据。"""
    docs = []
    sheets = pd.read_excel(path, sheet_name=None, header=0, dtype=str)
    for sheet_name, df in sheets.items():
        df = df.fillna("")
        columns = [str(c) for c in df.columns]
        for row_no, row in df.iterrows():
            parts = [f"{columns[i]}: {row.iloc[i]}" for i in range(len(columns)) if str(row.iloc[i]).strip()]
            if parts:
                docs.append(
                    Document(
                        page_content=f"[{sheet_name}]\n" + "\n".join(parts),
                        metadata={"sheet": sheet_name, "row": int(row_no) + 2},  # +2: header+1based
                    )
                )
    return docs


def load_csv(path: Path) -> list[Document]:
    text = _read_text_with_encoding(path)
    try:
        df = pd.read_csv(io.StringIO(text), dtype=str)
    except Exception:
        # 分隔符可能不是逗号，交给 pandas 嗅探
        df = pd.read_csv(io.StringIO(text), sep=None, engine="python", dtype=str)
    df = df.fillna("")
    columns = [str(c) for c in df.columns]
    docs = []
    for row_no, row in df.iterrows():
        parts = [f"{columns[i]}: {row.iloc[i]}" for i in range(len(columns)) if str(row.iloc[i]).strip()]
        if parts:
            docs.append(
                Document(page_content="\n".join(parts), metadata={"row": int(row_no) + 2})
            )
    return docs


_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def load_markdown(path: Path) -> list[Document]:
    """按标题结构切分：每个标题节一个 Document，heading_path 为标题链。"""
    text = _read_text_with_encoding(path)
    lines = text.splitlines()
    docs = []
    stack: list[tuple[int, str]] = []  # (level, title)
    current_lines: list[str] = []

    def flush():
        nonlocal current_lines
        if current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                heading_path = " > ".join(t for _, t in stack) if stack else None
                docs.append(
                    Document(page_content=body, metadata={"heading_path": heading_path})
                )
        current_lines = []

    for line in lines:
        m = _MD_HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            title = m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
        else:
            current_lines.append(line)
    flush()
    return docs


def load_txt(path: Path) -> list[Document]:
    return [Document(page_content=_read_text_with_encoding(path))] if path.stat().st_size > 0 else []


def load_url(url: str) -> list[Document]:
    """网页抓取：AsyncHtmlLoader → bs4 正文清洗 → html2text。"""
    loader = AsyncHtmlLoader([url], ignore_load_errors=True)
    raw_docs = loader.load()
    docs = []
    h2t = html2text.HTML2Text()
    h2t.ignore_links = True
    h2t.ignore_images = True
    h2t.body_width = 0
    for raw in raw_docs:
        soup = BeautifulSoup(raw.page_content, "lxml")
        for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "iframe"]):
            tag.decompose()
        body = soup.find("body") or soup
        text = h2t.handle(str(body))
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        # 限制单页大小，防止超大页面
        if len(text) > 200_000:
            text = text[:200_000]
        if text:
            docs.append(Document(page_content=text, metadata={"source_url": url}))
    if not docs:
        raise ValueError(f"网页抓取失败或内容为空: {url}")
    return docs


LOADER_BY_TYPE = {
    "pdf": load_pdf,
    "docx": load_docx,
    "xlsx": load_xlsx,
    "csv": load_csv,
    "md": load_markdown,
    "txt": load_txt,
}


def load_document(file_type: str, path: str) -> list[Document]:
    """统一入口。file_type=url 时 path 为 URL。"""
    if file_type == "url":
        return load_url(path)
    loader = LOADER_BY_TYPE.get(file_type)
    if loader is None:
        raise ValueError(f"不支持的文档类型: {file_type}")
    return loader(Path(path))
