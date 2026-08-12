# OPNsense administration

Gemini CLI reads this file by default. The full instructions live in
[AGENTS.md](AGENTS.md) — read it before administering an OPNsense firewall.

The three rules that matter most:

1. **Never guess an endpoint name.** Run
   `python skills/opnsense/scripts/opnsense.py find <what you want>` first.
   Port forwards are `firewall/d_nat`, not `firewall/dnat`.
2. **Every write needs a separate commit.** `add_*`/`set_*`/`del_*` only edit
   `config.xml`; the change is not live until you POST the controller's `apply`
   or `reconfigure` endpoint.
3. **There is no rollback.** Back up first, and arm
   `echo "pfctl -d" | at now + 5 minutes` before touching filter rules on a
   remote firewall.
