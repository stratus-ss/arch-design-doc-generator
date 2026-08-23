# Health Check Documentation

Use the guide that matches how you are collecting data. Both paths feed the same health check report pipeline, but the collection prerequisites and workflow differ.

| If you are doing... | Start here |
|---|---|
| Live collection from a cluster with `oc` access | [`collect/README.md`](collect/README.md) |
| Offline collection from a must-gather via supportshell / `omc` | [`supportshell/README.md`](supportshell/README.md) |

See also:

- [`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md)
- [`../../docs/HC_CHECK_RATIONALE.md`](../../docs/HC_CHECK_RATIONALE.md)
- [`../../docs/HC_Command_Reference.md`](../../docs/HC_Command_Reference.md)
- [Knowledge Base (KB) for recommendations and notes](../../README.md#knowledge-base-kb-for-recommendations-and-notes) — why some `[[checks]]` rows only set `content_from`
