#!/usr/bin/env python3
"""Bundle explicitly listed local assets into a self-contained HTML file."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


MEDIA_TYPE_RE = re.compile(
    r"^[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+(?:;[A-Za-z0-9._-]+=[A-Za-z0-9._-]+)*$"
)


class BundleError(ValueError):
    """Raised when the bundle manifest or source does not pass validation."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BundleError(f"cannot read manifest: {error}") from error
    if not isinstance(value, dict):
        raise BundleError("manifest root must be an object")
    return value


def resolve_asset(manifest_root: Path, relative_path: object) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise BundleError("entry.path must be a non-empty string")
    candidate = (manifest_root / relative_path).resolve()
    try:
        candidate.relative_to(manifest_root)
    except ValueError as error:
        raise BundleError(f"entry.path escapes manifest directory: {relative_path}") from error
    if not candidate.is_file():
        raise BundleError(f"asset is not a regular file: {relative_path}")
    return candidate


def validate_hash(data: bytes, expected: object, label: str) -> None:
    if expected is None:
        return
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise BundleError(f"{label} must be a lowercase SHA-256 hex digest")
    actual = sha256(data)
    if actual != expected:
        raise BundleError(f"{label} mismatch: expected {expected}, got {actual}")


def embed_entries(
    text: str,
    entries: object,
    manifest_root: Path,
    stack: tuple[Path, ...] = (),
) -> str:
    if not isinstance(entries, list):
        raise BundleError("entries must be an array")

    seen_references: set[str] = set()
    for index, entry in enumerate(entries):
        label = f"entries[{index}]"
        if not isinstance(entry, dict):
            raise BundleError(f"{label} must be an object")

        reference = entry.get("reference")
        media_type = entry.get("media_type")
        if not isinstance(reference, str) or not reference:
            raise BundleError(f"{label}.reference must be a non-empty string")
        if reference in seen_references:
            raise BundleError(f"duplicate reference in one document: {reference}")
        seen_references.add(reference)
        if not isinstance(media_type, str) or not MEDIA_TYPE_RE.fullmatch(media_type):
            raise BundleError(f"{label}.media_type is invalid")

        expected_occurrences = entry.get("expected_occurrences")
        if (
            not isinstance(expected_occurrences, int)
            or isinstance(expected_occurrences, bool)
            or expected_occurrences < 1
        ):
            raise BundleError(f"{label}.expected_occurrences must be a positive integer")

        actual_occurrences = text.count(reference)
        if actual_occurrences != expected_occurrences:
            raise BundleError(
                f"{label} occurrence mismatch for {reference!r}: "
                f"expected {expected_occurrences}, got {actual_occurrences}"
            )

        asset_path = resolve_asset(manifest_root, entry.get("path"))
        if asset_path in stack:
            raise BundleError(f"nested HTML cycle detected at {entry.get('path')}")
        try:
            payload = asset_path.read_bytes()
        except OSError as error:
            raise BundleError(f"cannot read asset {entry.get('path')}: {error}") from error
        validate_hash(payload, entry.get("source_sha256"), f"{label}.source_sha256")

        nested_entries = entry.get("entries")
        if nested_entries is not None:
            if media_type.split(";", 1)[0] != "text/html":
                raise BundleError(f"{label}.entries is only valid for text/html assets")
            try:
                nested_text = payload.decode("utf-8")
            except UnicodeDecodeError as error:
                raise BundleError(f"nested HTML is not UTF-8: {entry.get('path')}") from error
            nested_text = embed_entries(
                nested_text,
                nested_entries,
                manifest_root,
                stack + (asset_path,),
            )
            payload = nested_text.encode("utf-8")

        data_uri = f"data:{media_type};base64,{base64.b64encode(payload).decode('ascii')}"
        text = text.replace(reference, data_uri)

    return text


def build(source: Path, manifest_path: Path) -> bytes:
    manifest = read_json(manifest_path)
    if manifest.get("schema_version") != 1:
        raise BundleError("manifest.schema_version must be 1")

    try:
        source_bytes = source.read_bytes()
    except OSError as error:
        raise BundleError(f"cannot read source HTML: {error}") from error
    validate_hash(source_bytes, manifest.get("source_sha256"), "source_sha256")
    try:
        source_text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise BundleError("source HTML must be UTF-8") from error

    manifest_root = manifest_path.resolve().parent
    bundled = embed_entries(source_text, manifest.get("entries"), manifest_root)
    return bundled.encode("utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bundle manifest-listed local assets into a self-contained HTML file."
    )
    parser.add_argument("source", type=Path, help="UTF-8 source HTML")
    parser.add_argument("manifest", type=Path, help="JSON bundle manifest")
    parser.add_argument("output", type=Path, help="output HTML")
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the generated bytes with an existing output without writing",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        bundled = build(args.source.resolve(), args.manifest.resolve())
        output = args.output.resolve()
        digest = sha256(bundled)
        if args.check:
            if not output.is_file():
                raise BundleError(f"check target does not exist: {output}")
            existing = output.read_bytes()
            if existing != bundled:
                raise BundleError(
                    f"check failed: generated SHA-256 {digest}, "
                    f"existing SHA-256 {sha256(existing)}"
                )
            print(f"OK {output} sha256={digest} bytes={len(bundled)}")
            return 0

        if output.exists():
            raise BundleError(f"refusing to overwrite existing output: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(bundled)
        print(f"WROTE {output} sha256={digest} bytes={len(bundled)}")
        return 0
    except (BundleError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
