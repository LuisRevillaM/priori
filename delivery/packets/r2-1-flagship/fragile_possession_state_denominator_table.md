# R2-1 Flagship Denominator Table

Plan: `delivery/packets/r2-1-flagship/aggregate_over_fragile_possession_state_v0.json`
Plan hash: `f6e8310c02cf22d65f3faf85d4af3bdcc9cf6c47a057e655dd1915df0e2d6031`
Sealed audit: `delivery/packets/r1-c-sweep/population-audit/audit.json`

| Role | Match | Observed PASS | Lower | Upper | UNKNOWN | Population | FAIL |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `home` | `J03WOH` | 13 | 13 | 322 | 309 | 503 | 181 |
| `home` | `J03WOY` | 11 | 11 | 395 | 384 | 575 | 180 |
| `home` | `J03WPY` | 15 | 15 | 325 | 310 | 654 | 329 |
| `home` | `J03WQQ` | 7 | 7 | 475 | 468 | 662 | 187 |
| `home` | `J03WR9` | 14 | 14 | 340 | 326 | 649 | 309 |
| `home` | `J03WMX` | 10 | 10 | 537 | 527 | 714 | 177 |
| `home` | `J03WN1` | 3 | 3 | 361 | 358 | 450 | 89 |
| `away` | `J03WOH` | 11 | 11 | 397 | 386 | 503 | 106 |
| `away` | `J03WOY` | 6 | 6 | 388 | 382 | 575 | 187 |
| `away` | `J03WPY` | 4 | 4 | 548 | 544 | 654 | 106 |
| `away` | `J03WQQ` | 25 | 25 | 350 | 325 | 662 | 312 |
| `away` | `J03WR9` | 8 | 8 | 517 | 509 | 649 | 132 |
| `away` | `J03WMX` | 12 | 12 | 461 | 449 | 714 | 253 |
| `away` | `J03WN1` | 6 | 6 | 383 | 377 | 450 | 67 |

## Totals

- Observed PASS/lower bound: 145
- Upper bound: 5799
- UNKNOWN rows: 5654
- FAIL rows: 2615
- Population rows: 8414

## Sealed Audit Reconciliation

- Sealed PASS rows: 145
- Sealed FAIL rows: 2615
- Sealed UNKNOWN rows: 5654
- Sealed total rows: 8414
- All 14 role-match rows match sealed status counts: True
