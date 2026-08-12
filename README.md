# opnsense-agent-skill

Agentic administration of **OPNsense** firewalls — REST API, `configd` and
shell — for Claude Code, Cursor, GitHub Copilot, Windsurf, Cline, Zed, Codex
CLI, Gemini CLI, OpenCode and any MCP client.

Ships an offline index of **2399 API endpoints across 93 modules and 343
controllers**, scraped from the official reference and repaired where that
reference is wrong, so the agent looks endpoints up instead of guessing them.

Python 3.8+, standard library only. No pip install, no SDK.

---

## Why an index

The OPNsense API is large and its names are not guessable:

| You would write | It actually is |
| --- | --- |
| `firewall/dnat` | `firewall/d_nat` |
| `interfaces/vlan` | `interfaces/vlan_settings` |
| `routes/routes/add_route` | `routes/routes/addroute` |
| `addRule` | `add_rule` in the docs, `addRule` in the GUI — both work |

And the published reference is **generated per PHP class**, so actions inherited
from a base class are missing from it entirely — including
`firewall/filter/apply`, the call that makes any rule change take effect. Its
HTTP method column is also, by its own admission, only the "most likely" verb:
`wireguard/client/add_client` is published as `GET`.

Guessing produces a 404 that reads like "this feature doesn't exist". The index
turns that into a suggestion:

```
$ opnsense.py get firewall/dnat/searchRule
error: unknown endpoint /api/firewall/dnat/searchRule
  controllers in module firewall: firewall/alias, firewall/alias_util,
  firewall/category, firewall/d_nat, firewall/filter, firewall/filter_base, ...
```

Search understands networking vocabulary too, not just literal endpoint names:

```
$ opnsense.py find port forward
matched by concept — controllers that implement 'port forward':

POST      /api/firewall/d_nat/add_rule  (camel: addRule)
POST      /api/firewall/d_nat/apply
...
```

---

## Install

Pick whichever your tool speaks. Both can run at once.

### Instruction files

`AGENTS.md` at the repo root is read automatically by **Codex CLI, Gemini CLI,
OpenCode, Cursor, Zed and Aider**. Nothing to configure.

```bash
git clone https://github.com/eduhsouza-pixel/opnsense-agent-skill
cd opnsense-agent-skill

cp -r skills/opnsense ~/.claude/skills/                       # Claude Code
cp -r skills/opnsense ~/.config/opencode/skills/              # OpenCode
mkdir -p .cursor/rules && cp integrations/cursor/opnsense.mdc .cursor/rules/
mkdir -p .github && cp integrations/copilot/copilot-instructions.md .github/
```

Claude Code can also install it as a plugin:

```
/plugin marketplace add eduhsouza-pixel/opnsense-agent-skill
/plugin install opnsense-agent-skill
```

### MCP server

Six typed tools for any MCP client — Claude Code and Desktop, Cursor, Windsurf,
VS Code, Cline, Zed, Codex CLI, Gemini CLI, OpenCode.

```bash
python skills/opnsense/scripts/mcp_server.py --selftest    # 10 checks, no firewall needed
```

```bash
claude mcp add opnsense -- python /abs/path/skills/opnsense/scripts/mcp_server.py
```

Per-client configuration blocks are in
**[docs/integrations.md](docs/integrations.md)**.

---

## Configure

Create an API key at *System > Access > Users > API keys* — the REST API rejects
GUI passwords with 401 — then set:

```bash
OPNSENSE_URL=https://192.168.1.1
OPNSENSE_KEY=<key>
OPNSENSE_SECRET=<secret>
OPNSENSE_INSECURE=1     # default self-signed certificate
```

Environment variables or a `.env` file both work. See
[`.env.example`](.env.example).

```bash
python skills/opnsense/scripts/opnsense.py probe
```

---

## Usage

```bash
opnsense.py probe                        # connectivity, auth, version
opnsense.py find port forward            # search by keyword or concept
opnsense.py show firewall/d_nat          # every command + how to commit
opnsense.py get  firewall/filter/search_rule
opnsense.py post firewall/filter/add_rule --data @rule.json
opnsense.py post firewall/filter/apply
opnsense.py backup --out pre-change.xml
```

