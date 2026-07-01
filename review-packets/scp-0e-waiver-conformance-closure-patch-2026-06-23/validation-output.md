# Validation Output

## Command: `make scp-0-verify`

Working directory:

```text
/Users/luisrevilla/Documents/priori
```

Result: PASS

Evidence:

```text
commands/make-scp-0-verify.log
```

Key tail:

```text
"status": "PASS"
Ran 49 tests in 12.079s
OK
```

## Command: `make test`

Working directory:

```text
/Users/luisrevilla/Documents/priori
```

Result: PASS

Evidence:

```text
commands/make-test.log
```

Key tail:

```text
Ran 131 tests in 291.661s
OK
{"attestation_status": "VERIFIED", "blocking_reasons": []}
```

## Notes

- These logs were produced after committing `fb8193a`.
- The packet is inspection-only. Rerunning commands requires the full repository and local environment.

