# Traffic shaper

Module `trafficshaper`, commit with `POST /api/trafficshaper/service/reconfigure`.
Built on FreeBSD `dummynet`/`ipfw`, which runs *beside* pf rather than inside it.

## Model

Three layers, created in this order:

1. **Pipe** — a bandwidth limit with a scheduler. This is where the speed lives.
2. **Queue** — an optional weighted share of a pipe, for prioritising between
   traffic classes.
3. **Rule** — selects which traffic enters a pipe or queue.

## Endpoints

`trafficshaper/settings` provides `search_pipes` / `search_queues` /
`search_rules` and the matching `get_*`, `add_*`, `set_*`, `del_*`, `toggle_*`,
plus `download_*` / `upload_*` for bulk edits. `trafficshaper/service` adds
`statistics` and `flushreload`.

```bash
python scripts/opnsense.py get trafficshaper/settings/search_pipes
python scripts/opnsense.py get trafficshaper/service/statistics
```

## Per-host versus aggregate — the decision that gets made wrong

A pipe on its own is an **aggregate** limit: a 10 Mbit pipe is 10 Mbit shared by
everyone matching the rule. To give *each* host its own 10 Mbit, set the pipe's
**mask** to `source` (or `destination`, depending on direction). Without the
mask, one busy host starves the rest and it looks like the shaper is broken.

Pick the mask side by direction: limiting upload from the LAN masks on `source`;
limiting download to the LAN masks on `destination`.

## Direction and which interface

Shaper rules are evaluated on the **LAN-side** interface for both directions,
which is counterintuitive. Traffic arriving from the internet is "in" on WAN but
you shape it as it heads out toward the client. Attaching rules to WAN is a
common cause of a shaper that does nothing.

Create two rules — one per direction — and give each its own pipe. A single
bidirectional rule cannot express asymmetric links.

## fq_codel

For bufferbloat, use `fq_codel` as the pipe scheduler and set the pipe bandwidth
to roughly 90–95% of the measured line rate. The shaper can only control a queue
it owns; if the pipe is set at or above the real capacity, the bottleneck stays
at the ISP and there is nothing to manage.

## Verifying

```bash
python scripts/opnsense.py get trafficshaper/service/statistics
ssh root@<host> 'dnctl pipe show'
ssh root@<host> 'dnctl list'
ssh root@<host> 'ipfw show'
```

`dnctl pipe show` reporting **0 flows** while traffic is running means the ipfw
hooks are not classifying anything — the rule is not matching, not that the
limit is wrong. Check the interface and direction on the rule first.

## Known breakage

The shaper has had real regressions worth ruling out before deep debugging: a
`fq_codel` bandwidth-not-enforced bug on the 26.1 series, and a report on
26.7.1_1 (FreeBSD 15.1) where a dummynet delay of ≥10 ms blocked all traffic on
the pipe. If the configuration reads correctly and behaves absurdly, check the
release notes and issue tracker for your exact version before rebuilding it.

After changing pipes, a plain reconfigure sometimes leaves stale ipfw state:

```bash
python scripts/opnsense.py post trafficshaper/service/flushreload
```
