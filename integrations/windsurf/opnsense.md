---
trigger: model_decision
description: Administering an OPNsense firewall via its REST API, configd or shell
---

# OPNsense administration

Client: `python skills/opnsense/scripts/opnsense.py`. References:
`skills/opnsense/references/`.

## Look endpoints up, never guess

2399 endpoints, 93 modules, unpredictable names. Port forwards are
`firewall/d_nat` (`firewall/dnat` 404s). Static routes use `addroute`.
`firewall/filter/apply` works but is missing from the official reference, which
is generated per PHP class and drops inherited actions.

```bash
python skills/opnsense/scripts/opnsense.py find port forward
python skills/opnsense/scripts/opnsense.py show firewall/d_nat
```

## Two-phase changes

Writes edit `config.xml` only; the change goes live when you POST the
controller's `apply` or `reconfigure` endpoint. `show` tells you which one.
`{"result":"failed","validations":{...}}` means nothing was saved.

## Safety

No savepoint, no automatic rollback. Back up first; arm
`echo "pfctl -d" | at now + 5 minutes` before touching filter rules remotely;
add the permissive rule before removing the old one. Confirm anything affecting
reachability.

Full workflow in `AGENTS.md`; traps in `skills/opnsense/references/pitfalls.md`.
