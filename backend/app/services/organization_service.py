from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import OrgRole
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.utils import slugify
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.repositories.membership_repository import MembershipRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.common import PageParams
from app.schemas.organization import MemberAdd, OrganizationCreate, OrganizationUpdate


class OrganizationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.orgs = OrganizationRepository(db)
        self.members = MembershipRepository(db)
        self.users = UserRepository(db)

    # ---------- organizations ----------
    def create(self, user: User, data: OrganizationCreate) -> Organization:
        slug = data.slug or slugify(data.name)
        if not slug:
            raise BadRequestError("INVALID_SLUG", "Could not build a slug from the name.")
        if self.orgs.get_by_slug(slug):
            raise ConflictError("ORGANIZATION_SLUG_EXISTS", "Slug is already in use.")

        org = Organization(
            name=data.name, slug=slug, description=data.description, created_by_id=user.id
        )
        try:
            self.orgs.add(org)
            self.members.add(
                OrganizationMember(organization_id=org.id, user_id=user.id, role=OrgRole.ORG_ADMIN)
            )
            self.db.commit()  # org + admin membership are saved together, or not at all
        except IntegrityError:
            self.db.rollback()
            raise ConflictError("ORGANIZATION_SLUG_EXISTS", "Slug is already in use.") from None
        return org

    def list_for_user(self, user: User, params: PageParams) -> tuple[list[Organization], int]:
        if user.is_super_admin:
            return self.orgs.list_all(params)
        return self.orgs.list_for_user(user.id, params)

    def update(self, org: Organization, data: OrganizationUpdate) -> Organization:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(org, field, value)
        self.db.commit()
        self.db.refresh(org)
        return org

    # ---------- members ----------
    def list_members(
        self,
        org: Organization,
        params: PageParams,
        search: str | None,
        role: OrgRole | None,
        is_active: bool | None,
    ) -> tuple[list[OrganizationMember], int]:
        return self.members.list_for_org(org.id, params, search, role, is_active)

    def add_member(self, org: Organization, data: MemberAdd) -> OrganizationMember:
        user = self.users.get_by_email(data.email.lower())
        if user is None:
            raise NotFoundError("USER_NOT_FOUND", "No user with that email exists.")
        if not user.is_active:
            raise BadRequestError("USER_INACTIVE", "Cannot add an inactive user.")
        if self.members.get(org.id, user.id):
            raise ConflictError("MEMBER_ALREADY_EXISTS", "User is already a member.")

        membership = OrganizationMember(organization_id=org.id, user_id=user.id, role=data.role)
        try:
            self.members.add(membership)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ConflictError("MEMBER_ALREADY_EXISTS", "User is already a member.") from None
        return membership

    def change_role(self, org: Organization, user_id: int, role: OrgRole) -> OrganizationMember:
        membership = self._get_member(org.id, user_id)
        if role != OrgRole.ORG_ADMIN:
            self._ensure_not_last_admin(org.id, membership)
        membership.role = role
        self.db.commit()
        return membership

    def set_member_active(
        self, org: Organization, user_id: int, is_active: bool
    ) -> OrganizationMember:
        membership = self._get_member(org.id, user_id)
        if not is_active:
            self._ensure_not_last_admin(org.id, membership)
        membership.is_active = is_active
        self.db.commit()
        return membership

    def remove_member(self, org: Organization, user_id: int) -> None:
        membership = self._get_member(org.id, user_id)
        self._ensure_not_last_admin(org.id, membership)
        self.members.delete(membership)
        self.db.commit()

    # ---------- helpers ----------
    def _get_member(self, org_id: int, user_id: int) -> OrganizationMember:
        membership = self.members.get(org_id, user_id)
        if membership is None:
            raise NotFoundError("MEMBER_NOT_FOUND", "Member not found in this organization.")
        return membership

    def _ensure_not_last_admin(self, org_id: int, membership: OrganizationMember) -> None:
        is_active_admin = membership.role == OrgRole.ORG_ADMIN and membership.is_active
        if is_active_admin and self.members.count_active_admins(org_id) <= 1:
            raise ConflictError(
                "LAST_ADMIN_PROTECTED",
                "An organization must keep at least one active admin.",
            )