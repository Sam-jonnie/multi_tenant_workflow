from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.context import OrgContext, ProjectContext
from app.core.enums import OrgRole, ProjectStatus
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.core.permissions import has_min_role
from app.core.workflow import PROJECT_TRANSITIONS, ensure_transition
from app.models.project import Project, ProjectMember
from app.repositories.membership_repository import MembershipRepository
from app.repositories.project_repository import ProjectMemberRepository, ProjectRepository
from app.schemas.common import PageParams
from app.schemas.project import ProjectCreate, ProjectListQuery, ProjectUpdate


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.projects = ProjectRepository(db)
        self.members = ProjectMemberRepository(db)
        self.org_members = MembershipRepository(db)

    # ---------- projects ----------
    def create(self, ctx: OrgContext, data: ProjectCreate) -> Project:
        self._ensure_name_free(ctx.organization.id, data.name)
        project = Project(
            organization_id=ctx.organization.id,
            name=data.name,
            description=data.description,
            owner_id=ctx.user.id,
            start_date=data.start_date,
            due_date=data.due_date,
        )
        try:
            self.projects.add(project)
            self.members.add(ProjectMember(project_id=project.id, user_id=ctx.user.id))
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ConflictError("PROJECT_NAME_EXISTS", "A project with this name exists.") from None
        return project

    def list_projects(
        self, ctx: OrgContext, query: ProjectListQuery
    ) -> tuple[list[Project], int]:
        member_user_id = None if ctx.is_admin else ctx.user.id
        return self.projects.list_for_org(ctx.organization.id, query, member_user_id)

    def update(self, pctx: ProjectContext, data: ProjectUpdate) -> Project:
        project = pctx.project
        self._ensure_not_archived(project)
        changes = data.model_dump(exclude_unset=True)
        new_owner_id = changes.pop("owner_id", None)

        if "name" in changes and changes["name"].lower() != project.name.lower():
            self._ensure_name_free(project.organization_id, changes["name"])

        start = changes.get("start_date", project.start_date)
        due = changes.get("due_date", project.due_date)
        if start and due and due < start:
            raise BadRequestError("INVALID_DATE_RANGE", "due_date must be on or after start_date.")

        if new_owner_id is not None and new_owner_id != project.owner_id:
            if not pctx.org.is_admin:
                raise ForbiddenError("OWNER_CHANGE_DENIED", "Only an org admin can change the owner.")
            self._set_owner(project, new_owner_id)

        for field, value in changes.items():
            setattr(project, field, value)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ConflictError("PROJECT_NAME_EXISTS", "A project with this name exists.") from None
        self.db.refresh(project)
        return project

    def change_status(self, pctx: ProjectContext, new_status: ProjectStatus) -> Project:
        project = pctx.project
        ensure_transition(
            PROJECT_TRANSITIONS,
            project.status,
            new_status,
            code="INVALID_PROJECT_STATUS_TRANSITION",
            entity="project",
        )
        project.status = new_status
        self.db.commit()
        self.db.refresh(project)
        return project

    def delete(self, pctx: ProjectContext) -> None:
        project = pctx.project
        if pctx.org.is_admin:
            deletable = {ProjectStatus.PLANNING, ProjectStatus.ARCHIVED}
        elif pctx.is_owner and has_min_role(pctx.org.role, OrgRole.PROJECT_MANAGER):
            deletable = {ProjectStatus.PLANNING}
        else:
            raise ForbiddenError(
                "PROJECT_DELETE_DENIED", "Only the owner or an org admin can delete a project."
            )
        if project.status not in deletable:
            raise ConflictError(
                "PROJECT_DELETE_NOT_ALLOWED",
                f"A project in '{project.status}' status cannot be deleted by you.",
            )
        self.projects.delete(project)
        self.db.commit()

    # ---------- members ----------
    def list_members(
        self, pctx: ProjectContext, params: PageParams
    ) -> tuple[list[ProjectMember], int]:
        return self.members.list_for_project(pctx.project.id, params)

    def add_member(self, pctx: ProjectContext, user_id: int) -> ProjectMember:
        project = pctx.project
        self._ensure_not_archived(project)

        # Tenant check: the user must be an active member of THIS project's organization.
        org_membership = self.org_members.get(project.organization_id, user_id)
        if org_membership is None or not org_membership.is_active:
            raise BadRequestError(
                "USER_NOT_IN_ORGANIZATION", "User is not an active member of this organization."
            )
        if self.members.get(project.id, user_id):
            raise ConflictError("PROJECT_MEMBER_EXISTS", "User is already a project member.")

        member = ProjectMember(project_id=project.id, user_id=user_id)
        try:
            self.members.add(member)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ConflictError("PROJECT_MEMBER_EXISTS", "User is already a project member.") from None
        return member

    def remove_member(self, pctx: ProjectContext, user_id: int) -> None:
        project = pctx.project
        self._ensure_not_archived(project)
        if user_id == project.owner_id:
            raise ConflictError(
                "OWNER_CANNOT_BE_REMOVED", "Transfer ownership before removing the owner."
            )
        member = self.members.get(project.id, user_id)
        if member is None:
            raise NotFoundError("PROJECT_MEMBER_NOT_FOUND", "User is not a member of this project.")
        self.members.delete(member)
        self.db.commit()

    # ---------- helpers ----------
    def _ensure_name_free(self, org_id: int, name: str) -> None:
        if self.projects.get_by_name(org_id, name):
            raise ConflictError(
                "PROJECT_NAME_EXISTS", "A project with this name already exists in the organization."
            )

    @staticmethod
    def _ensure_not_archived(project: Project) -> None:
        if project.status == ProjectStatus.ARCHIVED:
            raise ConflictError("PROJECT_ARCHIVED", "Archived projects are read-only.")

    def _set_owner(self, project: Project, new_owner_id: int) -> None:
        membership = self.org_members.get(project.organization_id, new_owner_id)
        if membership is None or not membership.is_active:
            raise BadRequestError(
                "INVALID_OWNER", "The new owner must be an active member of this organization."
            )
        if not has_min_role(membership.role, OrgRole.PROJECT_MANAGER):
            raise BadRequestError("INVALID_OWNER", "The owner must be a project manager or admin.")
        project.owner_id = new_owner_id
        if self.members.get(project.id, new_owner_id) is None:
            self.members.add(ProjectMember(project_id=project.id, user_id=new_owner_id))