# R2-2 Flagship CAR-0 Retention Rate Table

Plan: `delivery/packets/r2-2-flagship/rate_and_share_car0_retention_v0.json`
Plan hash: `4a5650d8072539b68363d776bc146566bf47758226815f7eb523d5e71a675dba`
R2-1 denominator table: `delivery/packets/r2-1-flagship/fragile_possession_state_denominator_table.json`

| Role | Match | Rate | Lower | Upper | A | B | C | D1 | D2 | E | Known Den | Source Rows |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `home` | `J03WOH` | 0.722 | 0.070 | 0.973 | 13 | 5 | 2 | 0 | 167 | 316 | 18 | 503 |
| `home` | `J03WOY` | 0.688 | 0.064 | 0.971 | 11 | 5 | 2 | 0 | 155 | 402 | 16 | 575 |
| `home` | `J03WPY` | 0.625 | 0.072 | 0.957 | 15 | 9 | 1 | 0 | 183 | 446 | 24 | 654 |
| `home` | `J03WQQ` | 0.700 | 0.054 | 0.977 | 7 | 3 | 12 | 0 | 107 | 533 | 10 | 662 |
| `home` | `J03WR9` | 0.700 | 0.072 | 0.969 | 14 | 6 | 4 | 0 | 170 | 455 | 20 | 649 |
| `home` | `J03WMX` | 0.625 | 0.040 | 0.976 | 10 | 6 | 4 | 0 | 229 | 465 | 16 | 714 |
| `home` | `J03WN1` | 0.600 | 0.011 | 0.993 | 3 | 2 | 2 | 0 | 269 | 174 | 5 | 450 |
| `away` | `J03WOH` | 0.647 | 0.059 | 0.968 | 11 | 6 | 3 | 0 | 167 | 316 | 17 | 503 |
| `away` | `J03WOY` | 0.545 | 0.035 | 0.971 | 6 | 5 | 4 | 0 | 155 | 405 | 11 | 575 |
| `away` | `J03WPY` | 0.667 | 0.021 | 0.990 | 4 | 2 | 6 | 0 | 183 | 459 | 6 | 654 |
| `away` | `J03WQQ` | 0.694 | 0.170 | 0.925 | 25 | 11 | 4 | 0 | 107 | 515 | 36 | 662 |
| `away` | `J03WR9` | 0.800 | 0.044 | 0.989 | 8 | 2 | 1 | 0 | 170 | 468 | 10 | 649 |
| `away` | `J03WMX` | 0.632 | 0.047 | 0.972 | 12 | 7 | 6 | 0 | 229 | 460 | 19 | 714 |
| `away` | `J03WN1` | 0.429 | 0.021 | 0.972 | 6 | 8 | 3 | 0 | 269 | 164 | 14 | 450 |

## Totals

- A retained fragile rows: 145
- B known non-retained rows inside known denominator: 77
- C numerator-UNKNOWN rows inside known denominator: 54
- D1 denominator-UNKNOWN / numerator-FAIL rows: 0
- D2 denominator-UNKNOWN / numerator-UNKNOWN rows: 2560
- E denominator-FAIL rows excluded from the rate: 5578
- Source rows: 8414

## R2-1 Denominator Reconciliation

- Same 14 role-match rows: True
- Source population count matches R2-1: 8414 == 8414
- A count matches R2-1 typed_join_status PASS count: 145 == 145
- All 14 source populations match R2-1: True
- All 14 retained fragile PASS counts match R2-1: True
