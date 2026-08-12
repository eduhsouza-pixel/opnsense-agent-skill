# AGENTS.md — OPNsense administration

Instructions for any coding agent that manages an OPNsense firewall.
`AGENTS.md` is read automatically by Codex CLI, Gemini CLI, OpenCode, Cursor,
Zed, Aider, Jules and others. Claude Code users get the same content through
`skills/opnsense/SKILL.md`.

## Setup

```
OPNSENSE_URL=https://192.168.1.1
OPNSENSE_KEY=<api key>
OPNSENSE_SECRET=<api secret>
OPNSENSE_INSECURE=1
```

The REST API accepts **only** an API key/secret pair over HTTP Basic auth — a
GUI username and password returns 401. Create one at *System > Access > Users >
API keys*; the secret is shown once and is never stored on the firewall.

Verify before doing anything else:

```bash
python skills/opnsense/scripts/opnsense.py probe
```

## Never guess an endpoint name

The API has 2399 endpoints across 93 modules, and the names are not what you
would predict:

- Port forwards live at `firewall/d_nat`. `firewall/dnat` returns 404.
- The published reference lists `add_rule`; the GUI calls `addRule`. Both work.
- Static routes use `addroute` — lowercase, no separator.
- `firewall/filter/apply` works but is **absent from the official reference**,
  because the reference is generated per PHP class and this action is inherited.

Guessing produces a 404 that reads like "the feature doesn't exist" when it
does. Look it up instead:

```bash
python skills/opnsense/scripts/opnsense.py find port forward
python skills/opnsense/scripts/opnsense.py show firewall/d_nat
```

`find` understands networking vocabulary, not just literal endpoint names —
"port forward", "blocklist", "bufferbloat" and "api key" all resolve to the
controllers that implement them. `show` lists every command on a controller and
names the endpoint that commits changes for it.

## Every change is two steps

1. **Write** — `add_*` / `set_*` / `del_*` / `toggle_*`. Returns
   `{"result": "saved", "uuid": "..."}`. This edits `/conf/config.xml` only.
2. **Commit** — POST the controller's `apply` or `reconfigure` endpoint.

```bash
python skills/opnsense/scripts/opnsense.py post firewall/filter/add_rule --data @rule.json
python skills/opnsense/scripts/opnsense.py post firewall/filter/apply
```

`{"result": "failed", "validations": {...}}` means **nothing was written** — the
keys name the fields to fix. HTTP 200 with that body is still a failure.

Skipping the commit leaves a landmine: the change sits in `config.xml` and is
applied silently the next time anyone touches that module or the box reboots.

Use `--dry-run` to preview the request and its commit step without sending.

## Before changing a firewall you cannot physically reach

There is **no automatic rollback**. No savepoint endpoint exists in the core
API, despite what some third-party OPNsense tooling claims. A rule that locks
you out stays locked in.

1. Back up: `python skills/opnsense/scripts/opnsense.py backup --out pre-change.xml`
2. Arm a dead-man switch over SSH before touching filter rules:
   `echo "pfctl -d" | at now + 5 minutes` (cancel with `atq` / `atrm` once you
   have confirmed access still works).
3. Snapshot the VM, or use `core/snapshots` on ZFS.
4. Add the permissive rule and commit **before** removing the old one.

## Working style

- Read before you write. Show the user the current state before proposing a change.
- One change, one commit, one verification.
- Confirm anything touching reachability: filter rules on the management
  interface, interface addressing, gateways, routes, DNS for the whole network,
  firmware upgrades, reboots. Read-only queries need no confirmation.
- Correlate pf with the API by UUID — the rule `label` in `pfctl -sr` is the API
  UUID, and it is the only reliable join between the two views.
- Prefer the API over SSH. Drop to the shell only for what has no endpoint
  (`pfctl`, `tcpdump`, template debugging), and say why.

## Reference material

Seventeen documents in `skills/opnsense/references/` cover firewall rules, NAT,
aliases, interfaces and routing, DNS and DNSBL, DHCP, VPN, traffic shaping,
IDS/IPS, users and API keys, configd, backup and recovery, firmware, diagnostics
and HA/CARP.

Read `skills/opnsense/references/pitfalls.md` before any non-trivial change, and
`api-conventions.md` before writing an unfamiliar payload.

## MCP

`skills/opnsense/scripts/mcp_server.py` exposes the same capability as MCP tools
for clients that prefer them. See `docs/integrations.md`.
