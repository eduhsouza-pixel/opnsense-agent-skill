# opnsense-agent-skill

A [Claude Code](https://claude.com/claude-code) skill for administering
**OPNsense** firewalls through the REST API, `configd` and the shell.

It ships with an offline index of **2399 API endpoints across 93 modules and 343
controllers**, scraped from the official reference and patched with actions the
reference omits — so the agent looks endpoints up instead of guessing them.

## Why an index

The OPNsense API is large and its names are not guessable. Port forwards live at
`firewall/d_nat`, not `firewall/dnat`. The published reference lists `add_rule`
while the GUI calls `addRule`. Static routes use `addroute`, with no separator at
all. And because the reference is generated per PHP class, actions inherited
from a base class — including `firewall/filter/apply`, the call that makes any
rule change take effect — are missing from it entirely.

Guessing produces a 404 that reads like "this feature doesn't exist". The index
turns that into a suggestion:

```
$ opnsense.py get firewall/dnat/searchRule
error: unknown endpoint /api/firewall/dnat/searchRule
  controllers in module firewall: firewall/alias, firewall/alias_util,
  firewall/category, firewall/d_nat, firewall/filter, firewall/filter_base, ...
```

## Install

**As a plugin:**

```
/plugin marketplace add eduhsouza-pixel/opnsense-agent-skill
/plugin install opnsense-agent-skill
```

**Or copy the skill directly:**

```bash
git clone https://github.com/eduhsouza-pixel/opnsense-agent-skill
cp -r opnsense-agent-skill/skills/opnsense ~/.claude/skills/
```

## Configure

Create an API key at *System > Access > Users > API keys* — the REST API rejects
GUI passwords with 401 — then set:

```bash
OPNSENSE_URL=https://192.168.1.1
OPNSENSE_KEY=<key>
OPNSENSE_SECRET=<secret>
OPNSENSE_INSECURE=1     # default self-signed certificate
```

Environment variables or a `.env` file both work. See `.env.example`.

```bash
python skills/opnsense/scripts/opnsense.py probe
```

## The client

Standard library only, no dependencies.

```bash
opnsense.py probe                        # connectivity, auth, version
opnsense.py find port forward            # search the endpoint index
opnsense.py show firewall/d_nat          # every command + how to commit
opnsense.py get  firewall/filter/search_rule
opnsense.py post firewall/filter/add_rule --data @rule.json
opnsense.py post firewall/filter/apply
opnsense.py backup --out pre-change.xml
```

It knows the two-phase change model. Every write goes to `config.xml` and is not
live until you commit, so after a successful write it tells you what to call:

```
saved to config.xml only — NOT live yet. Commit with:
  opnsense.py post firewall/filter/apply
```

The commit target is derived from the index per controller, so it is right for
plugins the author never touched — `nginx/settings` resolves to
`nginx/service/reconfigure` with nothing hardcoded.

A 200 response carrying `{"result": "failed", "validations": {...}}` is treated
as the failure it is, and exits non-zero.

## What it covers

Firewall rules · aliases · NAT and port forwarding · interfaces, VLANs and VIPs ·
gateways and static routes · Unbound, DNSBL and Dnsmasq · DHCP (Kea, Dnsmasq,
ISC) · WireGuard, IPsec and OpenVPN · traffic shaping · Suricata IDS/IPS ·
captive portal · users, privileges and API keys · firmware and plugins ·
HA/CARP · backups and recovery · diagnostics and logs.

Seventeen reference documents in `skills/opnsense/references/` carry the detail.
[`pitfalls.md`](skills/opnsense/references/pitfalls.md) is the one to read first
— it collects traps verified against a running 26.7 box, such as:

- There is **no savepoint or automatic rollback** in the core API, contrary to
  what some third-party OPNsense tooling documents. A rule that locks you out
  stays locked in.
- `apply` runs `filter reload skip_alias`, so deleting an alias leaves an
  orphaned pf table that only `pfctl -t <name> -T kill` removes.
- The pf rule `label` is the API UUID — the only reliable join between the API
  view and live packet counters.

## Safety

The skill treats lockout as the characteristic failure of this work. It backs up
before changing, recommends arming `echo "pfctl -d" | at now + 5 minutes` before
touching filter rules on a remote box, and asks for confirmation before anything
affecting reachability. Read-only queries proceed without ceremony.

## Sources

Built from the official OPNsense documentation and API reference
(`docs.opnsense.org`), the FreeBSD `pf` and `pfctl` manuals, the OPNsense forum
and issue tracker, and verification against a live OPNsense 26.7 / FreeBSD 15.1
instance. Research was assembled with NotebookLM across 100 imported sources;
every endpoint claim was then cross-checked against the scraped reference,
because the synthesis got several exact endpoint names wrong.

Endpoint data reflects the reference as published for the 26.x series. Regenerate
it against your own version if you run something older.

## License

MIT — see [LICENSE](LICENSE).

Not affiliated with or endorsed by Deciso B.V. OPNsense is a registered
trademark of Deciso B.V.
