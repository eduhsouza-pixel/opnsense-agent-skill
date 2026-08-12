---
name: opnsense
description: Administer an OPNsense firewall through its REST API, configd and shell. Use for firewall rules, aliases, NAT and port forwarding, interfaces and VLANs, gateways and routing, Unbound/Dnsmasq DNS and DNSBL blocklists, DHCP (Kea/Dnsmasq/ISC), IPsec/OpenVPN/WireGuard VPNs, traffic shaping, Suricata IDS/IPS, captive portal, users and API keys, firmware upgrades, HA/CARP, backups and rollback, plus diagnostics, logs and connectivity troubleshooting. Triggers on OPNsense, opnsense.local, pfctl, configctl, config.xml, /api/firewall, or any request to inspect or change a firewall running OPNsense.
---

# OPNsense administration

Drive an OPNsense firewall the way a careful network engineer would: read state
first, change one thing at a time, commit deliberately, and never lose your way
back in.

## Setup

Credentials come from the environment or a `.env` file in the working directory:

```
OPNSENSE_URL=https://192.168.1.1
OPNSENSE_KEY=<api key>
OPNSENSE_SECRET=<api secret>
OPNSENSE_INSECURE=1
```

`OPNSENSE_INSECURE=1` is needed for the default self-signed certificate.

The REST API **only** accepts an API key/secret pair over HTTP Basic auth. A GUI
username and password returns 401. Keys are created at *System > Access > Users >
API keys*; the secret is shown once and never stored on the firewall.

Confirm the connection before doing anything else:

```bash
python scripts/opnsense.py probe
```

## The one rule that matters most

**Never guess an endpoint name.** The API has 2399 endpoints across 93 modules
and the names are not what you would predict — port forwards live at
`firewall/d_nat`, not `firewall/dnat`; the reference publishes `add_rule` while
the GUI calls `addRule`. Guessing produces a 404 that reads like "the feature
doesn't exist" when it does.

Search the bundled index instead:

```bash
python scripts/opnsense.py find port forward     # search by keyword
python scripts/opnsense.py show firewall/d_nat   # every command on a controller
```

`show` also prints the endpoint that commits changes for that controller.
The client validates every request against the index, so a typo fails with a
suggestion instead of a bare 404.

## Change lifecycle

Every mutation is two steps. Writing succeeds and changes nothing visible until
you commit.

1. **Read** — `search_*` to list, `get_*` to fetch one item by UUID.
2. **Write** — `add_*` / `set_*` / `del_*` / `toggle_*`. Returns
   `{"result": "saved", "uuid": "..."}`. This edits `/conf/config.xml` only.
3. **Commit** — `POST` the controller's `apply` or `reconfigure` endpoint. Now
   it is live.

`{"result": "failed", "validations": {...}}` means nothing was written; the
field names in `validations` tell you exactly what to fix. The client exits
non-zero on this, and reminds you when a write still needs its commit step.

Skipping the commit leaves a landmine: the change sits in `config.xml` and gets
applied silently the next time anyone touches that module or the box reboots.

```bash
python scripts/opnsense.py post firewall/filter/add_rule --data @rule.json
python scripts/opnsense.py post firewall/filter/apply
```

Use `--dry-run` to see the exact request and its commit step without sending.

## Before you change a firewall you cannot physically reach

Locking yourself out is the characteristic failure of this work, and OPNsense
has **no automatic rollback** — there is no savepoint endpoint in the core API,
despite what some third-party tooling claims.

Take these precautions, in order of value:

1. **Back up first.** `python scripts/opnsense.py backup --out pre-change.xml`
2. **Arm a dead-man switch** over SSH before touching filter rules:
   `echo "pfctl -d" | at now + 5 minutes` — if you lose access, the firewall
   disables itself in five minutes and you can reconnect. Cancel with `atrm`
   once you have confirmed access still works.
3. **Snapshot the VM or ZFS dataset** if the box is virtual.
4. **Never let the last rule on the management interface be the one you edit.**
   Add the permissive rule first, commit, verify, then remove the old one.

Rollback paths, in escalating order of disruption, are in
[references/backup-recovery.md](references/backup-recovery.md).

## Working style

- **Read before you write.** `search_*` the current state and show the user what
  exists before proposing a change.
- **One change, one commit, one verification.** Batch only changes that belong to
  the same logical edit.
- **Confirm anything that touches reachability** — filter rules on the management
  interface, interface addressing, gateway or route changes, DNS for the whole
  network, firmware upgrades, reboots. Read-only queries need no confirmation.
- **Correlate pf with the API by UUID.** The rule `label` in `pfctl -sr` is the
  API UUID. That is the only reliable join between the two views.
- **Prefer the API over the shell.** Drop to SSH only for what has no endpoint
  (`pfctl`, `tcpdump`, template debugging), and say why.

## Reference material

Load only what the task needs.

| File | Covers |
| --- | --- |
| [api-conventions.md](references/api-conventions.md) | Naming rules, auth, search/get/add/set payload shapes, discovering undocumented endpoints |
| [firewall-rules.md](references/firewall-rules.md) | Filter rules, rule fields, ordering, categories, groups, logging |
| [nat.md](references/nat.md) | Port forwards (`d_nat`), outbound NAT (`source_nat`), 1:1, NPT |
| [aliases.md](references/aliases.md) | Alias types, GeoIP, URL tables, orphaned pf tables |
| [interfaces-routing.md](references/interfaces-routing.md) | Assignments, VLANs, VIPs, gateways, static routes |
| [dns.md](references/dns.md) | Unbound, DNSBL blocklists, Dnsmasq, host overrides, DoT |
| [dhcp.md](references/dhcp.md) | Kea, Dnsmasq and ISC DHCP, leases, static mappings |
| [vpn.md](references/vpn.md) | WireGuard, IPsec, OpenVPN instances and status |
| [traffic-shaper.md](references/traffic-shaper.md) | Pipes, queues, rules, per-host vs aggregate limits |
| [ids-ips.md](references/ids-ips.md) | Suricata settings, rulesets, alerts, IPS mode |
| [users-access.md](references/users-access.md) | Users, groups, privileges, API keys, least privilege |
| [configd.md](references/configd.md) | The backend daemon, `configctl`, actions, templates, `pluginctl` |
| [backup-recovery.md](references/backup-recovery.md) | Backups, restore, console recovery, firmware revert, lockout |
| [firmware.md](references/firmware.md) | Updates, plugins, patches, reverting |
| [diagnostics.md](references/diagnostics.md) | Interfaces, ARP/NDP, states, logs, captures, resource usage |
| [ha-carp.md](references/ha-carp.md) | CARP VIPs, pfsync, XMLRPC sync, failover |
| [pitfalls.md](references/pitfalls.md) | Verified traps that cost real debugging time |

Read [pitfalls.md](references/pitfalls.md) before any non-trivial change.

## Other tools

The same capability is available outside Claude Code: `AGENTS.md` at the repo
root covers Codex CLI, Gemini CLI, OpenCode, Cursor, Zed and Aider, and
`scripts/mcp_server.py` exposes six MCP tools for any MCP client. See
`docs/integrations.md`.
