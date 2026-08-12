# OPNsense administration

Use `python skills/opnsense/scripts/opnsense.py` for anything touching an
OPNsense firewall. Detailed references are in `skills/opnsense/references/`.

## Never guess an endpoint name

```bash
python skills/opnsense/scripts/opnsense.py find port forward
python skills/opnsense/scripts/opnsense.py show firewall/d_nat
```

The API has 2399 endpoints and the names do not follow intuition: port forwards
are `firewall/d_nat`, static routes use `addroute`, and `firewall/filter/apply`
is real but absent from the official reference because it is inherited from a
base class. A guessed name gives a 404 that looks like a missing feature.

## Writes need a separate commit

`add_*`/`set_*`/`del_*`/`toggle_*` return `{"result":"saved"}` and change only
`config.xml`. POST the controller's `apply` or `reconfigure` to make it live.
Forgetting means the change fires later, unexpectedly.

`{"result":"failed","validations":{...}}` on HTTP 200 is still a failure.

## Safety

No automatic rollback exists. Back up (`opnsense.py backup`), arm
`echo "pfctl -d" | at now + 5 minutes` before remote filter-rule edits, and ask
the user before any change that could affect reachability.

See `AGENTS.md` and `skills/opnsense/references/pitfalls.md`.
