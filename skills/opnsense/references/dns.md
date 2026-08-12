# DNS — Unbound, DNSBL and Dnsmasq

## Unbound

Module `unbound`, commit with `POST /api/unbound/service/reconfigure`.

| Controller | Purpose |
| --- | --- |
| `settings` | All configuration (see below) |
| `service` | `reconfigure`, `reconfigure_general`, `restart`, `start`, `stop`, `status`, `dnsbl` |
| `diagnostics` | `stats`, `dumpcache`, `dumpinfra`, `listlocaldata`, `listlocalzones`, `listinsecure`, `test_blocklist` |
| `overview` | `search_queries`, `totals`, `get_policies`, `is_enabled`, `is_block_list_enabled` |

`settings` follows `search_X` / `get_X` / `add_X` / `set_X` / `del_X` /
`toggle_X` for each of: `host_override`, `host_alias`, `forward`, `acl`,
`dnsbl`.

### Local DNS records

```bash
python scripts/opnsense.py get unbound/settings/search_host_override
python scripts/opnsense.py post unbound/settings/add_host_override --data \
  '{"host":{"enabled":"1","hostname":"nas","domain":"lan.local","rr":"A","server":"192.168.1.20"}}'
python scripts/opnsense.py post unbound/service/reconfigure
```

`host_alias` adds extra names pointing at an existing override.

### Conditional forwarding

`add_forward` sends one domain to a specific upstream — the usual way to hand
an internal zone to an AD controller. Leave `domain` empty to forward
everything (full forwarding mode).

### Validating before restarting

```bash
ssh root@<host> 'configctl unbound check'
```

This reports errors that would stop Unbound from starting, plus warnings. Run it
after any custom-options change and before a reconfigure on a production
resolver.

## DNSBL blocklists

Managed through `unbound/settings/*_dnsbl` and applied with either
`unbound/service/dnsbl` or a full reconfigure.

```bash
python scripts/opnsense.py get unbound/settings/get_dnsbl
python scripts/opnsense.py post unbound/settings/set_dnsbl --data @dnsbl.json
python scripts/opnsense.py post unbound/service/dnsbl
```

Fields that matter: the blocklist source URLs, `whitelists` (regex-matched
allow entries), `blocklists` (extra domains), and the return type —
**`NXDOMAIN` is the sane default**. If you pick an address return type instead,
the destination field matters; with `NXDOMAIN` it is ignored entirely.

`source_nets` scopes the policy to specific client networks; empty means every
client.

### Testing without fooling yourself

Three separate caches sit between a change and an observed result: the client
stub resolver, Unbound's own cache, and the record's TTL. Test from a host that
has not asked before, aimed straight at the firewall:

```bash
drill @192.168.1.1 blocked.example.com     # expect NXDOMAIN
drill @192.168.1.1 example.com             # expect NOERROR — proves DNS still works
```

Always test a domain that should *not* be blocked in the same breath; an
over-broad list that breaks all resolution otherwise looks like success.

The built-in blocklist tester (`test_blocklist`) is local-only and cannot follow
CNAMEs into a blocked zone, so it disagrees with real lookups sometimes.

Large lists are heavy: a combined social-media policy produced a ~6 MB
`dnsbl.json`. Watch memory on small appliances.

### DNSSEC check

```bash
drill -D sigok.verteiltesysteme.net     # must resolve
drill -D sigfail.verteiltesysteme.net   # must SERVFAIL
```

## Dnsmasq

Module `dnsmasq`, commit with `POST /api/dnsmasq/service/reconfigure`. It serves
DNS and DHCP together, and OPNsense increasingly favours it over ISC DHCP.

`settings` manages `host`, `domain`, `range`, `option`, `tag`, `boot` with the
usual verb set, plus `download_hosts` / `upload_hosts` for bulk work.

Unbound and Dnsmasq can both be running and both listening on port 53 on
different addresses. Before diagnosing a resolution problem, establish which one
the client is actually reaching:

```bash
ssh root@<host> 'sockstat -4 -l | grep :53'
```

Do not trust `service unbound onestatus` alone — it has reported `not running`
for a live process.
