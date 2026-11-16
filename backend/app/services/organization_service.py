from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.context import OrgContext
from app.core.enums import AuditAction, AuditEntity, OrgRole
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.utils import slugify
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.repositories.membership_repository import MembershipRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.common import PageParams
from app.schemas.organization import MemberAdd, OrganizationCreate, OrganizationUpdate
from app.services.audit_service import AuditService


class OrganizationService:
    def __init__(self, db: Session, audit: AuditService) -> None:
        self.db = db
        self.audit = audit
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
            self.audit.log(
                AuditAction.ORGANIZATION_CREATED,
                entity_type=AuditEntity.ORGANIZATION,
                entity_id=org.id,
                user_id=user.id,
                organization_id=org.id,
                metadata={"name": org.name, "slug": org.slug},
            )
            self.db.commit()  # org + admin membership + audit row: all or nothing
        except IntegrityError:
            self.db.rollback()
            raise ConflictError("ORGANIZATION_SLUG_EXISTS", "Slug is already in use.") from None
        return org

    def list_for_user(self, user: User, params: PageParams) -> tuple[list[Organization], int]:
        if user.is_super_admin:
            return self.orgs.list_all(params)
        return self.orgs.list_for_user(user.id, params)

    def update(self, ctx: OrgContext, data: OrganizationUpdate) -> Organization:
        org = ctx.organization
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(org, field, value)
        if changes:
            self.audit.log(
                AuditAction.ORGANIZATION_UPDATED,
                entity_type=AuditEntity.ORGANIZATION,
                entity_id=org.id,
                user_id=ctx.user.id,
                organization_id=org.id,
                metadata={"changed_fields": sorted(changes)},
            )
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

    def add_member(self, ctx: OrgContext, data: MemberAdd) -> OrganizationMember:
        org = ctx.organization
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
            self._log_member(
                AuditAction.MEMBER_ADDED,
                ctx,
                membership.id,
                user_id=user.id,
                role=data.role.value,
            )
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ConflictError("MEMBER_ALREADY_EXISTS", "User is already a member.") from None
        return membership

    def change_role(self, ctx: OrgContext, user_id: int, role: OrgRole) -> OrganizationMember:
        membership = self._get_member(ctx.organization.id, user_id)
        old_role = membership.role
        if role == old_role:
            return membership
        if role != OrgRole.ORG_ADMIN:
            self._ensure_not_last_admin(ctx.organization.id, membership)

        membership.role = role
        self._log_member(
            AuditAction.MEMBER_ROLE_CHANGED,
            ctx,
            membership.id,
            user_id=user_id,
            from_role=old_role.value,
            to_role=role.value,
        )
        self.db.commit()
        return membership

    def set_member_active(
        self, ctx: OrgContext, user_id: int, is_active: bool
    ) -> OrganizationMember:
        membership = self._get_member(ctx.organization.id, user_id)
        if membership.is_active == is_active:
            return membership
        if not is_active:
            self._ensure_not_last_admin(ctx.organization.id, membership)

        membership.is_active = is_active
        self._log_member(
            AuditAction.MEMBER_STATUS_CHANGED,
            ctx,
            membership.id,
            user_id=user_id,
            is_active=is_active,
        )
        self.db.commit()
        return membership

    def remove_member(self, ctx: OrgContext, user_id: int) -> None:
        membership = self._get_member(ctx.organization.id, user_id)
        self._ensure_not_last_admin(ctx.organization.id, membership)

        membership_id = membership.id
        role = membership.role.value
        self.members.delete(membership)
        self._log_member(
            AuditAction.MEMBER_REMOVED, ctx, membership_id, user_id=user_id, role=role
        )
        self.db.commit()

    # ---------- helpers ----------
    def _log_member(
        self, action: AuditAction, ctx: OrgContext, membership_id: int, **metadata: object
    ) -> None:
        self.audit.log(
            action,
            entity_type=AuditEntity.ORGANIZATION_MEMBER,
            entity_id=membership_id,
            user_id=ctx.user.id,
            organization_id=ctx.organization.id,
            metadata=dict(metadata),
        )

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