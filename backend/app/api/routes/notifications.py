from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, NotificationServiceDep, TenantViewer
from app.schemas.common import ApiResponse, Page
from app.schemas.notification import (
    MarkAllReadResult,
    NotificationListQuery,
    NotificationRead,
    UnreadCount,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=ApiResponse[Page[NotificationRead]])
def list_notifications(
    query: Annotated[NotificationListQuery, Query()],
    ctx: TenantViewer,
    service: NotificationServiceDep,
) -> ApiResponse[Page[NotificationRead]]:
    notifications, total = service.list_for_user(ctx, query)
    items = [NotificationRead.model_validate(n) for n in notifications]
    return ApiResponse[Page[NotificationRead]](data=Page.create(items, total, query))


@router.get("/unread-count", response_model=ApiResponse[UnreadCount])
def unread_count(
    ctx: TenantViewer, service: NotificationServiceDep
) -> ApiResponse[UnreadCount]:
    return ApiResponse[UnreadCount](data=UnreadCount(unread=service.unread_count(ctx)))


@router.patch("/read-all", response_model=ApiResponse[MarkAllReadResult])
def mark_all_read(
    ctx: TenantViewer, service: NotificationServiceDep
) -> ApiResponse[MarkAllReadResult]:
    updated = service.mark_all_read(ctx)
    return ApiResponse[MarkAllReadResult](
        data=MarkAllReadResult(updated=updated), message="All notifications marked as read."
    )


@router.patch("/{notification_id}/read", response_model=ApiResponse[NotificationRead])
def mark_read(
    notification_id: int, current_user: CurrentUser, service: NotificationServiceDep
) -> ApiResponse[NotificationRead]:
    notification = service.mark_read(current_user, notification_id)
    return ApiResponse[NotificationRead](data=NotificationRead.model_validate(notification))