#!/usr/bin/env python3
"""MCP server exposing the OPNsense API as tools. Standard library only.

Speaks JSON-RPC 2.0 over stdio, so any MCP client can use it without installing
an SDK. Wraps opnsense.py, which lives beside this file.

Credentials come from the environment (see .env.example). Set
OPNSENSE_MCP_READONLY=1 to refuse every mutating call — the endpoint index and
all GET tools keep working.

Run directly to self-test:  python mcp_server.py --selftest
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import opnsense as opn  # noqa: E402

PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOLS = {"2024-11-05", "2025-03-26", "2025-06-18"}
SERVER_INFO = {"name": "opnsense", "version": "1.1.0"}


def readonly() -> bool:
    return os.environ.get("OPNSENSE_MCP_READONLY", "").lower() in ("1", "true", "yes")


# --------------------------------------------------------------------------- tools

TOOLS = [
    {
        "name": "opnsense_find_endpoint",
        "description": (
            "Search the offline index of 2399 OPNsense API endpoints by keyword. "
            "ALWAYS use this before calling opnsense_get or opnsense_post — endpoint "
            "names are not guessable (port forwards live at firewall/d_nat, not "
            "firewall/dnat). Works without credentials."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords, e.g. 'port forward' or 'dhcp lease'"},
                "module": {"type": "string", "description": "Restrict to one module, e.g. 'firewall'"},
                "limit": {"type": "integer", "default": 40},
            },
            "required": ["query"],
        },
    },
    {
        "name": "opnsense_describe_controller",
        "description": (
            "List every command on one controller (e.g. 'firewall/filter') plus the "
            "endpoint that commits changes for it. Works without credentials."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "controller": {"type": "string", "description": "module/controller, e.g. 'firewall/d_nat'"},
            },
            "required": ["controller"],
        },
    },
    {
        "name": "opnsense_get",
        "description": (
            "GET an OPNsense API endpoint — read-only. Path is module/controller/command, "
            "e.g. 'firewall/filter/search_rule'. Extra URL segments go in args."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "args": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["path"],
        },
    },
    {
        "name": "opnsense_post",
        "description": (
            "POST an OPNsense API endpoint. MUTATES the firewall. A write only edits "
            "config.xml — it is not live until you POST the controller's apply or "
            "reconfigure endpoint, which this tool names in its response. Use dry_run "
            "first to preview. Back up before changing filter rules on a remote box."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "args": {"type": "array", "items": {"type": "string"}},
                "body": {"type": "object", "description": "JSON body, usually {'rule': {...}}"},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["path"],
        },
    },
    {
        "name": "opnsense_backup_config",
        "description": "Download the running config.xml. Do this before any risky change.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "out_path": {"type": "string", "default": "config-backup.xml"},
            },
        },
    },
    {
        "name": "opnsense_probe",
        "description": "Check connectivity, authentication, firmware version and interfaces.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def tool_find(a):
    query = str(a.get("query", ""))
    limit = int(a.get("limit") or 40)
    hits, mode = opn.search_endpoints(query, a.get("module"))
    if not hits:
        return f"No endpoint matches {query!r}."

    note = {"exact": "",
            "concept": " (matched by concept — these controllers implement it)",
            "partial": " (partial — no endpoint matched every term)"}[mode]
    lines = [f"{len(hits)} match(es){note}"]
    for r in hits[:limit]:
        extra = f"  camel: {r['camel']}" if r["camel"] else ""
        params = f"  params: {r['p']}" if r["p"] else ""
        lines.append(f"{r['m']:9} /api/{r['mod']}/{r['ctl']}/{r['cmd']}{params}{extra}")
    if len(hits) > limit:
        lines.append(f"... {len(hits) - limit} more")
    return "\n".join(lines)


def tool_describe(a):
    spec = str(a.get("controller", "")).strip("/").split("/")
    if len(spec) != 2:
        return "Give module/controller, e.g. 'firewall/filter'."
    mod, ctl = spec
    rows = [r for r in opn.load_index()["endpoints"] if r["mod"] == mod and r["ctl"] == ctl]
    if not rows:
        return opn.suggest(mod)
    lines = [f"/api/{mod}/{ctl}/ — {len(rows)} commands"]
    for r in rows:
        extra = f"  camel: {r['camel']}" if r["camel"] else ""
        params = f"  params: {r['p']}" if r["p"] else ""
        note = "  [inherited, missing from the published reference]" if r.get("inherited") else ""
        lines.append(f"  {r['m']:9} {r['cmd']}{params}{extra}{note}")
    target = opn.resolve_apply(mod, ctl)
    if target:
        lines.append(f"\nCommit changes with: POST /api/{target}")
    return "\n".join(lines)


def tool_get(a):
    payload = opn.request("GET", str(a["path"]), a.get("args") or [])
    return json.dumps(payload, indent=2, ensure_ascii=False)


def tool_post(a):
    path = str(a["path"])
    parts = path.strip("/").split("/")
    mod, ctl = (parts + ["", ""])[:2]
    cmd = parts[2] if len(parts) > 2 else ""
    target = opn.resolve_apply(mod, ctl) if mod and ctl else None
    needs_commit = target and cmd not in opn.COMMIT_COMMANDS

    if a.get("dry_run"):
        out = [f"DRY RUN  POST /api/{path}" + ("/" + "/".join(map(str, a.get("args") or []))
                                               if a.get("args") else ""),
               "body: " + json.dumps(a.get("body") or {}, ensure_ascii=False)]
        if needs_commit:
            out.append(f"then commit: POST /api/{target}")
        return "\n".join(out)

    if readonly():
        raise opn.ApiError(
            "refused: this server runs with OPNSENSE_MCP_READONLY=1, so writes are "
            "disabled. Unset it to allow changes."
        )

    payload = opn.request("POST", path, a.get("args") or [], body=a.get("body"))
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if opn.failed(payload):
        raise opn.ApiError("the firewall refused the change; nothing was saved:\n" + text)
    if needs_commit:
        text += (f"\n\nSaved to config.xml only — NOT live yet. Commit with:\n"
                 f"  opnsense_post(path=\"{target}\")")
    return text


def tool_backup(a):
    out = str(a.get("out_path") or "config-backup.xml")
    payload = opn.request("GET", "core/backup/download", ["this"])
    text = payload.get("_raw") if isinstance(payload, dict) else None
    if text is None or not str(text).lstrip().startswith("<?xml"):
        raise opn.ApiError("did not receive a config.xml from the firewall")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    return f"Saved {out} ({len(text)} bytes)"


def tool_probe(a):
    fw = opn.request("GET", "core/firmware/status", [])
    info = {
        "url": opn.base_url(),
        "product": fw.get("product_version") or fw.get("product_id"),
        "status": fw.get("status"),
        "endpoints_indexed": opn.load_index()["count"],
        "readonly_mode": readonly(),
    }
    return json.dumps(info, indent=2, ensure_ascii=False)


HANDLERS = {
    "opnsense_find_endpoint": tool_find,
    "opnsense_describe_controller": tool_describe,
    "opnsense_get": tool_get,
    "opnsense_post": tool_post,
    "opnsense_backup_config": tool_backup,
    "opnsense_probe": tool_probe,
}


# --------------------------------------------------------------------------- jsonrpc


def result(rid, payload):
    return {"jsonrpc": "2.0", "id": rid, "result": payload}


def error(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def handle(msg):
    """Return a response dict, or None for notifications."""
    method, rid = msg.get("method"), msg.get("id")

    if method == "initialize":
        asked = (msg.get("params") or {}).get("protocolVersion")
        return result(rid, {
            "protocolVersion": asked if asked in SUPPORTED_PROTOCOLS else PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        })

    if method in ("notifications/initialized", "initialized", "notifications/cancelled"):
        return None

    if method == "ping":
        return result(rid, {})

    if method == "tools/list":
        return result(rid, {"tools": TOOLS})

    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        fn = HANDLERS.get(name)
        if fn is None:
            return error(rid, -32602, f"unknown tool: {name}")
        try:
            text = fn(params.get("arguments") or {})
            return result(rid, {"content": [{"type": "text", "text": text}],
                                "isError": False})
        except opn.ApiError as exc:
            # Tool-level failures go back as results so the model can react,
            # rather than as protocol errors the client may swallow.
            return result(rid, {"content": [{"type": "text", "text": f"error: {exc}"}],
                                "isError": True})
        except Exception as exc:  # noqa: BLE001
            return result(rid, {"content": [{"type": "text",
                                             "text": f"unexpected error: {exc!r}"}],
                                "isError": True})

    if rid is None:
        return None
    return error(rid, -32601, f"method not found: {method}")


def serve(stdin=None, stdout=None):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps(error(None, -32700, "parse error")) + "\n")
            stdout.flush()
            continue
        response = handle(msg)
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()


def selftest():
    """Exercise the protocol and the offline tools without a firewall."""
    checks = []

    r = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"}})
    checks.append(("initialize echoes the client's protocol",
                   r["result"]["protocolVersion"] == "2024-11-05"))

    checks.append(("initialized notification returns nothing",
                   handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None))

    r = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in r["result"]["tools"]]
    checks.append(("tools/list returns 6 tools", len(names) == 6))
    checks.append(("every tool has a handler", all(n in HANDLERS for n in names)))

    r = handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "opnsense_find_endpoint",
                           "arguments": {"query": "port forward"}}})
    checks.append(("find locates d_nat", "d_nat" in r["result"]["content"][0]["text"]))

    r = handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {"name": "opnsense_describe_controller",
                           "arguments": {"controller": "firewall/d_nat"}}})
    text = r["result"]["content"][0]["text"]
    checks.append(("describe names the commit endpoint",
                   "firewall/filter/apply" in text))

    r = handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                "params": {"name": "opnsense_post",
                           "arguments": {"path": "firewall/filter/add_rule",
                                         "body": {"rule": {}}, "dry_run": True}}})
    checks.append(("dry run names the commit step",
                   "firewall/filter/apply" in r["result"]["content"][0]["text"]))

    os.environ["OPNSENSE_MCP_READONLY"] = "1"
    r = handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                "params": {"name": "opnsense_post",
                           "arguments": {"path": "firewall/filter/apply"}}})
    checks.append(("readonly mode blocks writes", r["result"]["isError"] is True))
    del os.environ["OPNSENSE_MCP_READONLY"]

    r = handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                "params": {"name": "nope", "arguments": {}}})
    checks.append(("unknown tool is a protocol error", "error" in r))

    r = handle({"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                "params": {"name": "opnsense_get",
                           "arguments": {"path": "firewall/dnat/search_rule"}}})
    checks.append(("bad endpoint returns a suggestion, not a crash",
                   r["result"]["isError"] and "d_nat" in r["result"]["content"][0]["text"]))

    bad = [n for n, ok in checks if not ok]
    for name, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + name)
    print("\n%d/%d passed" % (len(checks) - len(bad), len(checks)))
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    serve()