Full reference, exit codes and naming rules:
**[docs/cli.md](docs/cli.md)**.

### It knows changes are two-phase

Every write edits `config.xml` and is **not live** until committed. After a
successful write the client names the commit endpoint:

```
saved to config.xml only — NOT live yet. Commit with:
  opnsense.py post firewall/filter/apply
```

The commit target is derived from the index per controller rather than a
hardcoded table, so it is correct for plugins the author never touched —
`nginx/settings` resolves to `nginx/service/reconfigure` with nothing
hardcoded. A 200 response carrying `{"result": "failed", "validations": {...}}`
is treated as the failure it is, and exits non-zero.

---

## What it covers

Firewall rules · aliases · NAT and port forwarding · interfaces, VLANs and VIPs ·
gateways and static routes · Unbound, DNSBL and Dnsmasq · DHCP (Kea, Dnsmasq,
ISC) · WireGuard, IPsec and OpenVPN · traffic shaping · Suricata IDS/IPS ·
captive portal · users, privileges and API keys · firmware and plugins ·
HA/CARP · backups and recovery · diagnostics and logs.

Seventeen reference documents in
[`skills/opnsense/references/`](skills/opnsense/references) carry the detail.
[`pitfalls.md`](skills/opnsense/references/pitfalls.md) is the one to read first
— traps verified against a running OPNsense 26.7 box:

- There is **no savepoint or automatic rollback** in the core API, contrary to
  what some third-party OPNsense tooling documents. A rule that locks you out
  stays locked in.
- `apply` runs `filter reload skip_alias`, so deleting an alias leaves an
  orphaned pf table that only `pfctl -t <name> -T kill` removes.
- The pf rule `label` is the API UUID — the only reliable join between the API
  view and live packet counters.
- `pfctl -sr` prints service names, not port numbers: 853 shows as `domain-s`.

---

## Safety

Lockout is the characteristic failure of this work, and OPNsense has no
automatic rollback. The skill backs up before changing, recommends arming
`echo "pfctl -d" | at now + 5 minutes` before touching filter rules on a remote
box, and asks for confirmation before anything affecting reachability —
management-interface rules, addressing, gateways, routes, network-wide DNS,
firmware, reboots. Read-only queries proceed without ceremony.

For the MCP server, `OPNSENSE_MCP_READONLY=1` refuses every write centrally
while leaving the index and all reads working.

---

## Repository layout

```
AGENTS.md                cross-tool instructions (Codex, Gemini, OpenCode, Cursor, Zed, Aider)
GEMINI.md                Gemini CLI entry point
.claude-plugin/          Claude Code plugin manifest
skills/opnsense/
  SKILL.md               Claude Code skill
  references/            17 domain documents
  scripts/opnsense.py    CLI client
  scripts/mcp_server.py  MCP server (stdio, JSON-RPC 2.0)
  scripts/data/          endpoints.json — the 2399-endpoint index
integrations/            copyable rule files for Cursor, Copilot, Windsurf, Cline
docs/integrations.md     per-tool setup, including every MCP config block
docs/cli.md              full CLI and MCP reference
```

---

## Sources

Built from the official OPNsense documentation and API reference
(`docs.opnsense.org`), the FreeBSD `pf` and `pfctl` manuals, the OPNsense forum
and issue tracker, and verification against a live OPNsense 26.7 / FreeBSD 15.1
instance. Research was assembled with NotebookLM across 100 imported sources;
every endpoint claim was then cross-checked against the scraped reference,
because the synthesis got several exact endpoint names wrong and described a
savepoint mechanism that does not exist.

Endpoint data reflects the reference as published for the 26.x series.
[docs/cli.md](docs/cli.md#regenerating-the-index) explains how to rebuild it for
another release.

## License

MIT — see [LICENSE](LICENSE).

Not affiliated with or endorsed by Deciso B.V. OPNsense is a registered
trademark of Deciso B.V.
