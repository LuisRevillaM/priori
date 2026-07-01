# Validation Output

Working directory: `/Users/luisrevilla/Documents/priori`

Date: 2026-06-21

```bash
python -m py_compile src/tqe/workshop/hermes_s2.py src/tqe/verification/m1_2_gate_s2.py src/tqe/verification/m1_2.py
```

Result: pass.

```bash
make m1-2-gate-s2-verify
```

Result: pass, 12/12.

```bash
make m1-2-verify
```

Result: pass, 3/3.

```bash
make test
```

Result: pass.

```text
Ran 27 tests in 190.982s
OK
```

```bash
make m1-1-gate-s7r-verify
```

Result: pass, 13/13.
