# Validation Output

Working directory: `/Users/luisrevilla/Documents/priori`

Date: 2026-06-21

```bash
python -m py_compile src/tqe/workshop/m1_2.py src/tqe/verification/m1_2_gate_s0.py src/tqe/verification/m1_2_gate_s1.py
```

Result: pass.

```bash
make m1-2-gate-s0-verify
```

Result: pass, 17/17.

```bash
make m1-2-gate-s1-verify
```

Result: pass, 10/10.

```bash
make m1-2-verify
```

Result: pass, 2/2.

```bash
make m1-1-gate-s7r-verify
```

Result: pass, 13/13.

```bash
make test
```

Result: pass.

```text
Ran 27 tests in 174.070s
OK
```
