"""补充 Loader 单元测试：Excel(xlsx) 表格语义保留、行号元数据。"""
import pytest

from app.services.parsing.chunkers import chunk_documents
from app.services.parsing.loaders import load_xlsx


@pytest.fixture
def xlsx_file(tmp_path):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "商品表"
    ws.append(["商品名称", "价格(元)", "库存"])
    ws.append(["蓝牙耳机", 299, 50])
    ws.append(["充电宝", 99, 120])
    p = tmp_path / "products.xlsx"
    wb.save(p)
    return p


def test_xlsx_rows_become_documents(xlsx_file):
    docs = load_xlsx(xlsx_file)
    assert len(docs) == 2  # 2 行数据（表头除外）

    # 内容保留 列名: 值 结构
    assert "商品名称: 蓝牙耳机" in docs[0].page_content
    assert "价格(元): 299" in docs[0].page_content
    assert "[商品表]" in docs[0].page_content

    # 行号元数据：表头第 1 行，数据行 2 起（1-based）
    assert docs[0].metadata["row"] == 2
    assert docs[1].metadata["row"] == 3


def test_xlsx_chunker_row_ranges(xlsx_file):
    docs = load_xlsx(xlsx_file)
    chunks = list(chunk_documents("xlsx", docs))
    # 行聚合：2 行合成 1 块，row_start/row_end 正确
    assert chunks[0]["row_start"] == 2
    assert chunks[0]["row_end"] == 3


def test_xlsx_empty_sheet(tmp_path):
    import openpyxl

    wb = openpyxl.Workbook()
    p = tmp_path / "empty.xlsx"
    wb.save(p)
    docs = load_xlsx(p)
    assert docs == []
