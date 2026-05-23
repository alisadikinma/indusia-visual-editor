"""Helpers for the auth route layer to find/create users.

Kept tiny on purpose. Anything that does more than `select(User)` should
graduate to a real service module (e.g. once invitation flows ship in
v1.5)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.models import Organization, User, UserRole
from indusia_visual_editor.services.auth.passwords import hash_password

SEED_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class DuplicateEmailError(Exception):
    """Raised when signup tries to register an existing email."""


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def _resolve_org(
    session: AsyncSession, organization_slug: str | None
) -> Organization:
    if organization_slug:
        result = await session.execute(
            select(Organization).where(Organization.slug == organization_slug)
        )
        org = result.scalar_one_or_none()
        if org is not None:
            return org
    # Fall back to the seed org provisioned by migration 0011_auth. v1
    # single-tenant deploys only ever have one org; signup without a
    # slug joins that one.
    seed = await session.get(Organization, SEED_ORG_ID)
    if seed is not None:
        return seed
    # Defensive: if the seed row was deleted manually, recreate it so
    # signup never silently 500s in a fresh dev DB.
    seed = Organization(id=SEED_ORG_ID, name="Default", slug="default")
    session.add(seed)
    await session.flush()
    return seed


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    plaintext_password: str,
    organization_slug: str | None = None,
    role: UserRole = UserRole.ENGINEER,
) -> User:
    normalised_email = email.lower()
    existing = await get_user_by_email(session, normalised_email)
    if existing is not None:
        raise DuplicateEmailError(normalised_email)

    org = await _resolve_org(session, organization_slug)
    user = User(
        email=normalised_email,
        password_hash=hash_password(plaintext_password),
        role=role,
        organization_id=org.id,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user
