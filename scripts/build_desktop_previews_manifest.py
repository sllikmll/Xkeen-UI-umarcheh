#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

PRODUCTION_FEATURES = [
    "runtime-start-stop-restart",
    "mihomo-version-health",
    "selector-list-and-tiles",
    "select-proxy",
    "per-node-ping",
    "proxy-table",
    "provider-update",
    "connections-table",
    "close-connection",
    "config-read-save-validate",
    "subscription-add-update-delete",
    "static-proxy-import-update-delete",
    "rule-providers",
    "dns-routes-manual-resolver",
    "logs-viewer",
    "settings-runtime-paths",
    "subscription-update-delete",
    "static-proxy-delete",
]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", type=Path, default=Path("dist-artifacts"))
    ap.add_argument("--version", default="0.4.1")
    ap.add_argument("--tag", default="v0.4.1-desktop-user-test")
    ns = ap.parse_args()
    expected = [
        "Unified-UI-Avalonia-UserTest-0.4.1-win-x64.zip",
        "Unified-UI-WPF-UserTest-0.4.1-win-x64.zip",
        "Unified-UI-Cpp-Win32-UserTest-0.4.1-win-x64.zip",
    ]
    artifacts = []
    errors = []
    for name in expected:
        p = ns.dist / name
        if not p.exists():
            errors.append(f"missing {name}")
            continue
        artifacts.append(
            {
                "file": name,
                "size": p.stat().st_size,
                "sha256": sha(p),
                "download_url": f"https://github.com/sllikmll/Unified-UI/releases/download/{ns.tag}/{name}",
            }
        )
    manifest = {
        "version": ns.version,
        "release_tag": ns.tag,
        "quality": "user-test-production",
        "backend": "unified-ui-native-bridge",
        "features": PRODUCTION_FEATURES,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "errors": errors,
    }
    out = ns.dist / "desktop-production-candidates-manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    # Compatibility alias for old README/tooling paths.
    (ns.dist / "desktop-previews-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    sums = "".join(f"{a['sha256']}  {a['file']}\n" for a in artifacts)
    (ns.dist / "DESKTOP_PREVIEWS_SHA256SUMS").write_text(sums, encoding="utf-8")
    print(json.dumps({"ok": not errors, "artifact_count": len(artifacts), "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
