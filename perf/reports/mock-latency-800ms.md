# Load test: mock LLM, simulated model latency 800 ms

| Metric | Value |
|---|---|
| Users | ramped 10 → 25 → 50 over 90 s |
| Requests | 1111 (12.3 req/s) |
| Error rate | 0.00% (0 failed) |
| p50 / p95 / p99 latency (all requests) | 870 / 1800 / 2100 ms |
| Chat requests logged in DB | 1000 |
| Avg tokens per chat request | 1182 (mock: 4 characters ≈ 1 token) |
| Avg estimated cost per chat request | $0.005059 (at $4 / $20 per MTok in/out) |
| Estimated cost of the whole run | $5.0592 |

| Endpoint | Requests | Failures | p50 ms | p95 ms | p99 ms |
|---|---|---|---|---|---|
| /chat [grounded] | 592 | 0 | 840 | 1200 | 1200 |
| /chat [refusal] | 205 | 0 | 820 | 1200 | 1200 |
| /chat [tool] | 198 | 0 | 1600 | 2100 | 2300 |
| /health | 116 | 0 | 4 | 8 | 12 |
