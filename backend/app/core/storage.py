import hashlib
import logging
import os
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings
from app.core.exceptions import BadRequestError, PayloadTooLargeError

logger = logging.getLogger(__name__)

CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True)
class StagedFile:
    """An upload that has been fully received into a temp file but not accepted yet."""

    path: Path
    size_bytes: int
    sha256: str


class FileStorage:
    """The only place that touches the disk for uploads.
    Swap this class for an S3 version later; nothing else needs to change."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.tmp_dir = self.root / ".tmp"

    def stage(self, stream: BinaryIO, max_bytes: int) -> StagedFile:
        """Copy the upload to a temp file in chunks, enforcing the size limit
        while reading, so a huge upload can never fill memory."""
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = self.tmp_dir / uuid.uuid4().hex
        digest = hashlib.sha256()
        size = 0
        try:
            with temp_path.open("wb") as out:
                while chunk := stream.read(CHUNK_SIZE):
                    size += len(chunk)
                    if size > max_bytes:
                        raise PayloadTooLargeError(
                            "FILE_TOO_LARGE",
                            f"The file exceeds the {max_bytes // (1024 * 1024)} MB limit.",
                        )
                    digest.update(chunk)
                    out.write(chunk)
            if size == 0:
                raise BadRequestError("EMPTY_FILE", "The uploaded file is empty.")
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        return StagedFile(path=temp_path, size_bytes=size, sha256=digest.hexdigest())

    def commit(self, staged: StagedFile, relative_path: str) -> None:
        """Move the accepted temp file to its final place (atomic on one filesystem)."""
        target = self.resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged.path, target)

    def discard(self, staged: StagedFile) -> None:
        staged.path.unlink(missing_ok=True)

    def resolve(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Path escapes the storage root.")
        return path

    def delete(self, relative_path: str) -> None:
        try:
            self.resolve(relative_path).unlink(missing_ok=True)
        except (OSError, ValueError):
            logger.warning("Could not delete stored file %s", relative_path, exc_info=True)

    def delete_many(self, relative_paths: Iterable[str]) -> None:
        for relative_path in relative_paths:
            self.delete(relative_path)


storage = FileStorage(settings.upload_dir)