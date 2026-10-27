from app.core.enums import OrgRole

# Higher number = more power. "At least project manager" becomes a simple comparison.
ROLE_RANK: dict[OrgRole, int] = {
    OrgRole.VIEWER: 1,
    OrgRole.TEAM_MEMBER: 2,
    OrgRole.PROJECT_MANAGER: 3,
    OrgRole.ORG_ADMIN: 4,
}


def has_min_role(role: OrgRole, minimum: OrgRole) -> bool:
    return ROLE_RANK[role] >= ROLE_RANK[minimum]