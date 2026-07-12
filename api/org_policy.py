"""Hermes organization policy facade for the WebUI (WP2)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from api.hermes_org_policy.bundle import PolicyBundle, PolicyBundleError, load_bundle_for_mode
from api.hermes_org_policy.evaluate import PolicyContext, evaluate

logger = logging.getLogger(__name__)

_UNLOADED = object()
_BUNDLE: PolicyBundle | None | object = _UNLOADED
_BUNDLE_LOADED: PolicyBundle | None = None


class OrgPolicyDeny(Exception):
    def __init__(self, message: str, *, code: str = "denied", status: int = 403):
        super().__init__(message)
        self.code = code
        self.status = status


def policy_mode() -> str:
    return (os.environ.get("HERMES_ORG_POLICY_MODE") or "legacy_unrestricted").strip()


def bundle_path() -> Path:
    raw = os.environ.get("HERMES_ORG_POLICY_BUNDLE") or ""
    if raw.strip():
        return Path(raw).expanduser()
    # Default: sibling checkout on host
    return Path("/root/ourtools/hermes-org/policy.bundle.json")


def _load_bundle() -> PolicyBundle | None:
    global _BUNDLE, _BUNDLE_LOADED
    if _BUNDLE is not _UNLOADED:
        return _BUNDLE_LOADED  # type: ignore[return-value]
    mode = policy_mode()
    expected = (os.environ.get("HERMES_ORG_POLICY_HASH") or "").strip() or None
    try:
        _BUNDLE_LOADED = load_bundle_for_mode(
            bundle_path(),
            policy_mode=mode,
            expected_hash=expected,
        )
    except PolicyBundleError as exc:
        if mode == "policy_required":
            raise
        logger.warning("org policy bundle not loaded: %s", exc)
        _BUNDLE_LOADED = None
    _BUNDLE = _UNLOADED
    return _BUNDLE_LOADED


def ensure_startup() -> None:
    """Fail closed when policy_required and bundle invalid."""
    if policy_mode() == "policy_required":
        _load_bundle()
        b = _BUNDLE_LOADED
        logger.info(
            "org policy active mode=%s bundle=%s hash=%s",
            policy_mode(),
            bundle_path(),
            b.content_hash if b else "n/a",
        )


def enforcement_enabled() -> bool:
    return policy_mode() == "policy_required" and _load_bundle() is not None


def _principal() -> str | None:
    try:
        from api.profiles import _is_isolated_profile_mode, _isolated_profile_name

        if _is_isolated_profile_mode():
            return _isolated_profile_name()
    except Exception:
        pass
    return None


def authorize_board(
    *,
    requested_board: str | None,
    action: str = "board_switch",
) -> str | None:
    """Return normalized allowed board slug or raise OrgPolicyDeny."""
    if not enforcement_enabled():
        return requested_board
    principal = _principal()
    if not principal:
        return requested_board
    bundle = _load_bundle()
    ctx = PolicyContext(
        actor_id=principal,
        actor_kind="executive",
        principal=principal,
        requested_board=requested_board,
        policy_mode=policy_mode(),
    )
    decision = evaluate(bundle, "board_switch" if action == "board_switch" else "read", ctx)
    if not decision.allowed:
        status = 404 if action in ("read", "board_list") else 403
        raise OrgPolicyDeny(decision.reason, code=decision.code, status=status)
    return decision.normalized_board or requested_board


def filter_board_slugs(slugs: list[str]) -> list[str]:
    if not enforcement_enabled():
        return slugs
    principal = _principal()
    if not principal:
        return slugs
    bundle = _load_bundle()
    out: list[str] = []
    for slug in slugs:
        ctx = PolicyContext(
            actor_id=principal,
            actor_kind="executive",
            principal=principal,
            requested_board=slug,
            policy_mode=policy_mode(),
        )
        if evaluate(bundle, "read", ctx).allowed:
            out.append(slug)
    return out


def admit_task_create(body: dict, *, board: str | None) -> dict:
    """Server-side task admission; returns mutated body for create_task."""
    if not enforcement_enabled():
        return body
    principal = _principal()
    if not principal:
        return body
    bundle = _load_bundle()
    assignee = body.get("assignee")
    is_root = not body.get("parents")
    ctx = PolicyContext(
        actor_id=principal,
        actor_kind="executive",
        principal=principal,
        board=board,
        requested_board=board,
        assignee_profile=str(assignee) if assignee else None,
        is_root_task=bool(is_root),
        policy_mode=policy_mode(),
    )
    decision = evaluate(bundle, "task_create", ctx)
    if not decision.allowed:
        raise OrgPolicyDeny(decision.reason, code=decision.code, status=403)
    out = dict(body)
    if decision.required_assignee:
        out["assignee"] = decision.required_assignee
    out["created_by"] = principal
    return out


def authorize_project_os_board(requested_board: str) -> None:
    authorize_board(requested_board=requested_board or None, action="read")