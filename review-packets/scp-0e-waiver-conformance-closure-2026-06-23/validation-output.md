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
Ran 42 tests in 10.389s
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
Ran 124 tests in 304.684s
OK
{"attestation_status": "VERIFIED", "blocking_reasons": []}
```

## Notes

- These logs were produced after committing `beea7df`.
- The packet is inspection-only. Rerunning commands requires the full repository, local environment, and dependencies.

