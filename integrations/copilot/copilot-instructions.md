# OPNsense administration

When working with an OPNsense firewall, use the client at
`skills/opnsense/scripts/opnsense.py` and the references in
`skills/opnsense/references/`.

## Endpoint names are not guessable

The API has 2399 endpoints across 93 modules. Look one up before calling it:

```bash
python skills/opnsense/scripts/opnsense.py find port forward
python skills/opnsense/scripts/opnsense.py show firewall/d_nat
```

Concrete traps: port forwards are `firewall/d_nat` (not `firewall/dnat`); the
reference publishes `add_rule` while the GUI calls `addRule`; static routes use
`addroute` with no separator; and `firewall/filter/apply` — the call that makes
any rule change take effect — is absent from the official reference because it
is inherited from a base class.

## Writes are not live until committed

```bash
python skills/opnsense/scripts/opnsense.py post firewall/filter/add_rule --data @rule.json
python skills/opnsense/scripts/opnsense.py post firewall/filter/apply
```

`add_*`, `set_*`, `del_*` and `toggle_*` only edit `config.xml`. Forgetting the
commit leaves a change that applies silently later, on the next unrelated apply
or reboot.

A 200 response carrying `{"result": "failed", "validations": {...}}` is a
failure — nothing was saved, and the keys name the bad fields.

## Safety

There is no automatic rollback. Back up before changing anything
(`opnsense.py backup --out pre-change.xml`), and on a remote firewall arm
`echo "pfctl -d" | at now + 5 minutes` before editing filter rules.

Ask the user before any change that could affect reachability. Read-only
queries do not need confirmation.

See `AGENTS.md` for the full workflow and `skills/opnsense/references/pitfalls.md`
for verified traps.
