#!/usr/bin/env python3
"""opnsense.py — OPNsense REST API client for agents. Standard library only.

Credentials are read from the environment, or from a .env file:

    OPNSENSE_URL=https://192.168.1.1        (or OPNSENSE_HOST=192.168.1.1)
    OPNSENSE_KEY=...
    OPNSENSE_SECRET=...
    OPNSENSE_INSECURE=1                     (self-signed certificate)

Subcommands:
    probe                      check connectivity, auth and firmware version
    find <terms...>            search the bundled index of 2399 endpoints
    show <module>/<controller> list every command of one controller
    get <path> [args...]       GET  /api/<path>/<args...>
    post <path> [args...]      POST /api/<path>/<args...>  (body via --data)
    backup [--out FILE]        download the running config.xml

Every request is validated against the bundled endpoint index first, so a
mistyped endpoint fails with a suggestion instead of a bare 404.
"""
from __future__ import annotations

import argparse
import base64
import difflib
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

INDEX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "endpoints.json")

# The published reference is generated per PHP class, so actions a controller
# inherits from a base class are missing from it. These are real and callable;
# without them, index validation would reject a valid request.
# FilterBaseController hands `apply` to every rule-style firewall controller.
INHERITED = {
    ("firewall", ctl): [("apply", "POST")]
    for ctl in ("filter", "d_nat", "source_nat", "one_to_one", "npt")
}

# Controllers whose changes are committed by a different controller.
SPECIAL_APPLY = {
    ("firewall", "filter"): "firewall/filter/apply",
    ("firewall", "d_nat"): "firewall/filter/apply",
    ("firewall", "source_nat"): "firewall/filter/apply",
    ("firewall", "one_to_one"): "firewall/filter/apply",
    ("firewall", "npt"): "firewall/filter/apply",
    ("firewall", "category"): "firewall/alias/reconfigure",
}

# Commands that ARE the commit step — they never need a follow-up apply.
COMMIT_COMMANDS = {"apply", "reconfigure", "reload", "restart", "start", "stop",
                   "reload_rules", "reloadRules"}


class ApiError(RuntimeError):
    pass


# --------------------------------------------------------------------------- config


def load_dotenv(explicit: str | None) -> None:
    """Populate os.environ from a .env file without overriding real env vars."""
    candidates = [explicit] if explicit else [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
    ]
    for path in candidates:
        if not path or not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = value
        return


def base_url() -> str:
    url = os.environ.get("OPNSENSE_URL") or os.environ.get("OPNSENSE_HOST", "")
    if not url:
        raise ApiError("set OPNSENSE_URL (or OPNSENSE_HOST) in the environment or a .env file")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


def auth_header() -> str:
    key = os.environ.get("OPNSENSE_KEY", "")
    secret = os.environ.get("OPNSENSE_SECRET", "")
    if not key or not secret:
        raise ApiError(
            "set OPNSENSE_KEY and OPNSENSE_SECRET. The REST API rejects username/password "
            "with 401 — generate a key pair under System > Access > Users > API keys, or "
            "POST /api/auth/user/addApiKey/<username>."
        )
    token = base64.b64encode(f"{key}:{secret}".encode()).decode()
    return "Basic " + token


