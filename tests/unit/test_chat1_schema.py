"""Unit tests: CHAT-1 schema structural checks (import + field presence)."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# ORM model field checks
# ---------------------------------------------------------------------------


def test_user_orm_importable():
    from app.infra.models import User  # noqa: F401


def test_user_orm_has_is_active():
    from app.infra.models import User

    assert hasattr(User, "is_active")


def test_widget_config_orm_has_structured_fields():
    from app.infra.models import WidgetConfig

    for field in (
        "public_widget_id",
        "owner_user_id",
        "allowed_origins",
        "theme",
        "greeting",
        "enabled_tools",
        "is_active",
    ):
        assert hasattr(WidgetConfig, field), f"WidgetConfig missing field: {field}"


def test_widget_config_orm_has_no_generic_fields():
    from app.infra.models import WidgetConfig

    # old generic schema must be gone
    assert not hasattr(WidgetConfig, "name")
    assert not hasattr(WidgetConfig, "config")


def test_audit_log_orm_has_renamed_fields():
    from app.infra.models import AuditLog

    for field in ("actor_user_id", "target_type", "target_id", "log_metadata"):
        assert hasattr(AuditLog, field), f"AuditLog missing field: {field}"


def test_audit_log_orm_has_no_old_field_names():
    from app.infra.models import AuditLog

    for old in ("user_id", "resource_type", "resource_id", "extra"):
        assert not hasattr(AuditLog, old), f"AuditLog still has old field: {old}"


def test_conversation_orm_has_widget_id():
    from app.infra.models import Conversation

    assert hasattr(Conversation, "widget_id")


# ---------------------------------------------------------------------------
# Domain model checks
# ---------------------------------------------------------------------------


def test_user_domain_has_is_active_default_true():
    from app.domain.models import UserDomain

    m = UserDomain(email="test@example.com")
    assert m.is_active is True


def test_widget_config_domain_structured():
    from app.domain.models import WidgetConfigDomain

    owner = uuid.uuid4()
    m = WidgetConfigDomain(owner_user_id=owner)
    assert m.allowed_origins == []
    assert m.enabled_tools == []
    assert m.theme == {}
    assert m.is_active is True
    assert m.greeting is None


def test_audit_log_domain_uses_renamed_fields():
    from app.domain.models import AuditLogDomain

    m = AuditLogDomain(action="write_memory", target_type="memory")
    assert m.actor_user_id is None
    assert m.target_id is None
    assert m.log_metadata is None


def test_conversation_domain_has_nullable_user_and_widget():
    from app.domain.models import ConversationDomain

    m = ConversationDomain()
    assert m.user_id is None
    assert m.widget_id is None


# ---------------------------------------------------------------------------
# Auth / widgets domain module checks
# ---------------------------------------------------------------------------


def test_auth_domain_errors_importable():
    from app.domain.auth import (  # noqa: F401
        ROLE_ADMIN,
        ROLE_USER,
        VALID_ROLES,
        InactiveUserError,
        InvalidCredentialsError,
        UserAlreadyExistsError,
        UserNotFoundError,
    )


def test_auth_role_constants():
    from app.domain.auth import ROLE_ADMIN, ROLE_USER, VALID_ROLES

    assert ROLE_USER == "user"
    assert ROLE_ADMIN == "admin"
    assert ROLE_USER in VALID_ROLES
    assert ROLE_ADMIN in VALID_ROLES


def test_widgets_domain_errors_importable():
    from app.domain.widgets import (  # noqa: F401
        WidgetInactiveError,
        WidgetNotFoundError,
        WidgetOriginDeniedError,
    )


# ---------------------------------------------------------------------------
# Repository import checks
# ---------------------------------------------------------------------------


def test_widget_config_repo_importable():
    from app.repositories.widget_configs import WidgetConfigRepository  # noqa: F401


def test_audit_log_repo_importable():
    from app.repositories.audit_logs import AuditLogRepository  # noqa: F401


# ---------------------------------------------------------------------------
# Migration smoke
# ---------------------------------------------------------------------------


def test_migration_002_exists_with_correct_revision():
    from app.core.paths import PROJECT_ROOT

    path = PROJECT_ROOT / "alembic" / "versions" / "002_chat1_schema.py"
    assert path.exists(), "002_chat1_schema.py migration file missing"
    text = path.read_text()
    assert '"002"' in text  # revision ID present
    assert '"001"' in text  # down_revision points to 001
