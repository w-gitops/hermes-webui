"""Load and verify versioned Hermes organization policy bundles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore


class PolicyBundleError(Exception):
    """Policy bundle missing, malformed, or hash mismatch."""


@dataclass(frozen=True)
class PolicyBundle:
    schema_version: int
    release_tag: str
    content_hash: str
    org: dict[str, Any]
    path: Path | None = None

    def require_startup(self, *, expected_hash: str | None = None, policy_mode: str = "policy_required") -> None:
        if policy_mode == "policy_required":
            if expected_hash and expected_hash != self.content_hash:
                raise PolicyBundleError(f"hash mismatch: expected {expected_hash}, got {self.content_hash}")
        elif policy_mode != "legacy_unrestricted":
            raise PolicyBundleError(f"unknown policy_mode: {policy_mode}")


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(org: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(org).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def load_org_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PolicyBundleError(f"org yaml root must be mapping: {path}")
    return data


def validate_org(org: dict[str, Any], schema_path: Path | None = None) -> None:
    if jsonschema is None:
        return
    if schema_path is None:
        schema_path = Path(__file__).resolve().parents[2] / "schema" / "org.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=org, schema=schema)


def build_bundle(org: dict[str, Any], *, source_path: Path | None = None) -> PolicyBundle:
    validate_org(org)
    sv = int(org.get("schema_version", 0))
    tag = str(org.get("release_tag", ""))
    if sv < 1 or not tag:
        raise PolicyBundleError("schema_version and release_tag required")
    return PolicyBundle(
        schema_version=sv,
        release_tag=tag,
        content_hash=content_hash(org),
        org=org,
        path=source_path,
    )


def bundle_document(bundle: PolicyBundle) -> dict[str, Any]:
    return {
        "schema_version": bundle.schema_version,
        "release_tag": bundle.release_tag,
        "content_hash": bundle.content_hash,
        "org": bundle.org,
    }


def write_bundle(bundle: PolicyBundle, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(bundle_document(bundle), indent=2) + "\n", encoding="utf-8")


def load_bundle(path: Path, *, verify_hash: bool = True, schema_path: Path | None = None) -> PolicyBundle:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise PolicyBundleError("bundle root must be object")
    org = raw.get("org")
    if not isinstance(org, dict):
        raise PolicyBundleError("bundle.org missing")
    validate_org(org, schema_path=schema_path)
    declared = str(raw.get("content_hash", ""))
    computed = content_hash(org)
    if verify_hash and declared and declared != computed:
        raise PolicyBundleError(f"bundle hash mismatch: declared {declared}, computed {computed}")
    bundle = PolicyBundle(
        schema_version=int(raw.get("schema_version", org.get("schema_version", 0))),
        release_tag=str(raw.get("release_tag", org.get("release_tag", ""))),
        content_hash=declared or computed,
        org=org,
        path=path,
    )
    return bundle


def load_bundle_for_mode(
    bundle_path: Path,
    *,
    policy_mode: str,
    expected_hash: str | None = None,
) -> PolicyBundle | None:
    if policy_mode == "legacy_unrestricted":
        return None
    if policy_mode != "policy_required":
        raise PolicyBundleError(f"unknown policy_mode: {policy_mode}")
    if not bundle_path.is_file():
        raise PolicyBundleError(f"policy bundle missing: {bundle_path}")
    bundle = load_bundle(bundle_path)
    bundle.require_startup(expected_hash=expected_hash, policy_mode=policy_mode)
    return bundle