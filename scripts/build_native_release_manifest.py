#!/usr/bin/env python3
"""Build and validate Unified UI Native desktop release manifest.

This script is intentionally offline-friendly: it does not build PyInstaller or
Electron artifacts by itself. It validates a prepared artifact directory,
computes SHA256/size metadata, and writes a stable JSON manifest consumed by the
README/download portal/release notes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIST = REPO_ROOT / "dist-artifacts"
DEFAULT_OUT = REPO_ROOT / "dist-artifacts" / "native-release-manifest.json"


@dataclass(frozen=True)
class ExpectedArtifact:
    key: str
    label: str
    platform: str
    pattern: str
    required: bool = True


EXPECTED: tuple[ExpectedArtifact, ...] = (
    ExpectedArtifact("mac_arm64_zip", "macOS Apple Silicon portable ZIP", "macOS", r"Unified-UI-Native-.+-mac-arm64\.zip$"),
    ExpectedArtifact("win_setup_x64", "Windows x64 setup wizard", "Windows", r"Unified-UI-Native-Setup-.+-x64\.exe$"),
    ExpectedArtifact("win_standalone_x64", "Windows x64 standalone EXE", "Windows", r"Unified-UI-Native-(?!Setup-).+-x64\.exe$"),
    ExpectedArtifact("win_portable_x64", "Windows x64 portable ZIP", "Windows", r"Unified-UI-Native-.+-windows-x64-portable\.zip$"),
    ExpectedArtifact("linux_portable_x64", "Linux x64 portable tar.gz", "Linux", r"Unified-UI-Native-.+-linux-x64-portable\.tar\.gz$"),
    ExpectedArtifact("linux_deb_x64", "Linux Debian/Ubuntu package", "Linux", r"Unified-UI-Native-.+-linux-x64\.deb$"),
    ExpectedArtifact("linux_rpm_x64", "Linux RPM package", "Linux", r"Unified-UI-Native-.+-linux-x64\.rpm$"),
    ExpectedArtifact("sha256sums", "SHA256SUMS", "all", r"SHA256SUMS$", required=False),
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_artifact(dist: Path, spec: ExpectedArtifact) -> Path | None:
    regex = re.compile(spec.pattern)
    matches = sorted((p for p in dist.iterdir() if p.is_file() and regex.search(p.name)), key=lambda p: p.name)
    if not matches:
        return None
    # Prefer the most recently modified matching artifact when old release files
    # are still in the directory.
    return max(matches, key=lambda p: (p.stat().st_mtime, p.name))


def build_manifest(dist: Path, version: str, release_tag: str, release_base_url: str) -> tuple[dict, list[str]]:
    errors: list[str] = []
    artifacts: list[dict] = []
    for spec in EXPECTED:
        path = find_artifact(dist, spec)
        if path is None:
            if spec.required:
                errors.append(f"missing required artifact: {spec.key} ({spec.pattern})")
            continue
        rel_url = f"{release_base_url.rstrip('/')}/{path.name}" if release_base_url else ""
        artifacts.append({
            "key": spec.key,
            "label": spec.label,
            "platform": spec.platform,
            "file": path.name,
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
            "download_url": rel_url,
        })
    manifest = {
        "product": "Unified UI Native",
        "version": version,
        "release_tag": release_tag,
        "release_base_url": release_base_url,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    return manifest, errors


def write_sha256sums(dist: Path, artifacts: list[dict]) -> Path:
    sums = dist / "SHA256SUMS"
    lines = [f"{item['sha256']}  {item['file']}" for item in artifacts if item.get("key") != "sha256sums"]
    sums.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return sums


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=DEFAULT_DIST, help="Directory containing release artifacts")
    parser.add_argument("--version", default="2.6.4", help="Native product version")
    parser.add_argument("--tag", default="v2.6.4-native", help="GitHub release tag")
    parser.add_argument("--release-base-url", default="https://github.com/sllikmll/Unified-UI/releases/download/v2.6.4-native", help="Base URL for download links")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT, help="Manifest JSON path")
    parser.add_argument("--write-sha256sums", action="store_true", help="Regenerate dist/SHA256SUMS from found artifacts")
    parser.add_argument("--allow-missing", action="store_true", help="Write partial manifest instead of failing when required files are absent")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dist = args.dist.resolve()
    if not dist.is_dir():
        print(f"artifact directory not found: {dist}", file=sys.stderr)
        return 2
    manifest, errors = build_manifest(dist, args.version, args.tag, args.release_base_url)
    if args.write_sha256sums:
        sums = write_sha256sums(dist, manifest["artifacts"])
        # Rebuild after adding SHA256SUMS so it appears in manifest too.
        manifest, errors = build_manifest(dist, args.version, args.tag, args.release_base_url)
        manifest["sha256sums_file"] = sums.name
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": not errors or args.allow_missing, "output": str(args.output), "artifact_count": manifest["artifact_count"], "errors": errors}, ensure_ascii=False, indent=2))
    if errors and not args.allow_missing:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
