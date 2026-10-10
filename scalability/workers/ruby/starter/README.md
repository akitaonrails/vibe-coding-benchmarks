# Clean-path starter

This starter computes healthy effects and acknowledges only HTTP200/201. It
intentionally lacks the complete timeout, retry, DLQ and bounded-concurrency policy.
It uses one consumer slot. Implement the public scalability/CONTRACT.md before
fault qualification. This is not a qualified reference or a capacity result.

Bunny normal connection/consumer recovery remains enabled. Baseline behavior may
vary with idiomatic library features across ecosystems; those features are part
of the comparison, rather than intentionally disabled implementation work.
