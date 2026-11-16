import zipfile
from pathlib import Path

import pytest

from app.core.enums import FileKind
from app.core.exceptions import BadRequestError
from app.core.file_validation import ALLOWED_EXTENSIONS, detect_file_kind, sanitize_filename


def write_file(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def write_zip(tmp_path: Path, name: str, entries: list[str]) -> Path:
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as archive:
        for entry in entries:
            archive.writestr(entry, "x")
    return path


# ---------- detection by content ----------
def test_detects_images_and_pdf(tmp_path):
    assert detect_file_kind(write_file(tmp_path, "a", b"\x89PNG\r\n\x1a\n" + b"0" * 20)) == FileKind.PNG
    assert detect_file_kind(write_file(tmp_path, "b", b"\xff\xd8\xff\xe0" + b"0" * 20)) == FileKind.JPEG
    assert detect_file_kind(write_file(tmp_path, "c", b"GIF89a" + b"0" * 20)) == FileKind.GIF
    assert detect_file_kind(write_file(tmp_path, "d", b"RIFF\x00\x00\x00\x00WEBPVP8 ")) == FileKind.WEBP
    assert detect_file_kind(write_file(tmp_path, "e", b"%PDF-1.7\n%%EOF")) == FileKind.PDF


def test_detects_utf8_text(tmp_path):
    assert detect_file_kind(write_file(tmp_path, "t", "héllo wörld\n".encode())) == FileKind.TEXT


def test_binary_with_nul_bytes_is_rejected(tmp_path):
    assert detect_file_kind(write_file(tmp_path, "x", b"MZ\x90\x00\x03\x00\x00\x00")) is None


def test_invalid_utf8_is_rejected(tmp_path):
    assert detect_file_kind(write_file(tmp_path, "x", b"abc\xff\xfe\xfdabc")) is None


def test_office_documents(tmp_path):
    docx = write_zip(tmp_path, "a", ["[Content_Types].xml", "word/document.xml"])
    xlsx = write_zip(tmp_path, "b", ["[Content_Types].xml", "xl/workbook.xml"])
    pptx = write_zip(tmp_path, "c", ["[Content_Types].xml", "ppt/presentation.xml"])
    assert detect_file_kind(docx) == FileKind.DOCX
    assert detect_file_kind(xlsx) == FileKind.XLSX
    assert detect_file_kind(pptx) == FileKind.PPTX


def test_plain_zip_is_rejected(tmp_path):
    assert detect_file_kind(write_zip(tmp_path, "z", ["a.txt", "b.txt"])) is None


def test_macro_enabled_document_is_rejected(tmp_path):
    macro = write_zip(
        tmp_path, "m", ["[Content_Types].xml", "word/document.xml", "word/vbaProject.bin"]
    )
    assert detect_file_kind(macro) is None


def test_corrupt_zip_is_rejected(tmp_path):
    assert detect_file_kind(write_file(tmp_path, "bad", b"PK\x03\x04 not really a zip")) is None


# ---------- extension rules ----------
def test_extension_must_belong_to_detected_kind():
    assert ".png" not in ALLOWED_EXTENSIONS[FileKind.PDF]
    assert ".exe" not in ALLOWED_EXTENSIONS[FileKind.PNG]
    assert ".jpeg" in ALLOWED_EXTENSIONS[FileKind.JPEG]


# ---------- file name sanitizing ----------
def test_sanitize_removes_directories():
    assert sanitize_filename("../../etc/passwd.txt") == "passwd.txt"
    assert sanitize_filename("C:\\fakepath\\a.png") == "a.png"


def test_sanitize_removes_unsafe_characters():
    assert sanitize_filename("report<>.pdf") == "report.pdf"
    assert sanitize_filename("bad\x00name.png") == "badname.png"
    assert sanitize_filename("notes.txt:hidden") == "notes.txthidden"


def test_sanitize_trims_dots_and_spaces():
    assert sanitize_filename("  ..hidden.txt") == "hidden.txt"


def test_sanitize_limits_length_and_keeps_extension():
    name = sanitize_filename("a" * 300 + ".pdf")
    assert len(name) <= 200
    assert name.endswith(".pdf")


@pytest.mark.parametrize("raw", [None, "", "   ", "..."])
def test_sanitize_rejects_empty_names(raw):
    with pytest.raises(BadRequestError):
        sanitize_filename(raw)