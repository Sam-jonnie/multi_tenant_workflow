import re
import unicodedata
import zipfile
from codecs import getincrementaldecoder
from pathlib import Path, PurePath

from app.core.enums import FileKind
from app.core.exceptions import BadRequestError

HEADER_SIZE = 16
READ_CHUNK_SIZE = 64 * 1024
MAX_FILENAME_LENGTH = 200
MAX_ZIP_ENTRIES = 5_000
MAX_ZIP_UNCOMPRESSED_BYTES = 200 * 1024 * 1024

# The client's extension must be one of these FOR THE TYPE WE DETECTED in the bytes.
ALLOWED_EXTENSIONS: dict[FileKind, frozenset[str]] = {
    FileKind.PNG: frozenset({".png"}),
    FileKind.JPEG: frozenset({".jpg", ".jpeg"}),
    FileKind.GIF: frozenset({".gif"}),
    FileKind.WEBP: frozenset({".webp"}),
    FileKind.PDF: frozenset({".pdf"}),
    FileKind.DOCX: frozenset({".docx"}),
    FileKind.XLSX: frozenset({".xlsx"}),
    FileKind.PPTX: frozenset({".pptx"}),
    FileKind.TEXT: frozenset({".txt", ".csv", ".md"}),
}

_CANONICAL_EXTENSION: dict[FileKind, str] = {
    FileKind.PNG: ".png",
    FileKind.JPEG: ".jpg",
    FileKind.GIF: ".gif",
    FileKind.WEBP: ".webp",
    FileKind.PDF: ".pdf",
    FileKind.DOCX: ".docx",
    FileKind.XLSX: ".xlsx",
    FileKind.PPTX: ".pptx",
}

_MIME_TYPES: dict[FileKind, str] = {
    FileKind.PNG: "image/png",
    FileKind.JPEG: "image/jpeg",
    FileKind.GIF: "image/gif",
    FileKind.WEBP: "image/webp",
    FileKind.PDF: "application/pdf",
    FileKind.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    FileKind.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    FileKind.PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

_TEXT_MIME_TYPES: dict[str, str] = {
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".md": "text/markdown",
}

_OFFICE_MARKERS: dict[str, FileKind] = {
    "word/document.xml": FileKind.DOCX,
    "xl/workbook.xml": FileKind.XLSX,
    "ppt/presentation.xml": FileKind.PPTX,
}

_UNSAFE_FILENAME_CHARS = re.compile(r'[\x00-\x1f\x7f<>:"|?*]')


def storage_extension(kind: FileKind, client_extension: str) -> str:
    """The extension we store under. Text files keep theirs (all three are harmless)."""
    return client_extension if kind == FileKind.TEXT else _CANONICAL_EXTENSION[kind]


def mime_type_for(kind: FileKind, client_extension: str) -> str:
    return _TEXT_MIME_TYPES[client_extension] if kind == FileKind.TEXT else _MIME_TYPES[kind]


def sanitize_filename(raw: str | None) -> str:
    """Make a client-supplied name safe to store and show. Never used as a disk path."""
    if not raw:
        raise BadRequestError("FILE_NAME_REQUIRED", "The uploaded file must have a name.")

    name = re.split(r"[\\/]", raw)[-1]  # drop any directory part, Windows or Unix style
    name = unicodedata.normalize("NFC", name)
    name = _UNSAFE_FILENAME_CHARS.sub("", name).strip(" .")
    if not name:
        raise BadRequestError("FILE_NAME_INVALID", "The file name is not valid.")

    if len(name) > MAX_FILENAME_LENGTH:
        suffix = PurePath(name).suffix[:20]
        name = name[: MAX_FILENAME_LENGTH - len(suffix)] + suffix
    return name


def detect_file_kind(path: Path) -> FileKind | None:
    """Decide what a file really is by looking at its bytes. None = not allowed."""
    with path.open("rb") as f:
        header = f.read(HEADER_SIZE)

    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return FileKind.PNG
    if header.startswith(b"\xff\xd8\xff"):
        return FileKind.JPEG
    if header[:6] in (b"GIF87a", b"GIF89a"):
        return FileKind.GIF
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return FileKind.WEBP
    if header.startswith(b"%PDF-"):
        return FileKind.PDF
    if header.startswith(b"PK\x03\x04"):  # zip container: docx, xlsx, pptx, or a plain zip
        return _detect_office_document(path)
    if _is_utf8_text(path):
        return FileKind.TEXT
    return None


def _detect_office_document(path: Path) -> FileKind | None:
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ZIP_ENTRIES:
                return None
            if sum(entry.file_size for entry in entries) > MAX_ZIP_UNCOMPRESSED_BYTES:
                return None  # zip-bomb guard; we never extract, we only read the index
            names = {entry.filename for entry in entries}
    except (zipfile.BadZipFile, OSError):
        return None

    if "[Content_Types].xml" not in names:
        return None
    if any(name.lower().endswith("vbaproject.bin") for name in names):
        return None  # macro-enabled document renamed to .docx/.xlsx/.pptx
    for marker, kind in _OFFICE_MARKERS.items():
        if marker in names:
            return kind
    return None


def _is_utf8_text(path: Path) -> bool:
    decoder = getincrementaldecoder("utf-8")()
    try:
        with path.open("rb") as f:
            while chunk := f.read(READ_CHUNK_SIZE):
                if b"\x00" in chunk:
                    return False
                decoder.decode(chunk)
        decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        return False
    return True