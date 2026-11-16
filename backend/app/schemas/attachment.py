from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.enums import SortOrder
from app.schemas.common import PageParams
from app.schemas.user import UserBrief


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    task_id: int | None
    filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    uploaded_by: UserBrief
    created_at: datetime

    @computed_field
    @property
    def download_url(self) -> str:
        return f"/api/v1/attachments/{self.id}/download"


class AttachmentListQuery(PageParams):
    model_config = ConfigDict(str_strip_whitespace=True)

    search: str | None = Field(None, max_length=100)
    sort_order: SortOrder = SortOrder.DESC