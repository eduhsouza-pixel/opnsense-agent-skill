# Pitfalls

Traps verified against a running OPNsense 26.7 / FreeBSD 15.1, or against the
API reference itself. Each one produces a confusing symptom rather than a clean
error.

## There is no savepoint or automatic rollback

Some third-party OPNsense tooling documents a "savepoint / 60-second automatic
rollback" on firewall changes. **The core MVC API has no such thing.** There is
no `savepoint` or `rollback` endpoint anywhere in the 2399-endpoint surface, and
`applyAction` is a plain `configdRun('filter reload skip_alias')`. A rule that
locks you out stays locked in.

(The legacy `os-firewall` plugin API did expose savepoints. That is a different
code path and not what `/api/firewall/filter/*` uses.)

Mitigate with a backup, a `pfctl -d` dead-man switch, and a VM/ZFS snapshot.

## `apply` uses `skip_alias`, so pf tables are not rebuilt

Deleting an alias leaves its pf table loaded and orphaned. Even a full
`configctl filter reload` does not remove it. Only this does:

```bash
pfctl -t <TABLE_NAME> -T kill
```

Relatedly, `configctl filter delete.table` does **not** delete a table — it
takes two parameters and removes one *entry* from a table.

## The pf rule label is the API UUID

This is the only reliable way to correlate an API rule with live counters:

```bash
pfctl -sr -vv | grep -A2 <uuid>
```

`/api/diagnostics/firewall/stats` gives counters **per interface**, not per
rule, so it cannot do this join.

## `pfctl -sr` prints service names, not port numbers

Port 53 shows as `domain`, 853 as `domain-s`, 443 as `https`. Grepping the
ruleset for a port number finds nothing. Search by the rule UUID instead.

## Username and password are rejected by the REST API

The API returns 401 for GUI credentials — it needs a key/secret pair. If you
truly only have a password, the fallback is a form POST to `/index.php` and
reusing the `WebSession` cookie, but the CSRF hidden field has a **randomised
name per session**: parse both `name` and `value` out of the same GET, and send
`X-CSRFToken` on subsequent calls. Generating a proper key is almost always
faster.

## `config.xml` user entries carry a UUID attribute

The tag is `<user uuid="...">`, never a bare `<user>`. Any grep or sed for
`<user>` literally matches nothing.

## Service status can lie

`service unbound onestatus` has reported `not running` while the process was up
and the port was listening. Cross-check with `sockstat -4 -l | grep :53` and
`ps auxw | grep unbound` before acting on a status string.

## DNS blocklist tests fool you with caching

After changing a DNSBL, a client that already resolved the domain keeps the old
answer until the TTL expires, and Unbound caches its own view. Test with
`drill @<firewall-ip> <domain>` from a machine that has not queried it, and
flush with `configctl unbound dnsbl` plus a service reconfigure.

The built-in blocklist tester is local-only and cannot match domains that
resolve via CNAME into a blocked zone.

## The root shell is a menu

Root's shell is `/usr/local/sbin/opnsense-shell`. An interactive SSH session
lands in the console menu; remote command execution (`ssh host "command"`)
bypasses it and behaves normally. For long or quote-heavy commands, send base64:

```bash
echo <base64> | openssl base64 -d -A | sh
```

## Selection fields silently reset

See [api-conventions.md](api-conventions.md) — reading a model with `get` and
POSTing it back unchanged will blank every multi-select field, because `get`
returns option dictionaries and `set` expects flat comma-separated keys.

## The XML rule parser is not a source of truth

Parsing `config.xml` for firewall rules has returned zero results on a box with
78 active rules — automation-generated and plugin rules do not all live where
you expect. Use the API or `pfctl` to enumerate rules.
