"""Tests for WebUI organization policy integration (WP2)."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT.parent / "root" / "ourtools" / "hermes-org" / "policy.bundle.json"
# fallback when running in /opt/hermes
_ALT_BUNDLE = Path("/root/ourtools/hermes-org/policy.bundle.json")


def _bundle_path() -> Path:
    if _ALT_BUNDLE.is_file():
        return _ALT_BUNDLE
    return Path(__file__).resolve().parents[2] / "hermes-org" / "policy.bundle.json"


class OrgPolicyModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = mock.patch.dict(
            os.environ,
            {
                "HERMES_ORG_POLICY_MODE": "policy_required",
                "HERMES_ORG_POLICY_BUNDLE": str(_bundle_path()),
            },
            clear=False,
        )
        self.env.start()
        import importlib
        import api.org_policy as op

        importlib.reload(op)
        self.op = op
        op._BUNDLE = op._UNLOADED
        op._BUNDLE_LOADED = None

    def tearDown(self) -> None:
        self.env.stop()

    def test_quinn_denied_gandalf_board(self) -> None:
        with mock.patch("api.profiles._is_isolated_profile_mode", return_value=True), mock.patch(
            "api.profiles._isolated_profile_name", return_value="quinn"
        ):
            with self.assertRaises(self.op.OrgPolicyDeny):
                self.op.authorize_board(requested_board="gandalf")

    def test_gandalf_default_board(self) -> None:
        with mock.patch("api.profiles._is_isolated_profile_mode", return_value=True), mock.patch(
            "api.profiles._isolated_profile_name", return_value="gandalf"
        ):
            board = self.op.authorize_board(requested_board=None)
            self.assertEqual(board, "gandalf")

    def test_admit_rejects_infra_assignee(self) -> None:
        with mock.patch("api.profiles._is_isolated_profile_mode", return_value=True), mock.patch(
            "api.profiles._isolated_profile_name", return_value="quinn"
        ):
            with self.assertRaises(self.op.OrgPolicyDeny):
                self.op.admit_task_create(
                    {"title": "x", "assignee": "infra-engineer", "parents": []},
                    board="quinn",
                )


if __name__ == "__main__":
    unittest.main()