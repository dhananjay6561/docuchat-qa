# Load test: mock LLM, simulated model latency 0 ms

| Metric | Value |
|---|---|
| Users | ramped 10 → 25 → 50 over 90 s |
| Requests | 1599 (17.7 req/s) |
| Error rate | 0.00% (0 failed) |
| p50 / p95 / p99 latency (all requests) | 10 / 17 / 27 ms |
| Chat requests logged in DB | 1456 |
| Avg tokens per chat request | 1199 (mock: 4 characters ≈ 1 token) |
| Avg estimated cost per chat request | $0.005124 (at $4 / $20 per MTok in/out) |
| Estimated cost of the whole run | $7.4607 |

| Endpoint | Requests | Failures | p50 ms | p95 ms | p99 ms |
|---|---|---|---|---|---|
| /chat [grounded] | 870 | 0 | 10 | 17 | 27 |
| /chat [refusal] | 292 | 0 | 10 | 16 | 41 |
| /chat [tool] | 293 | 0 | 10 | 17 | 26 |
| /health | 144 | 0 | 4 | 12 | 15 |
