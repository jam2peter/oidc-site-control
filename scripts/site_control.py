#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, NoReturn

FORMAT="OIDC_SITE_CONTROL_BUNDLE_V1"
MARKER=".site-control-release.json"
SAFE_PATH=re.compile(r"^[A-Za-z0-9._/-]+$")


def die(message: str) -> "NoReturn":
    raise SystemExit(f"ERROR: {message}")


def load_config(path: str) -> dict[str, Any]:
    with open(path,"r",encoding="utf-8") as fh:
        cfg=json.load(fh)
    if not isinstance(cfg,dict):
        raise ValueError("config must be an object")
    endpoint=str(cfg.get("endpoint","")).strip()
    audience=str(cfg.get("audience",endpoint)).strip()
    header=str(cfg.get("oidc_header","X-Site-Control-GitHub-OIDC")).strip()
    roots=cfg.get("allowed_roots")
    if not endpoint.startswith("https://"):
        raise ValueError("endpoint must use https")
    if not audience:
        raise ValueError("audience missing")
    if not re.fullmatch(r"[A-Za-z0-9-]{1,80}", header):
        raise ValueError("oidc_header invalid")
    if not isinstance(roots,list) or not roots or not all(re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}",str(x)) for x in roots):
        raise ValueError("allowed_roots invalid")
    return cfg


def safe_rel(path: str) -> bool:
    if not path or len(path)>240 or path.startswith("/") or "\x00" in path:
        return False
    if path==MARKER:
        return False
    if any(part in {"",".",".."} for part in path.split("/")):
        return False
    return SAFE_PATH.fullmatch(path) is not None


def validate_target(target: str, roots: list[str]) -> None:
    match=re.fullmatch(r"([a-z0-9][a-z0-9._-]{0,63})/([a-z0-9][a-z0-9._-]{0,63})",target)
    if not match:
        die("target must match <root>/<slug>")
    if match.group(1) not in roots:
        die("target root is not allowlisted")


def build_bundle(source: str, target: str, commit: str, cfg: dict[str,Any]) -> dict[str,Any]:
    validate_target(target,[str(x) for x in cfg["allowed_roots"]])
    if not re.fullmatch(r"[a-fA-F0-9]{40}",commit):
        die("source commit invalid")
    root=pathlib.Path(source).resolve()
    if not root.is_dir():
        die("source directory not found")
    limits=cfg.get("limits") if isinstance(cfg.get("limits"),dict) else {}
    max_files=int(limits.get("max_files",2000))
    max_bytes=int(limits.get("max_bytes",64*1024*1024))
    entries=[]
    total=0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            die(f"symlink not allowed: {path}")
        if not path.is_file():
            continue
        rel=path.relative_to(root).as_posix()
        if not safe_rel(rel):
            die(f"unsafe/reserved file path: {rel}")
        data=path.read_bytes()
        total+=len(data)
        if total>max_bytes:
            die("bundle exceeds byte limit")
        sha=hashlib.sha256(data).hexdigest()
        entries.append((rel,data,sha))
    if not entries or len(entries)>max_files:
        die("invalid file count")
    material=b"".join(rel.encode()+b"\0"+sha.encode()+b"\n" for rel,_,sha in entries)
    manifest=hashlib.sha256(material).hexdigest()
    idem="deploy:"+hashlib.sha256((target+"\0"+commit.lower()+"\0"+manifest).encode()).hexdigest()
    files={
        rel:{
            "sha256":sha,
            "encoding":"gzip+base64",
            "base64":base64.b64encode(gzip.compress(data,9)).decode("ascii")
        }
        for rel,data,sha in entries
    }
    return {
        "format":FORMAT,
        "source_commit":commit.lower(),
        "target":target,
        "manifest_sha256":manifest,
        "idempotency_key":idem,
        "files":files,
    }


def request_json(url: str, *, method="GET", headers=None, payload=None) -> tuple[int,dict[str,Any]]:
    data=None if payload is None else json.dumps(payload,separators=(",",":")).encode()
    h={"Accept":"application/json","User-Agent":"OIDC-Site-Control/0.1"}
    if headers: h.update(headers)
    if data is not None: h["Content-Type"]="application/json"
    req=urllib.request.Request(url,data=data,method=method,headers=h)
    try:
        with urllib.request.urlopen(req,timeout=45) as response:
            raw=response.read().decode("utf-8")
            return response.status,json.loads(raw or "{}")
    except urllib.error.HTTPError as exc:
        raw=exc.read().decode("utf-8",errors="replace")
        try: body=json.loads(raw or "{}")
        except json.JSONDecodeError: body={"error":"http_error"}
        return exc.code,body


def get_oidc_token(audience: str) -> str:
    url=os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL","")
    token=os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN","")
    if not url or not token:
        die("GitHub Actions OIDC unavailable; permissions.id-token=write is required")
    sep="&" if "?" in url else "?"
    status,data=request_json(
        url+sep+"audience="+urllib.parse.quote(audience,safe=""),
        headers={"Authorization":f"bearer {token}"}
    )
    if status!=200 or not data.get("value"):
        die(f"OIDC token request failed: HTTP {status}")
    return str(data["value"])


def api_call(cfg: dict[str,Any], action: str, *, method="GET", payload=None, query=None) -> dict[str,Any]:
    endpoint=str(cfg["endpoint"])
    params={"action":action}
    if query: params.update({k:str(v) for k,v in query.items()})
    sep="&" if "?" in endpoint else "?"
    url=endpoint.rstrip("?")+sep+urllib.parse.urlencode(params)
    oidc=get_oidc_token(str(cfg.get("audience") or endpoint))
    status,data=request_json(
        url,method=method,
        headers={str(cfg.get("oidc_header","X-Site-Control-GitHub-OIDC")):oidc},
        payload=payload
    )
    oidc=""
    if status not in (200,201):
        die(f"{action} failed: HTTP {status}: {data.get('error') or data.get('message') or 'unknown'}")
    return data


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--config",required=True)
    sub=parser.add_subparsers(dest="command",required=True)

    sub.add_parser("health")
    stage=sub.add_parser("stage"); stage.add_argument("--source",required=True); stage.add_argument("--target",required=True)
    inspect=sub.add_parser("inspect"); inspect.add_argument("--target",required=True)
    apply=sub.add_parser("apply"); apply.add_argument("--job-id",type=int,required=True)
    rollback=sub.add_parser("rollback"); rollback.add_argument("--deployment-id",type=int,required=True)

    args=parser.parse_args()
    cfg=load_config(args.config)

    if args.command=="health":
        out=api_call(cfg,"health")
    elif args.command=="stage":
        commit=os.environ.get("GITHUB_SHA","")
        bundle=build_bundle(args.source,args.target,commit,cfg)
        out=api_call(cfg,"deploy.stage",method="POST",payload=bundle)
        out.setdefault("manifest_sha256",bundle["manifest_sha256"])
    elif args.command=="inspect":
        validate_target(args.target,[str(x) for x in cfg["allowed_roots"]])
        out=api_call(cfg,"deploy.inspect",query={"target":args.target})
    elif args.command=="apply":
        if args.job_id<1: die("job id invalid")
        out=api_call(cfg,"deploy.apply",method="POST",query={"job_id":args.job_id})
    else:
        if args.deployment_id<1: die("deployment id invalid")
        out=api_call(cfg,"deploy.rollback",method="POST",query={"deployment_id":args.deployment_id})

    print(json.dumps(out,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
