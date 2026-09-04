"""文档解析单元测试：loaders 与 chunkers 的元数据正确性。"""
import pytest

from app.services.parsing.chunkers import chunk_documents
from app.services.parsing.loaders import load_csv, load_document, load_markdown, load_txt


@pytest.fixture
def md_file(tmp_path):
    content = """# 商品详情

## 规格参数
- 重量：100g
- 尺寸：10cm

## 售后服务
保修 1 年。
"""
    p = tmp_path / "test.md"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def csv_file(tmp_path):
    content = "名称,价格,库存\n蓝牙耳机,299,50\n充电宝,99,120\n"
    p = tmp_path / "test.csv"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def txt_file(tmp_path):
    p = tmp_path / "test.txt"
    p.write_text("这是纯文本知识内容。", encoding="utf-8")
    return p


def test_markdown_heading_paths(md_file):
    docs = load_markdown(md_file)
    headings = {d.metadata.get("heading_path") for d in docs}
    # h1 下无直接内容时不产生块；各子节带完整标题链
    assert "商品详情 > 规格参数" in headings
    assert "商品详情 > 售后服务" in headings
    # 内容不含标题行
    assert all(not d.page_content.startswith("#") for d in docs)
    # 内容正确归属
    spec_doc = next(d for d in docs if d.metadata["heading_path"] == "商品详情 > 规格参数")
    assert "重量" in spec_doc.page_content
    assert "保修" not in spec_doc.page_content


def test_md_chunker_keeps_heading_path(md_file):
    docs = load_markdown(md_file)
    chunks = list(chunk_documents("md", docs))
    assert len(chunks) >= 2
    assert any(c["heading_path"] == "商品详情 > 规格参数" for c in chunks)
    assert all(c["content_hash"] for c in chunks)
    assert all(c["token_count"] > 0 for c in chunks)


def test_csv_row_numbers(csv_file):
    docs = load_csv(csv_file)
    assert len(docs) == 2
    # 表头占第 1 行，数据行从第 2 行起
    assert docs[0].metadata["row"] == 2
    assert docs[1].metadata["row"] == 3
    assert "蓝牙耳机" in docs[0].page_content
    assert "名称: 蓝牙耳机" in docs[0].page_content


def test_csv_chunker_row_ranges(csv_file):
    docs = load_csv(csv_file)
    chunks = list(chunk_documents("csv", docs))
    assert chunks[0]["row_start"] == 2
    assert chunks[0]["row_end"] == 3  # 行聚合


def test_txt_loader(txt_file):
    docs = load_document("txt", str(txt_file))
    assert len(docs) == 1
    assert "纯文本知识内容" in docs[0].page_content


def test_txt_chunker():
    from langchain_core.documents import Document

    long_text = ("这是用于测试递归分块的中文内容。" * 50)  # 超过 700 字符
    docs = [Document(page_content=long_text)]
    chunks = list(chunk_documents("txt", docs))
    assert len(chunks) > 1
    assert all(len(c["content"]) <= 700 + 20 for c in chunks)  # 容差


def test_unknown_type_raises():
    with pytest.raises(ValueError):
        load_document("exe", "somewhere")
