"""上传文件安全校验单元测试：扩展名白名单、magic bytes、大小限制、落盘命名。"""
import pytest

from app.core.exceptions import BusinessError
from app.utils.file_utils import save_upload, validate_upload


def test_accepts_allowed_types():
    # 二进制类型必须带正确 magic bytes；文本类型无校验
    cases = {
        "a.pdf": b"%PDF-1.4 test",
        "b.docx": b"PK\x03\x04 zipfake",
        "c.xlsx": b"PK\x03\x04 zipfake",
        "d.csv": b"a,b\n1,2\n",
        "e.md": b"# title",
        "f.markdown": b"text",
        "g.txt": b"text",
    }
    for name, content in cases.items():
        file_type, _ = validate_upload(name, content, max_mb=50)
        assert file_type in ("pdf", "docx", "xlsx", "csv", "md", "txt")


def test_rejects_unknown_extension():
    with pytest.raises(BusinessError) as exc:
        validate_upload("evil.exe", b"MZ...", max_mb=50)
    assert exc.value.code == "unsupported_type"


def test_rejects_extension_case_insensitive_accept():
    file_type, _ = validate_upload("A.PDF", b"%PDF-1.4 fake", max_mb=50)
    assert file_type == "pdf"


def test_rejects_magic_mismatch():
    """扩展名 pdf 但内容不是 PDF 头 → 拒绝。"""
    with pytest.raises(BusinessError) as exc:
        validate_upload("fake.pdf", b"just plain text", max_mb=50)
    assert exc.value.code == "invalid_file"


def test_rejects_oversize():
    with pytest.raises(BusinessError) as exc:
        validate_upload("big.txt", b"a" * (2 * 1024 * 1024 + 1), max_mb=2)
    assert exc.value.code == "file_too_large"


def test_checksum_is_sha256():
    _, checksum = validate_upload("a.txt", b"hello", max_mb=50)
    import hashlib

    assert checksum == hashlib.sha256(b"hello").hexdigest()


def test_save_upload_uuid_naming(monkeypatch, tmp_path):
    """落盘为 {uuid}.{ext}，内容完整。"""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))

    rel = save_upload(b"content-bytes", "pdf")
    assert rel.endswith(".pdf")
    assert len(rel.split(".")[0]) == 32  # uuid hex
    stored = (tmp_path / rel).read_bytes()
    assert stored == b"content-bytes"
