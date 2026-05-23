"""Phase 13.4 — RBAC + org-scope filter.

End-to-end tests against the live FastAPI app. Each test signs up a user
with a specific role (set via direct DB write since signup defaults to
engineer), then asserts the role gate works as designed.

Cross-org isolation: engineer of org A must NOT see / mutate org B's
projects. The list_projects route is scoped by current_user.organization_id;
the get_project / update_project / delete_project paths refuse rows that
belong to a different org.
"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import (
    Organization,
    Project,
    User,
    UserRole,
)
from indusia_visual_editor.main import app
from indusia_visual_editor.services.auth.dependencies import (
    get_current_user,
    get_current_user_optional,
)
from indusia_visual_editor.services.auth.passwords import hash_password


DB_URL = os.environ.get("IVE_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DB_URL, reason="IVE_DATABASE_URL not set"
)


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _assert_envelope(body: dict, expect_status: bool) -> None:
    assert set(body.keys()) == {"status", "message", "data"}
    assert body["status"] is expect_status


@pytest.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine(DB_URL, echo=False, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _create_user_with_role(
    db_session: AsyncSession, role: UserRole, org_id: uuid.UUID | None = None
) -> User:
    if org_id is None:
        org = Organization(name=_unique("org"), slug=_unique("org"))
        db_session.add(org)
        await db_session.flush()
        org_id = org.id
    user = User(
        organization_id=org_id,
        email=f"{_unique(role.value)}@indusiatest.dev",
        password_hash=hash_password("not-used-here-2026"),
        role=role,
    )
    db_session.add(user)
    await db_session.commit()
    return user


def _override_current_user(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_user_optional] = lambda: user


def _clear_override() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_user_optional, None)


@pytest.mark.asyncio
async def test_engineer_can_create_project(
    client: AsyncClient, db_session: AsyncSession
):
    eng = await _create_user_with_role(db_session, UserRole.ENGINEER)
    _override_current_user(eng)
    try:
        response = await client.post(
            "/api/projects",
            json={"name": "engineer-can-create", "slug": _unique("eng")},
            headers={"Authorization": "Bearer any"},
        )
        assert response.status_code == 201, response.text
    finally:
        _clear_override()


@pytest.mark.asyncio
async def test_viewer_cannot_create_project(
    client: AsyncClient, db_session: AsyncSession
):
    viewer = await _create_user_with_role(db_session, UserRole.VIEWER)
    _override_current_user(viewer)
    try:
        response = await client.post(
            "/api/projects",
            json={"name": "viewer-blocked", "slug": _unique("viewer")},
            headers={"Authorization": "Bearer any"},
        )
        assert response.status_code == 403, response.text
        _assert_envelope(response.json(), expect_status=False)
    finally:
        _clear_override()


@pytest.mark.asyncio
async def test_engineer_cannot_delete_project(
    client: AsyncClient, db_session: AsyncSession
):
    """Delete is admin-only in v1 — engineer is a 403 even on their own org."""
    eng = await _create_user_with_role(db_session, UserRole.ENGINEER)
    _override_current_user(eng)
    try:
        # Engineer creates a project they own.
        create = await client.post(
            "/api/projects",
            json={"name": "engineer-owned", "slug": _unique("eng-own")},
            headers={"Authorization": "Bearer any"},
        )
        assert create.status_code == 201, create.text
        project_id = create.json()["data"]["id"]

        delete = await client.delete(
            f"/api/projects/{project_id}",
            headers={"Authorization": "Bearer any"},
        )
        assert delete.status_code == 403, delete.text
        _assert_envelope(delete.json(), expect_status=False)
    finally:
        _clear_override()


@pytest.mark.asyncio
async def test_admin_can_delete_project(
    client: AsyncClient, db_session: AsyncSession
):
    admin = await _create_user_with_role(db_session, UserRole.ADMIN)
    _override_current_user(admin)
    try:
        create = await client.post(
            "/api/projects",
            json={"name": "admin-owned", "slug": _unique("adm-own")},
            headers={"Authorization": "Bearer any"},
        )
        project_id = create.json()["data"]["id"]
        delete = await client.delete(
            f"/api/projects/{project_id}",
            headers={"Authorization": "Bearer any"},
        )
        assert delete.status_code == 200, delete.text
    finally:
        _clear_override()


@pytest.mark.asyncio
async def test_list_projects_scoped_to_organization(
    client: AsyncClient, db_session: AsyncSession
):
    """Two engineers in two different orgs. Each one's GET /api/projects
    must NEVER return the other org's rows."""
    # Org A engineer
    eng_a = await _create_user_with_role(db_session, UserRole.ENGINEER)
    # Org B engineer
    eng_b = await _create_user_with_role(db_session, UserRole.ENGINEER)

    # Engineer A creates a project in their own org.
    _override_current_user(eng_a)
    try:
        slug_a = _unique("org-a")
        create_a = await client.post(
            "/api/projects",
            json={"name": "org-a-only", "slug": slug_a},
            headers={"Authorization": "Bearer any"},
        )
        assert create_a.status_code == 201, create_a.text
    finally:
        _clear_override()

    # Engineer B lists — must NOT see org A's project.
    _override_current_user(eng_b)
    try:
        listing = await client.get(
            "/api/projects",
            headers={"Authorization": "Bearer any"},
        )
        assert listing.status_code == 200
        slugs = [p["slug"] for p in listing.json()["data"]]
        assert slug_a not in slugs, (
            f"cross-org leak: org B engineer saw org A slug {slug_a!r}"
        )
    finally:
        _clear_override()
