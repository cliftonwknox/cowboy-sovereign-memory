---
description: Show the health and contents of Cowboy Claude's Sovereign Memory — store counts, pending proposals, open conflicts, and whether the embedder/dreamer services are up.
---

Report the status of **Cowboy Claude's Sovereign Memory**:

- Active memory counts by layer (episodic / semantic) — run a quick query against the store.
- Pending proposals (promote / merge / consolidate) waiting for review, and open conflicts.
- Whether the embedder endpoint (and dreamer, if configured) responds to `/health`.
- The configured tier (store backend + whether a dreamer is set).

If anything's down, tell me plainly and what to do about it. If there are pending proposals or conflicts, summarize them and offer to walk me through approving/resolving them (nothing durable changes without my say-so).
