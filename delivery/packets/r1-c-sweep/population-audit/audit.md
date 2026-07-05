# R1-5 Full-Population Audit

Source plan: `delivery/packets/r1-5-copy-proof/search-run/plans/r1_5_fragile_possession_state_v0.json`
Plan hash: `ae4d5b3915454e78ff11b81f88cd302b3564c12de1af978a52b3c420ba69c20e`
Execution plan hash: `bc77278b3358106178749a72edfdc730b56b23bd6b6b650c60895598ac2edfbe`
Match scope: `canonical_matches.parquet` (7 matches)

## Summary

Total terminal rows: 8414
Terminal population hash: `5cb6279ffb2ac055c20dcb928de42ea728916d3d6a07003b9b4479033b7706ab`

### Status Distributions

- `typed_join_status`: UNKNOWN 5654, FAIL 2615, PASS 145
- `window_status`: UNKNOWN 4702, FAIL 1420, PASS 2292
- `pressure_status`: None 2560, FAIL 5138, PASS 716
- `support_arrival_status`: None 2560, PASS 2546, FAIL 3308

### UNKNOWN Accounting

- `typed_join_unknown_rows`: 5654
- `window_unknown_rows`: 4702
- `pressure_unknown_rows`: 0
- `support_arrival_unknown_rows`: 0

Requested-evidence missing rows: 5654

### By Role / Match / Period

| Role | Match | Period | Rows | Status distribution |
| --- | --- | --- | ---: | --- |
| `away` | `J03WOH` | `firstHalf` | 254 | UNKNOWN 206, FAIL 44, PASS 4 |
| `away` | `J03WOH` | `secondHalf` | 249 | UNKNOWN 180, FAIL 62, PASS 7 |
| `away` | `J03WOY` | `firstHalf` | 283 | UNKNOWN 201, FAIL 80, PASS 2 |
| `away` | `J03WOY` | `secondHalf` | 292 | UNKNOWN 181, FAIL 107, PASS 4 |
| `away` | `J03WPY` | `firstHalf` | 415 | UNKNOWN 338, FAIL 76, PASS 1 |
| `away` | `J03WPY` | `secondHalf` | 239 | UNKNOWN 206, FAIL 30, PASS 3 |
| `away` | `J03WQQ` | `firstHalf` | 389 | FAIL 175, UNKNOWN 206, PASS 8 |
| `away` | `J03WQQ` | `secondHalf` | 273 | UNKNOWN 119, FAIL 137, PASS 17 |
| `away` | `J03WR9` | `firstHalf` | 358 | UNKNOWN 260, FAIL 92, PASS 6 |
| `away` | `J03WR9` | `secondHalf` | 291 | FAIL 40, UNKNOWN 249, PASS 2 |
| `away` | `J03WMX` | `firstHalf` | 439 | UNKNOWN 252, FAIL 181, PASS 6 |
| `away` | `J03WMX` | `secondHalf` | 275 | UNKNOWN 197, FAIL 72, PASS 6 |
| `away` | `J03WN1` | `firstHalf` | 292 | UNKNOWN 251, FAIL 38, PASS 3 |
| `away` | `J03WN1` | `secondHalf` | 158 | UNKNOWN 126, PASS 3, FAIL 29 |
| `home` | `J03WOH` | `firstHalf` | 254 | UNKNOWN 154, FAIL 92, PASS 8 |
| `home` | `J03WOH` | `secondHalf` | 249 | FAIL 89, UNKNOWN 155, PASS 5 |
| `home` | `J03WOY` | `firstHalf` | 283 | FAIL 106, UNKNOWN 168, PASS 9 |
| `home` | `J03WOY` | `secondHalf` | 292 | UNKNOWN 216, FAIL 74, PASS 2 |
| `home` | `J03WPY` | `firstHalf` | 415 | FAIL 217, UNKNOWN 189, PASS 9 |
| `home` | `J03WPY` | `secondHalf` | 239 | UNKNOWN 121, FAIL 112, PASS 6 |
| `home` | `J03WQQ` | `firstHalf` | 389 | UNKNOWN 247, FAIL 136, PASS 6 |
| `home` | `J03WQQ` | `secondHalf` | 273 | UNKNOWN 221, FAIL 51, PASS 1 |
| `home` | `J03WR9` | `firstHalf` | 358 | UNKNOWN 192, FAIL 158, PASS 8 |
| `home` | `J03WR9` | `secondHalf` | 291 | UNKNOWN 134, FAIL 151, PASS 6 |
| `home` | `J03WMX` | `firstHalf` | 439 | UNKNOWN 345, FAIL 92, PASS 2 |
| `home` | `J03WMX` | `secondHalf` | 275 | UNKNOWN 182, FAIL 85, PASS 8 |
| `home` | `J03WN1` | `firstHalf` | 292 | UNKNOWN 212, FAIL 77, PASS 3 |
| `home` | `J03WN1` | `secondHalf` | 158 | UNKNOWN 146, FAIL 12 |
