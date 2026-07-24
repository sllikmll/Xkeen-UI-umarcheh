#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--dist', type=Path, default=Path('dist-artifacts'))
    ap.add_argument('--version', default='0.1.0')
    ap.add_argument('--tag', default='v0.1.0-desktop-previews')
    ns=ap.parse_args()
    expected=[
      'Unified-UI-Avalonia-Preview-0.1.0-win-x64.zip',
      'Unified-UI-WPF-Preview-0.1.0-win-x64.zip',
      'Unified-UI-Cpp-Native-Preview-0.1.0-mac-arm64.zip',
    ]
    artifacts=[]; errors=[]
    for name in expected:
        p=ns.dist/name
        if not p.exists(): errors.append(f'missing {name}'); continue
        artifacts.append({'file':name,'size':p.stat().st_size,'sha256':sha(p),'download_url':f'https://github.com/sllikmll/Unified-UI/releases/download/{ns.tag}/{name}'})
    manifest={'version':ns.version,'release_tag':ns.tag,'artifact_count':len(artifacts),'artifacts':artifacts,'errors':errors}
    out=ns.dist/'desktop-previews-manifest.json'
    out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    sums=''.join(f"{a['sha256']}  {a['file']}
" for a in artifacts)
    (ns.dist/'DESKTOP_PREVIEWS_SHA256SUMS').write_text(sums,encoding='utf-8')
    print(json.dumps({'ok':not errors,'artifact_count':len(artifacts),'errors':errors},ensure_ascii=False,indent=2))
    return 0 if not errors else 1
if __name__=='__main__': raise SystemExit(main())
