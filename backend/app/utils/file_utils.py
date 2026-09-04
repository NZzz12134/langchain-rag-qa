"""上传文件安全校验：扩展名白名单 + magic bytes 双校验 + SHA256。"""
import hashlib
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import BusinessError

ALLOWED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".csv": "csv",
    ".md": "md",
    ".markdown": "md",
    ".txt": "txt",
}

# magic bytes：docx/xlsx 均为 zip(PK)；pdf 为 %PDF；md/csv/txt 为文本（无二进制特征校验）
MAGIC_SIGNATURES = {
    "pdf": b"%PDF",
    "docx": b"PK\x03\x04",
    "xlsx": b"PK\x03\x04",
}


def validate_upload(filename: str, content: bytes, max_mb: int) -> tuple[str, str]:
    """返回 (file_type, checksum)。"""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise BusinessError("unsupported_type", f"不支持的文件类型：{ext}（支持 pdf/docx/xlsx/csv/md/txt）")
    file_type = ALLOWED_EXTENSIONS[ext]

    if len(content) > max_mb * 1024 * 1024:
        raise BusinessError("file_too_large", f"文件大小超过限制（{max_mb}MB）")

    signature = MAGIC_SIGNATURES.get(file_type)
    if signature and not content[:8].startswith(signature):
        raise BusinessError("invalid_file", "文件内容与扩展名不符，已拒绝")

    checksum = hashlib.sha256(content).hexdigest()
    return file_type, checksum


def save_upload(content: bytes, file_type: str) -> str:
    """落盘为 {uuid}.{ext}，返回相对 STORAGE_DIR 的路径。"""
    settings = get_settings()
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    rel_path = f"{uuid.uuid4().hex}.{file_type}"
    (settings.storage_path / rel_path).write_bytes(content)
    return rel_path


def resolve_storage_path(rel_path: str) -> Path:
    return get_settings().storage_path / rel_path
