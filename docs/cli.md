# CLI reference

`skills/opnsense/scripts/opnsense.py` — Python 3.8+, standard library only.

```
usage: opnsense.py [-h] [--env ENV] [--timeout TIMEOUT] [--raw]
                   {find,show,get,post,backup,probe} ...
```

| Global option | Meaning |
| --- | --- |
| `--env PATH` | Read credentials from this `.env` instead of searching |
| `--timeout N` | Request timeout in seconds (default 60) |
| `--raw` | Print non-JSON responses verbatim instead of wrapping them |

## Credentials

Read from the environment, or from a `.env` in the working directory or beside
the script. Real environment variables win over the file.

| Variable | Required | Notes |
| --- | --- | --- |
| `OPNSENSE_URL` | yes | `https://192.168.1.1`. `OPNSENSE_HOST` also accepted; scheme defaults to `https://` |
| `OPNSENSE_KEY` | yes | API key — used as the Basic-auth username |
| `OPNSENSE_SECRET` | yes | API secret — used as the Basic-auth password |
| `OPNSENSE_INSECURE` | no | `1` skips certificate verification, needed for the default self-signed cert |

The REST API rejects GUI usernames and passwords with 401. Create a key pair at
*System > Access > Users > API keys*, or
`POST /api/auth/user/addApiKey/<username>` if you already have one. The secret
is displayed once and is not stored on the firewall.

`find` and `show` read the bundled index and work with no credentials at all.

---

## probe

```bash
opnsense.py probe
```

Confirms the URL resolves, the credentials authenticate, and reports the
firmware version plus interface summary. Run it first when anything is not
behaving.

## find

```bash
opnsense.py find <terms...> [--module MOD] [--limit N] [--json]
```

Searches the offline index of 2399 endpoints. Matching happens in three tiers,
and the output tells you which one produced the result:

1. **exact** — every term appears in the endpoint's module, controller, command
   or parameters.
2. **concept** — the query uses networking vocabulary that maps to controllers.
   `port forward`, `blocklist`, `bufferbloat`, `api key`, `lease`, `carp` and
   about seventy others resolve this way, because the index holds structural
   names only and "port forward" appears nowhere inside `firewall/d_nat/add_rule`.
3. **partial** — no endpoint matched every term, so results are ranked by how
   many matched, with a term naming a module weighted higher. This is what
   rescues `wireguard peer`, since WireGuard calls a peer a "client".

```bash
$ opnsense.py find port forward --limit 4
matched by concept — controllers that implement 'port forward':

POST      /api/firewall/d_nat/add_rule  (camel: addRule)
POST      /api/firewall/d_nat/apply
POST      /api/firewall/d_nat/del_rule  params: $uuid  (camel: delRule)
GET       /api/firewall/d_nat/get_rule  params: $uuid=null  (camel: getRule)
... 5 more (raise --limit)
```

`--json` emits the raw index rows, for scripting. Exit code is 1 when nothing
matched.

## show

```bash
opnsense.py show <module>/<controller>
```

Lists every command on one controller with its HTTP method, positional
parameters and camelCase alias, then names the endpoint that commits changes for
that controller.

```bash
$ opnsense.py show firewall/d_nat
/api/firewall/d_nat/ — 8 commands
  POST      add_rule  (camel: addRule)
  POST      del_rule  params: $uuid  (camel: delRule)
  GET       get_rule  params: $uuid=null  (camel: getRule)
  ...
commit changes with: POST /api/firewall/filter/apply
```

Commands marked `[inherited, undocumented]` are real but absent from the
official reference — see [Endpoint naming](#endpoint-naming).

## get

```bash
opnsense.py get <path> [args...] [--force]
```

`path` is `module/controller/command`; extra positional arguments become URL
segments.

```bash
opnsense.py get firewall/filter/search_rule
opnsense.py get firewall/alias/get_item 5f0b...c3
opnsense.py get core/backup/diff this 20260812 20260811
```

## post

```bash
opnsense.py post <path> [args...] [--data JSON|@file] [--dry-run] [--force]
```

```bash
opnsense.py post firewall/filter/add_rule --data @rule.json
opnsense.py post firewall/filter/toggle_rule 5f0b...c3 0
opnsense.py post firewall/filter/apply
```

After a successful write it tells you the change is not live yet and names the
commit endpoint:

```
saved to config.xml only — NOT live yet. Commit with:
  opnsense.py post firewall/filter/apply
```

`--dry-run` prints the exact request and its commit step without sending
anything.

Prefer `--data @file.json` over an inline string — shell quoting mangles JSON,
and the client says so explicitly when parsing fails.

## backup

```bash
opnsense.py backup [--out FILE]
```

Downloads the running `config.xml` (default `config-backup.xml`). Do this before
any change you might need to undo. Related endpoints for rollback:
`core/backup/backups`, `core/backup/diff`, `core/backup/revert_backup`, and
`core/snapshots/*` on ZFS installs.

---

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | The firewall refused the change (`result: failed` with validations), or a search matched nothing |
| 2 | Configuration, connectivity or endpoint error — the message says which |

A 200 response carrying `{"result": "failed", "validations": {...}}` is treated
as the failure it is. Checking only the HTTP status will mislead you.

## Endpoint naming

Three rules explain almost every 404:

- **The controller segment is literal.** `DNatController` becomes `d_nat`.
  `firewall/dnat` does not exist. Likewise `source_nat`, `one_to_one`,
  `alias_util`, `vlan_settings`.
- **The command accepts both forms.** The reference publishes `add_rule`; the
  GUI calls `addRule`. Phalcon camelizes, so both reach `addRuleAction`.
  Exception: `routes/routes` uses `addroute`, `searchroute`, `delroute` —
  lowercase, no separator.
- **The reference is incomplete and its method column is a guess.** It is
  generated per PHP class, so inherited actions are missing —
  `firewall/filter/apply` among them. And the generator states it records only
  the "most likely call method", which is why `wireguard/client/add_client` is
  published as `GET`. The client re-adds known inherited actions, and treats a
  method mismatch as a note rather than a block.

`--force` skips index validation entirely, for an endpoint you know exists that
the index does not carry.

## Regenerating the index

`skills/opnsense/scripts/data/endpoints.json` reflects the reference as
published for the 26.x series. The source pages are static Sphinx HTML at
`https://docs.opnsense.org/development/api/{core,plugins}/<name>.html`, with
five-cell tables (method, module, controller, command, parameters) — no
JavaScript and no authentication, so `html.parser` from the standard library is
enough to rebuild it for another release.

---

## MCP tools

The same capability is available as MCP tools via
`skills/opnsense/scripts/mcp_server.py`. See
[integrations.md](integrations.md) for client configuration.

| Tool | Maps to |
| --- | --- |
| `opnsense_find_endpoint` | `find` |
| `opnsense_describe_controller` | `show` |
| `opnsense_get` | `get` |
| `opnsense_post` | `post` (supports `dry_run`) |
| `opnsense_backup_config` | `backup` |
| `opnsense_probe` | `probe` |

`OPNSENSE_MCP_READONLY=1` makes `opnsense_post` refuse every call while leaving
the index and all reads working.

```bash
python skills/opnsense/scripts/mcp_server.py --selftest
```
