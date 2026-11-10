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
    # authentication
    USER_REGISTERED = "user_registered"
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGED = "password_changed"
    # organizations and members
    ORGANIZATION_CREATED = "organization_created"
    ORGANIZATION_UPDATED = "organization_updated"
    MEMBER_ADDED = "member_added"
    MEMBER_REMOVED = "member_removed"
    MEMBER_ROLE_CHANGED = "member_role_changed"
    MEMBER_STATUS_CHANGED = "member_status_changed"
    # projects
    PROJECT_CREATED = "project_created"
    PROJECT_UPDATED = "project_updated"
    PROJECT_STATUS_CHANGED = "project_status_changed"
    PROJECT_DELETED = "project_deleted"
    PROJECT_MEMBER_ADDED = "project_member_added"
    PROJECT_MEMBER_REMOVED = "project_member_removed"
    # tasks
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_ASSIGNED = "task_assigned"
    TASK_STATUS_CHANGED = "task_status_changed"
    TASK_DELETED = "task_deleted"
    TASK_DEPENDENCY_ADDED = "task_dependency_added"
    TASK_DEPENDENCY_REMOVED = "task_dependency_removed"
    # comments and files
    COMMENT_ADDED = "comment_added"
    COMMENT_UPDATED = "comment_updated"
    COMMENT_DELETED = "comment_deleted"
    FILE_UPLOADED = "file_uploaded"
    FILE_DELETED = "file_deleted"


class AuditEntity(StrEnum):
    USER = "user"
    ORGANIZATION = "organization"
    ORGANIZATION_MEMBER = "organization_member"
    PROJECT = "project"
    PROJECT_MEMBER = "project_member"
    TASK = "task"
    TASK_DEPENDENCY = "task_dependency"
    COMMENT = "comment"
    ATTACHMENT = "attachment"


class FileKind(StrEnum):
    """What a file REALLY is, decided from its bytes (used in Part 2)."""

    PNG = "png"
    JPEG = "jpeg"
    GIF = "gif"
    WEBP = "webp"
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    TEXT = "text"


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class ProjectSortBy(StrEnum):
    NAME = "name"
    STATUS = "status"
    START_DATE = "start_date"
    DUE_DATE = "due_date"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class TaskSortBy(StrEnum):
    TITLE = "title"
    PRIORITY = "priority"
    STATUS = "status"
    POSITION = "position"
    DUE_DATE = "due_date"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"