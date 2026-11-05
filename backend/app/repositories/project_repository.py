from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.core.enums import ProjectSortBy, ProjectStatus
from app.core.utils import escape_like
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.repositories.query_utils import order_by_clauses, paginate
from app.schemas.common import PageParams
from app.schemas.project import ProjectListQuery

SORT_COLUMNS = {
    ProjectSortBy.NAME: Project.name,
    ProjectSortBy.STATUS: Project.status,
    ProjectSortBy.START_DATE: Project.start_date,
    ProjectSortBy.DUE_DATE: Project.due_date,
    ProjectSortBy.CREATED_AT: Project.created_at,
    ProjectSortBy.UPDATED_AT: Project.updated_at,
}


class ProjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, project_id: int) -> Project | None:
        return self.db.scalar(
            select(Project).options(joinedload(Project.owner)).where(Project.id == project_id)
        )

    def get_by_name(self, org_id: int, name: str) -> Project | None:
        return self.db.scalar(
            select(Project).where(
                Project.organization_id == org_id, func.lower(Project.name) == name.lower()
            )
        )

    def add(self, project: Project) -> Project:
        self.db.add(project)
        self.db.flush()
        return project

    def delete(self, project: Project) -> None:
        self.db.delete(project)

    def list_for_org(
        self, org_id: int, query: ProjectListQuery, member_user_id: int | None
    ) -> tuple[list[Project], int]:
        stmt = select(Project).where(Project.organization_id == org_id)

        if member_user_id is not None:  # non-admins only see projects they belong to
            stmt = stmt.where(
                Project.id.in_(
                    select(ProjectMember.project_id).where(ProjectMember.user_id == member_user_id)
                )
            )
        if query.status is not None:
            stmt = stmt.where(Project.status == query.status)
        elif not query.include_archived:
            stmt = stmt.where(Project.status != ProjectStatus.ARCHIVED)
        if query.owner_id is not None:
            stmt = stmt.where(Project.owner_id == query.owner_id)
        if query.search:
            pattern = f"%{escape_like(query.search)}%"
            stmt = stmt.where(
                or_(
                    Project.name.ilike(pattern, escape="\\"),
                    Project.description.ilike(pattern, escape="\\"),
                )
            )
        if query.due_from:
            stmt = stmt.where(Project.due_date >= query.due_from)
        if query.due_to:
            stmt = stmt.where(Project.due_date <= query.due_to)

        return paginate(
            self.db,
            stmt,
            query,
            order_by=order_by_clauses(SORT_COLUMNS[query.sort_by], query.sort_order, Project.id),
            options=[joinedload(Project.owner)],
        )


class ProjectMemberRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, project_id: int, user_id: int) -> ProjectMember | None:
        return self.db.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
            )
        )

    def add(self, member: ProjectMember) -> ProjectMember:
        self.db.add(member)
        self.db.flush()
        return member

    def delete(self, member: ProjectMember) -> None:
        self.db.delete(member)

    def list_for_project(
        self, project_id: int, params: PageParams
    ) -> tuple[list[ProjectMember], int]:
        stmt = (
            select(ProjectMember)
            .join(ProjectMember.user)
            .where(ProjectMember.project_id == project_id)
        )
        return paginate(
            self.db,
            stmt,
            params,
            order_by=[User.full_name.asc(), ProjectMember.id.asc()],
            options=[contains_eager(ProjectMember.user)],
        )