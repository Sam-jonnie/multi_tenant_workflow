import logging
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationEvent:
    """A committed notification, ready to be pushed to the user."""

    id: int
    recipient_id: int
    organization_id: int
    type: str
    title: str
    message: str
    entity_type: str
    entity_id: int | None
    project_id: int | None
    created_at: str  # ISO 8601

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def deliver_notifications(events: Sequence[NotificationEvent]) -> None:
    """Called after the database commit. It must never raise: the action already
    succeeded, and a failed push must not turn it into an error response.

    Part 1 only logs. Part 2 replaces this body with Redis, WebSocket and email delivery.
    """
    try:
        for event in events:
            logger.debug("notification %s queued for user %s", event.id, event.recipient_id)
    except Exception:
        logger.exception("Notification delivery failed")