def ssl_context() -> ssl.SSLContext | None:
    if os.environ.get("OPNSENSE_INSECURE", "").lower() in ("1", "true", "yes"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None


# --------------------------------------------------------------------------- index


_INDEX_CACHE = None


def load_index() -> dict:
    global _INDEX_CACHE
    if _INDEX_CACHE is not None:
        return _INDEX_CACHE
    if not os.path.isfile(INDEX_PATH):
        raise ApiError(f"endpoint index missing at {INDEX_PATH}")
    with open(INDEX_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    known = {(r["mod"], r["ctl"], r["cmd"]) for r in data["endpoints"]}
    for (mod, ctl), actions in INHERITED.items():
        for cmd, method in actions:
            if (mod, ctl, cmd) not in known:
                data["endpoints"].append({"m": method, "k": "core", "mod": mod, "ctl": ctl,
                                          "cmd": cmd, "camel": "", "p": "", "inherited": True})
    data["count"] = len(data["endpoints"])
    _INDEX_CACHE = data
    return data


def resolve_apply(mod: str, ctl: str) -> str | None:
    """Which endpoint commits a change made on mod/ctl, derived from the index."""
    special = SPECIAL_APPLY.get((mod, ctl))
    if special:
        return special
    rows = load_index()["endpoints"]
    for cmd in ("apply", "reconfigure"):
        if any(r["mod"] == mod and r["ctl"] == ctl and r["cmd"] == cmd for r in rows):
            return f"{mod}/{ctl}/{cmd}"
    # Most modules park the commit step on a dedicated service controller.
    for other in ("service", "general", "settings"):
        for cmd in ("reconfigure", "apply"):
            if any(r["mod"] == mod and r["ctl"] == other and r["cmd"] == cmd for r in rows):
                return f"{mod}/{other}/{cmd}"
    return None


def index_lookup(path: str):
    """Return the index row for module/controller/command, or None."""
    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) < 3:
        return None
    mod, ctl, cmd = parts[0], parts[1], parts[2]
    for row in load_index()["endpoints"]:
        if row["mod"] == mod and row["ctl"] == ctl and cmd in (row["cmd"], row["camel"]):
            return row
    return None


def suggest(path: str) -> str:
    parts = [p for p in path.strip("/").split("/") if p]
    rows = load_index()["endpoints"]
    if len(parts) >= 2:
        same = [r for r in rows if r["mod"] == parts[0] and r["ctl"] == parts[1]]
        if same:
            names = sorted({r["cmd"] for r in same})
            close = difflib.get_close_matches(parts[2] if len(parts) > 2 else "", names, 5, 0.3)
            listed = close or names[:15]
            return "commands on %s/%s: %s" % (parts[0], parts[1], ", ".join(listed))
    if parts:
        ctls = sorted({f"{r['mod']}/{r['ctl']}" for r in rows if r["mod"] == parts[0]})
        if ctls:
            return "controllers in module %s: %s" % (parts[0], ", ".join(ctls))
        mods = sorted({r["mod"] for r in rows})
        close = difflib.get_close_matches(parts[0], mods, 5, 0.3)
        if close:
            return "did you mean module: %s" % ", ".join(close)
    return "run `opnsense.py find <term>` to search all endpoints"


# --------------------------------------------------------------------------- http


def request(method: str, path: str, args, body=None, timeout=60, check_index=True):
    path = path.strip("/")
    if path.startswith("api/"):
        path = path[4:]

    if check_index:
        row = index_lookup(path)
        if row is None:
            raise ApiError(
                f"unknown endpoint /api/{path}\n  {suggest(path)}\n"
                "  (the reference omits inherited actions — pass --force to send it anyway)")
        # The reference states its method column is only the "most likely" verb,
        # inferred rather than declared — `wireguard/client/add_client` is listed
        # as GET. Treat a mismatch as a hint, never as a block.
        allowed = row["m"].replace(",", " ").split()
        if method not in allowed:
            print(f"note: the reference lists /api/{path} as {row['m']}; "
                  f"sending {method} anyway (the method column is inferred).",
                  file=sys.stderr)

    segments = [urllib.parse.quote(str(a), safe="") for a in (args or [])]
    url = "/".join([base_url(), "api", path] + segments)

    data = None
    headers = {"Authorization": auth_header(), "Accept": "application/json"}
    if method == "POST":
        data = json.dumps(body if body is not None else {}).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:600]
        if exc.code == 401:
            raise ApiError(
                "401 unauthorized — the API needs a key/secret pair, not the GUI password. "
                "Also confirm the key's user has the privilege for this endpoint."
            ) from exc
        if exc.code == 404:
            raise ApiError(f"404 on {url}\n  {suggest(path)}\n  body: {detail}") from exc
        raise ApiError(f"HTTP {exc.code} on {url}\n  {detail}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(
            f"cannot reach {url}: {exc.reason}\n"
            "  For a self-signed certificate set OPNSENSE_INSECURE=1."
        ) from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw}


def failed(payload) -> bool:
    """True when OPNsense returned HTTP 200 but refused the change."""
    if not isinstance(payload, dict):
        return False
    if payload.get("result") in ("failed", "error"):
        return True
    return bool(payload.get("validations"))


