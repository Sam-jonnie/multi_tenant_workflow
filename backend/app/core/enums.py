from enum import StrEnum


class OrgRole(StrEnum):
    ORG_ADMIN = "org_admin"
    PROJECT_MANAGER = "project_manager"
    TEAM_MEMBER = "team_member"
    VIEWER = "viewer"


class ProjectStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TaskStatus(StrEnum):
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    REVIEW = "review"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationType(StrEnum):
    TASK_ASSIGNED = "task_assigned"
    TASK_REASSIGNED = "task_reassigned"
    TASK_STATUS_CHANGED = "task_status_changed"
    COMMENT_ADDED = "comment_added"
    USER_MENTIONED = "user_mentioned"
    PROJECT_MEMBER_ADDED = "project_member_added"
    TASK_DUE_SOON = "task_due_soon"
    TASK_OVERDUE = "task_overdue"


class AuditAction(StrEnum):
    LOGIN = "login"
    PROJECT_CREATED = "project_created"
    PROJECT_UPDATED = "project_updated"
    TASK_CREATED = "task_created"
    TASK_ASSIGNED = "task_assigned"
    TASK_STATUS_CHANGED = "task_status_changed"
    COMMENT_ADDED = "comment_added"
    FILE_UPLOADED = "file_uploaded"
    MEMBER_ADDED = "member_added"
    MEMBER_REMOVED = "member_removed"