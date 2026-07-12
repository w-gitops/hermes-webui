"""Deterministic organization policy evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from api.hermes_org_policy.bundle import PolicyBundle

Action = Literal[
    "read",
    "board_list",
    "board_switch",
    "board_manage",
    "task_create",
    "task_mutate",
    "task_admit",
    "dispatch_spawn",
    "kanban_tool",
    "override",
    "config_mutate",
]

ActorKind = Literal["executive", "orchestrator", "dispatcher", "worker", "unknown"]


@dataclass
class PolicyContext:
    actor_id: str
    actor_kind: ActorKind = "unknown"
    principal: str | None = None
    board: str | None = None
    requested_board: str | None = None
    assignee_profile: str | None = None
    department: str | None = None
    capability: str | None = None
    is_root_task: bool = False
    has_authenticated_override: bool = False
    kanban_tool_name: str | None = None
    kanban_board_arg: str | None = None
    injected_board: str | None = None
    policy_mode: str = "policy_required"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    code: str
    normalized_board: str | None = None
    required_assignee: str | None = None
    stamp: dict[str, str] | None = None


def _executive(bundle: PolicyBundle, ctx: PolicyContext) -> dict[str, Any] | None:
    pid = ctx.principal or ctx.actor_id
    principals = bundle.org.get("principals") or {}
    cfg = principals.get(pid)
    return cfg if isinstance(cfg, dict) else None


def _profile_capabilities(bundle: PolicyBundle) -> dict[str, set[str]]:
    caps: dict[str, set[str]] = {}
    for cap_name, spec in (bundle.org.get("capabilities") or {}).items():
        if not isinstance(spec, dict):
            continue
        for prof in spec.get("profiles") or []:
            caps.setdefault(str(prof), set()).add(str(cap_name))
    for dept_name, spec in (bundle.org.get("departments") or {}).items():
        if not isinstance(spec, dict):
            continue
        for cap in spec.get("capabilities") or []:
            for prof in spec.get("profiles") or []:
                caps.setdefault(str(prof), set()).add(str(cap))
    return caps


def _board_allowed(exec_cfg: dict[str, Any], board: str) -> bool:
    allowed = [str(b) for b in exec_cfg.get("allowed_boards") or []]
    if board in allowed:
        return True
    for prefix in exec_cfg.get("allowed_board_prefixes") or []:
        p = str(prefix)
        if p and board.startswith(p):
            return True
    return False


def _resolve_board(exec_cfg: dict[str, Any], ctx: PolicyContext) -> str | None:
    if ctx.requested_board:
        return ctx.requested_board
    if ctx.board:
        return ctx.board
    return str(exec_cfg.get("default_board") or "") or None


def _deny(code: str, reason: str) -> Decision:
    return Decision(allowed=False, reason=reason, code=code)


def _allow(code: str, reason: str, *, board: str | None = None, assignee: str | None = None, stamp: dict | None = None) -> Decision:
    return Decision(allowed=True, reason=reason, code=code, normalized_board=board, required_assignee=assignee, stamp=stamp)


def evaluate(bundle: PolicyBundle | None, action: Action, ctx: PolicyContext) -> Decision:
    if ctx.policy_mode == "legacy_unrestricted":
        return _allow("legacy_allow", "legacy unrestricted mode")

    if bundle is None:
        return _deny("policy_missing", "policy_required but no bundle loaded")

    if action in ("read", "board_list", "board_switch"):
        exec_cfg = _executive(bundle, ctx)
        if exec_cfg:
            board = _resolve_board(exec_cfg, ctx)
            if not board:
                return _deny("board_missing", "no board resolved")
            if not _board_allowed(exec_cfg, board):
                return _deny("board_forbidden", f"board {board} not allowed for {ctx.principal or ctx.actor_id}")
            return _allow("board_ok", "board authorized", board=board)
        if ctx.actor_kind == "dispatcher":
            return _allow("dispatcher_board", "dispatcher may access boards")
        if ctx.actor_kind == "worker":
            if ctx.injected_board and ctx.requested_board and ctx.requested_board != ctx.injected_board:
                return _deny("worker_board_override", "worker cannot override injected board")
            return _allow("worker_board", "worker uses injected board", board=ctx.injected_board)
        if ctx.actor_id == "org-router":
            if ctx.board:
                return _allow("router_board", "router pinned to task board", board=ctx.board)
            return _deny("router_no_board", "org-router requires task board")
        return _deny("actor_unknown", f"unknown actor for board action: {ctx.actor_id}")

    if action == "task_create":
        exec_cfg = _executive(bundle, ctx)
        if not exec_cfg:
            return _deny("not_executive", "only executives use task_create admission rules")
        board = _resolve_board(exec_cfg, ctx)
        if not board or not _board_allowed(exec_cfg, board):
            return _deny("board_forbidden", "board not allowed for task create")
        tc = exec_cfg.get("task_create") or {}
        must = tc.get("root_assignee_must_be")
        assignee = ctx.assignee_profile
        if ctx.is_root_task and must:
            if assignee and assignee != must:
                forbidden = set(tc.get("forbid_direct_assignee_profiles") or [])
                if assignee and assignee != must:
                    return _deny(
                        "assignee_forbidden",
                        f"root task assignee must be {must}, got {assignee}",
                    )
            if not assignee:
                assignee = str(must)
        if assignee:
            prof_caps = _profile_capabilities(bundle)
            denied = set(exec_cfg.get("deny_capabilities") or [])
            for cap in prof_caps.get(assignee, set()):
                if cap in denied:
                    return _deny("capability_forbidden", f"assignee {assignee} implies denied capability {cap}")
        principal = ctx.principal or ctx.actor_id
        boards_meta = bundle.org.get("boards") or {}
        classification = (boards_meta.get(board) or {}).get("classification_default", "internal")
        stamp = {f: principal if f == "principal" else (board if f == "board" else principal if f == "created_by" else classification) for f in (tc.get("stamp_fields") or [])}
        return _allow("task_create_ok", "task create admitted", board=board, assignee=assignee, stamp=stamp)

    if action == "task_admit":
        return evaluate(bundle, "task_create", ctx)

    if action == "dispatch_spawn":
        disp = (bundle.org.get("system_actors") or {}).get("dispatcher") or {}
        if not disp.get("spawn", {}).get("enforce_policy", True):
            return _allow("spawn_legacy", "spawn enforcement disabled")
        principal = ctx.principal or ctx.extra.get("task_principal")
        assignee = ctx.assignee_profile
        board = ctx.board or ctx.injected_board
        if principal:
            exec_cfg = (bundle.org.get("principals") or {}).get(str(principal))
            if isinstance(exec_cfg, dict) and assignee:
                forbidden = set((exec_cfg.get("task_create") or {}).get("forbid_direct_assignee_profiles") or [])
                if assignee in forbidden:
                    return _deny("spawn_assignee_forbidden", f"spawn denied: {principal} -> {assignee}")
                denied_caps = set(exec_cfg.get("deny_capabilities") or [])
                for cap in _profile_capabilities(bundle).get(assignee, set()):
                    if cap in denied_caps:
                        return _deny("spawn_capability_forbidden", f"spawn denied capability {cap}")
        if ctx.is_root_task and principal and assignee:
            exec_cfg = (bundle.org.get("principals") or {}).get(str(principal))
            if isinstance(exec_cfg, dict):
                must = (exec_cfg.get("task_create") or {}).get("root_assignee_must_be")
                if must and assignee != must and not ctx.has_authenticated_override:
                    return _deny("spawn_router_bypass", f"root must be assigned to {must}")
        if board and ctx.requested_board and ctx.requested_board != board:
            return _deny("spawn_board_mismatch", "spawn board mismatch")
        return _allow("spawn_ok", "dispatch spawn allowed", board=board)

    if action == "kanban_tool":
        if ctx.actor_kind == "worker" or ctx.actor_id == "task_worker":
            inj = ctx.injected_board
            arg = ctx.kanban_board_arg
            if arg and inj and arg != inj:
                return _deny("kanban_board_override", "kanban tool board override denied")
        exec_cfg = _executive(bundle, ctx)
        if exec_cfg:
            board = ctx.kanban_board_arg or _resolve_board(exec_cfg, ctx)
            if board and not _board_allowed(exec_cfg, board):
                return _deny("kanban_board_forbidden", f"kanban board {board} forbidden")
        return _allow("kanban_ok", "kanban tool allowed", board=ctx.kanban_board_arg or ctx.board)

    if action == "override":
        if ctx.has_authenticated_override:
            return _allow("override_ok", "authenticated override recorded")
        return _deny("override_required", "explicit authenticated override required")

    if action == "board_manage":
        return _deny("board_manage_denied", "board management not enabled in wp1")

    if action == "config_mutate":
        return _deny("config_mutate_denied", "config mutation denied for actor")

    return _deny("action_unknown", f"unhandled action {action}")