# --------------------------------------------------------------------------- commands


def emit(payload, raw=False):
    if raw and isinstance(payload, dict) and "_raw" in payload:
        sys.stdout.write(payload["_raw"])
        return
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def cmd_find(ns):
    rows = load_index()["endpoints"]
    terms = [t.lower() for t in ns.terms]
    hits = []
    for row in rows:
        if ns.module and row["mod"] != ns.module:
            continue
        hay = f"{row['mod']}/{row['ctl']}/{row['cmd']} {row['camel']} {row['p']}".lower()
        if all(t in hay for t in terms):
            hits.append(row)
    # No row matched every term. Fall back to any-term matches, ranked by how
    # many hit, so a search using the wrong vocabulary still lands somewhere —
    # WireGuard calls a peer a "client", Kea calls a lease a "reservation".
    partial = False
    if not hits and len(terms) > 1:
        scored = []
        for row in rows:
            if ns.module and row["mod"] != ns.module:
                continue
            hay = f"{row['mod']}/{row['ctl']}/{row['cmd']} {row['camel']} {row['p']}".lower()
            # A term naming the module is worth more than one matching a command
            # anywhere, so "wireguard peer" ranks wireguard above kea's add_peer.
            score = sum(2 if t in row["mod"].lower() else 1 for t in terms if t in hay)
            if score:
                scored.append((-score, row["mod"], row["ctl"], row["cmd"], row))
        scored.sort()
        hits = [s[4] for s in scored]
        partial = bool(hits)

    if ns.json:
        emit(hits)
        return 0 if hits else 1
    if not hits:
        print("no endpoint matches %s" % " ".join(ns.terms))
        return 1
    if partial:
        print("no endpoint matches all of %s — closest by partial match:\n"
              % " ".join(ns.terms))
    for row in hits[: ns.limit]:
        alias = f"  (camel: {row['camel']})" if row["camel"] else ""
        params = f"  params: {row['p']}" if row["p"] else ""
        print(f"{row['m']:9} /api/{row['mod']}/{row['ctl']}/{row['cmd']}{params}{alias}")
    if len(hits) > ns.limit:
        print(f"... {len(hits) - ns.limit} more (raise --limit)")
    return 0


def cmd_show(ns):
    target = ns.controller.strip("/").split("/")
    if len(target) != 2:
        print("usage: show <module>/<controller>", file=sys.stderr)
        return 2
    mod, ctl = target
    rows = [r for r in load_index()["endpoints"] if r["mod"] == mod and r["ctl"] == ctl]
    if not rows:
        print(suggest(mod), file=sys.stderr)
        return 1
    print(f"/api/{mod}/{ctl}/ — {len(rows)} commands")
    for row in rows:
        alias = f"  (camel: {row['camel']})" if row["camel"] else ""
        params = f"  params: {row['p']}" if row["p"] else ""
        note = "  [inherited, undocumented]" if row.get("inherited") else ""
        print(f"  {row['m']:9} {row['cmd']}{params}{alias}{note}")
    apply_to = resolve_apply(mod, ctl)
    if apply_to:
        print(f"\ncommit changes with: POST /api/{apply_to}")
    return 0


def read_body(spec):
    if spec is None:
        return None
    try:
        if spec.startswith("@"):
            with open(spec[1:], encoding="utf-8") as fh:
                return json.load(fh)
        return json.loads(spec)
    except FileNotFoundError as exc:
        raise ApiError(f"--data file not found: {spec[1:]}") from exc
    except json.JSONDecodeError as exc:
        where = spec[1:] if spec.startswith("@") else "--data argument"
        raise ApiError(
            f"invalid JSON in {where}: {exc}\n"
            "  Shell quoting mangles inline JSON easily — prefer --data @file.json."
        ) from exc


def cmd_get(ns):
    payload = request("GET", ns.path, ns.args, timeout=ns.timeout, check_index=not ns.force)
    emit(payload, ns.raw)
    return 1 if failed(payload) else 0


