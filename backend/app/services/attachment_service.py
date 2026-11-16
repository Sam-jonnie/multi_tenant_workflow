import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import AttachmentContext, ProjectContext
from app.core.enums import AuditAction, AuditEntity
from app.core.exceptions import NotFoundError, UnsupportedMediaTypeError
from app.core.file_validation import (
    ALLOWED_EXTENSIONS,
    detect_file_kind,
    mime_type_for,
    sanitize_filename,
    storage_extension,
)
from app.core.rules import ensure_project_writable
from app.core.storage import FileStorage, storage
from app.models.attachment import Attachment
from app.repositories.attachment_repository import AttachmentRepository
from app.schemas.attachment import AttachmentListQuery
from app.services.audit_service import AuditService


class AttachmentService:
    def __init__(
        self, db: Session, audit: AuditService, file_storage: FileStorage = storage
    ) -> None:
        self.db = db
        self.audit = audit
        self.storage = file_storage
        self.attachments = AttachmentRepository(db)

    def upload(
        self,
        pctx: ProjectContext,
        task_id: int | None,
        filename: str | None,
        stream: BinaryIO,
    ) -> Attachment:
        project = pctx.project
        user = pctx.org.user
        ensure_project_writable(project)

        display_name = sanitize_filename(filename)
        extension = Path(display_name).suffix.lower()

        # 1. receive the bytes into a temp file (size limit enforced while streaming)
        staged = self.storage.stage(stream, settings.max_upload_size_bytes)
        stored_path: str | None = None
        try:
            # 2. decide what the file REALLY is from its bytes
            kind = detect_file_kind(staged.path)
            if kind is None:
                raise UnsupportedMediaTypeError(
                    "UNSUPPORTED_FILE_TYPE", "This file type is not allowed."
                )
            # 3. the extension the client gave must agree with the content
            if extension not in ALLOWED_EXTENSIONS[kind]:
                raise UnsupportedMediaTypeError(
                    "FILE_EXTENSION_MISMATCH",
                    f"The file content is {kind.value}, but the name ends with "
                    f"'{extension or 'no extension'}'.",
                )

            # 4. accept: final location uses a random name, never the client's
            mime_type = mime_type_for(kind, extension)
            stored_path = (
                f"{project.organization_id}/{project.id}/"
                f"{uuid.uuid4().hex}{storage_extension(kind, extension)}"
            )
            self.storage.commit(staged, stored_path)

            attachment = Attachment(
                project_id=project.id,
                task_id=task_id,
                uploaded_by_id=user.id,
                filename=display_name,
                mime_type=mime_type,
                size_bytes=staged.size_bytes,
                storage_path=stored_path,
                checksum_sha256=staged.sha256,
            )
            self.attachments.add(attachment)
            self.audit.log(
                AuditAction.FILE_UPLOADED,
                entity_type=AuditEntity.ATTACHMENT,
                entity_id=attachment.id,
                user_id=user.id,
                organization_id=project.organization_id,
                metadata={
                    "project_id": project.id,
                    "task_id": task_id,
                    "filename": display_name,
                    "mime_type": mime_type,
                    "size_bytes": staged.size_bytes,
                },
            )
            self.db.commit()
        except Exception:
            # Disk and database cannot share one transaction, so undo the disk side by hand.
            self.db.rollback()
            self.storage.discard(staged)
            if stored_path is not None:
                self.storage.delete(stored_path)
            raise

        self.db.refresh(attachment)
        return attachment

    def list_for_project(
        self, pctx: ProjectContext, query: AttachmentListQuery
    ) -> tuple[list[Attachment], int]:
        return self.attachments.list_for_project(pctx.project.id, query)

    def list_for_task(
        self, task_id: int, query: AttachmentListQuery
    ) -> tuple[list[Attachment], int]:
        return self.attachments.list_for_task(task_id, query)

    def file_path(self, actx: AttachmentContext) -> Path:
        path = self.storage.resolve(actx.attachment.storage_path)
        if not path.is_file():
            raise NotFoundError("FILE_MISSING", "The file is no longer available.")
        return path

    def delete(self, actx: AttachmentContext) -> None:
        attachment = actx.attachment
        ensure_project_writable(attachment.project)
        stored_path = attachment.storage_path

        self.audit.log(
            AuditAction.FILE_DELETED,
            entity_type=AuditEntity.ATTACHMENT,
            entity_id=attachment.id,
            user_id=actx.user.id,
            organization_id=attachment.project.organization_id,
            metadata={
                "project_id": attachment.project_id,
                "task_id": attachment.task_id,
                "filename": attachment.filename,
            },
        )
        self.attachments.delete(attachment)
        self.db.commit()
        self.storage.delete(stored_path)  # after the commit: a dangling file beats a dangling row