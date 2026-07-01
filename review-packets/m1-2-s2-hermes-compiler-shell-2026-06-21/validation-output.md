# Validation Output

Working directory: `/Users/luisrevilla/Documents/priori`

Date: 2026-06-21

```bash
python -m py_compile src/tqe/workshop/m1_2.py src/tqe/workshop/hermes_s2.py src/tqe/verification/m1_2.py src/tqe/verification/m1_2_gate_s0.py src/tqe/verification/m1_2_gate_s1.py src/tqe/verification/m1_2_gate_s2.py
```

Result: pass.

```bash
make m1-2-gate-s0-verify
```

Result: pass, 17/17.

```bash
make m1-2-gate-s2-verify
```

Result: pass, 8/8.

```bash
make m1-2-verify
```

Result: pass, 3/3.

```bash
make m1-1-gate-s7r-verify
```

Result: pass, 13/13.

```bash
make test
```

Result: pass.

```text
Ran 27 tests in 174.521s
OK
```