def cmd_post(ns):
    body = read_body(ns.data)
    parts = ns.path.strip("/").split("/")
    mod, ctl = (parts + ["", ""])[:2]
    cmd = parts[2] if len(parts) > 2 else ""
    apply_to = resolve_apply(mod, ctl) if mod and ctl else None
    needs_apply = apply_to and cmd not in COMMIT_COMMANDS

    if ns.dry_run:
        if index_lookup(ns.path.strip("/")) is None and not ns.force:
            raise ApiError(f"unknown endpoint /api/{ns.path}\n  {suggest(ns.path)}")
        segs = "/".join(str(a) for a in ns.args)
        print(f"DRY RUN  POST {base_url()}/api/{ns.path.strip('/')}" + (f"/{segs}" if segs else ""))
        print("body:", json.dumps(body if body is not None else {}, ensure_ascii=False))
        if needs_apply:
            print(f"then commit: POST /api/{apply_to}")
        return 0

    payload = request("POST", ns.path, ns.args, body=body, timeout=ns.timeout,
                      check_index=not ns.force)
    emit(payload, ns.raw)
    if failed(payload):
        print("\nrefused: the change was NOT saved. Fix the fields above and retry.",
              file=sys.stderr)
        return 1
    if needs_apply:
        print(f"\nsaved to config.xml only — NOT live yet. Commit with:"
              f"\n  opnsense.py post {apply_to}", file=sys.stderr)
    return 0


def cmd_probe(ns):
    out = {"url": base_url()}
    fw = request("GET", "core/firmware/status", [], timeout=ns.timeout)
    out["product"] = fw.get("product_version") or fw.get("product_id")
    out["status"] = fw.get("status")
    ifaces = request("GET", "interfaces/overview/interfaces_info", [], timeout=ns.timeout)
    rows = ifaces.get("rows", ifaces if isinstance(ifaces, list) else [])
    out["interfaces"] = [
        {"device": r.get("device"), "identifier": r.get("identifier"),
         "status": r.get("status"), "addresses": r.get("addr4") or r.get("ipv4")}
        for r in rows
    ] if isinstance(rows, list) else rows
    out["endpoints_indexed"] = load_index()["count"]
    emit(out)
    return 0


def cmd_backup(ns):
    payload = request("GET", "core/backup/download", ["this"], timeout=ns.timeout)
    text = payload.get("_raw") if isinstance(payload, dict) else None
    if text is None:
        text = json.dumps(payload, ensure_ascii=False)
    if not text.lstrip().startswith("<?xml"):
        raise ApiError("did not receive a config.xml — got: " + text[:300])
    with open(ns.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"saved {ns.out}  ({len(text)} bytes)")
    return 0


# --------------------------------------------------------------------------- cli


def build_parser():
    p = argparse.ArgumentParser(prog="opnsense.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--env", help="path to a .env file with credentials")
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--raw", action="store_true", help="print non-JSON responses verbatim")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("find", help="search the bundled endpoint index")
    f.add_argument("terms", nargs="+")
    f.add_argument("--module")
    f.add_argument("--limit", type=int, default=40)
    f.add_argument("--json", action="store_true")
    f.set_defaults(func=cmd_find)

    s = sub.add_parser("show", help="list all commands of one controller")
    s.add_argument("controller")
    s.set_defaults(func=cmd_show)

    g = sub.add_parser("get", help="GET an endpoint")
    g.add_argument("path")
    g.add_argument("args", nargs="*")
    g.add_argument("--force", action="store_true", help="skip index validation")
    g.set_defaults(func=cmd_get)

    o = sub.add_parser("post", help="POST an endpoint")
    o.add_argument("path")
    o.add_argument("args", nargs="*")
    o.add_argument("--data", help="JSON string, or @file.json")
    o.add_argument("--dry-run", action="store_true")
    o.add_argument("--force", action="store_true", help="skip index validation")
    o.set_defaults(func=cmd_post)

    b = sub.add_parser("backup", help="download the running config.xml")
    b.add_argument("--out", default="config-backup.xml")
    b.set_defaults(func=cmd_backup)

    pr = sub.add_parser("probe", help="check connectivity, auth and version")
    pr.set_defaults(func=cmd_probe)
    return p


def main(argv=None):
    ns = build_parser().parse_args(argv)
    if ns.cmd not in ("find", "show"):
        load_dotenv(ns.env)
    try:
        return ns.func(ns)
    except ApiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
