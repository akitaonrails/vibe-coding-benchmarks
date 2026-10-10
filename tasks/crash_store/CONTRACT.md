# Crash store: bounded development instance v1

Implement `Solution#call(request)` (Ruby) or `Solution::call(Value) -> Value`
(Rust). The supplied JSONL adapter owns transport. A fresh process has no store;
its first request is `init`. All inputs obey this schema. Integers are at most
1,000,000; keys and values are Unicode strings of at most 40 characters. No
host filesystem persistence is needed: `crash` is a simulated power failure.

This is a logical durability model, not a production disk format or the full
F1 frontier task. Durable page writes are atomic; the incomplete next write is
ignored. There are no checksums or arbitrary byte corruption in this instance.

## State and operations

* `{"op":"init","capacity":N}` resets everything, N in 1..128. Return
  `{"ok":true}`. Current map is empty and has no pages. Snapshot IDs start at 1.
* `{"op":"commit","changes":[[key,value_or_null],...]}` applies changes in
  order to the current map; null deletes. The entire resulting map is written
  copy-on-write into **max(1, number of keys)** newly allocated pages, even for
  an empty or unchanged result. Each page has an increasing integer identity,
  beginning at 1. Allocation consumes lowest new identities first; IDs never
  recycle. If free capacity cannot hold the entire new map, return
  `{"error":"full"}` with absolutely no state change, including ID counters.
  On success, publish the complete map atomically and return `{"ok":true}`.
  Old pages remain allocated until reclamation, whether live or garbage.
* Optional `"cut":K` on commit simulates a crash after K durable steps.
  First come the new map's individual page writes, then one publication step.
  Allocate exactly min(K,page_count) pages. The map is published iff
  K >= page_count+1. Return `{"crashed":true}` even if publication happened.
  There is no acknowledgement before publication. Capacity is checked first:
  a full commit returns `full`, even when a cut is supplied. No volatile pending
  transaction survives. An interrupted map's pages are garbage.
* `{"op":"snapshot"}` durably records the current map and its pages. Return
  `{"snapshot":ID}` and advance the snapshot counter. Snapshots of the initial
  empty map consume no pages. IDs never recycle, including across crashes.
* `{"op":"drop","snapshot":ID}` removes a live snapshot and returns
  `{"ok":true}`. Unknown/dropped IDs return `{"error":"snapshot"}`.
* `{"op":"read"}` returns `{"data":{key:value,...}}` for current state.
  With `"snapshot":ID`, read that snapshot, or return `{"error":"snapshot"}`.
  JSON object ordering is immaterial.
* `{"op":"reclaim"}` removes all allocated pages not referenced by current
  state or any live snapshot, oldest page ID first. Return `{"reclaimed":N}`.
  Optional `"cut":K` instead removes only the first min(K,garbage_count)
  garbage pages and returns `{"crashed":true}`. Live pages never move.
* `{"op":"crash"}` discards volatile work; return `{"ok":true}`. All published
  maps, snapshots, allocated pages and counters above are durable.
* `{"op":"status"}` returns `{"used":N,"live":L,"snapshots":S}`. Used counts
  all allocated pages; live counts the union referenced by current/snapshots;
  S counts live snapshot handles.

Cuts are nonnegative integers. Unknown operations are not generated. Every
request produces exactly one JSON object, including errors and simulated
crashes. All traces contain at most 400 requests. Do not delegate domain logic
to another language. Only `src/**` is candidate-editable; build/run scripts and
package configuration are supplied and protected. Both language ports receive
the same contract. A no-supplied-tests condition still receives this contract.
