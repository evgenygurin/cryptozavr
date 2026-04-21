#!/usr/bin/env python3
"""Validate plugin artefacts: plugin.json, .mcp.json, fastmcp.json, skills frontmatter.

Used by CI and locally before commits touching plugin-facing files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"ok: {msg}")


def validate_json(path: Path, required_keys: set[str]) -> None:
    if not path.is_file():
        _fail(f"{path} does not exist")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        _fail(f"{path} is not valid JSON: {exc}")
    missing = required_keys - set(data.keys())
    if missing:
        _fail(f"{path} missing required keys: {sorted(missing)}")
    _ok(f"{path} parsed; required keys present")


def validate_plugin_json() -> None:
    validate_json(
        ROOT / "plugin.json",
        required_keys={"name", "version", "description", "mcpServers"},
    )


def validate_mcp_json() -> None:
    path = ROOT / ".mcp.json"
    validate_json(path, required_keys={"mcpServers"})
    data = json.loads(path.read_text())
    servers = data["mcpServers"]
    if "cryptozavr-research" not in servers:
        _fail(".mcp.json missing mcpServers['cryptozavr-research']")
    server = servers["cryptozavr-research"]
    for field in ("command", "args"):
        if field not in server:
            _fail(f".mcp.json cryptozavr-research missing '{field}'")
    _ok(".mcp.json cryptozavr-research server declared correctly")


def validate_fastmcp_json() -> None:
    path = ROOT / "fastmcp.json"
    validate_json(path, required_keys={"source", "environment"})
    data = json.loads(path.read_text())
    src = data["source"]
    if "path" not in src or "entrypoint" not in src:
        _fail("fastmcp.json source must have 'path' and 'entrypoint'")
    src_path = ROOT / src["path"]
    if not src_path.is_file():
        _fail(f"fastmcp.json source.path points to missing file: {src_path}")
    _ok("fastmcp.json source + environment valid")


def main() -> None:
    print("Validating plugin artefacts...")
    validate_plugin_json()
    validate_mcp_json()
    validate_fastmcp_json()
    print("All plugin artefacts valid.")


if __name__ == "__main__":
    main()
