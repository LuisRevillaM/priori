PYTHON ?= $(if $(wildcard $(CURDIR)/.venv/bin/python),$(CURDIR)/.venv/bin/python,python3.12)
PYTHONPATH := $(CURDIR)/src
export PYTHONPATH

.PHONY: setup provision-j03woh provision-corpus gate-a-build gate-b-build gate-c-build gate-a-verify gate-b-verify gate-c-verify m1-verify m1-baseline-freeze test

setup:
	python3.12 -m venv .venv
	$(CURDIR)/.venv/bin/python -m pip install --upgrade pip
	$(CURDIR)/.venv/bin/python -m pip install -e .
	npm --prefix apps/replay-proof install

provision-j03woh:
	$(PYTHON) scripts/data/source_lock_idsse.py --match-id J03WOH --download

provision-corpus:
	$(PYTHON) scripts/data/source_lock_idsse.py --match-id ALL --artifact-dir artifacts/m1/gate-b --download

gate-a-build:
	$(PYTHON) -m tqe.data.gate_a_build
	$(PYTHON) -m tqe.evidence.gate_a_replay

gate-b-build:
	$(PYTHON) -m tqe.data.gate_b_build

gate-c-build:
	$(PYTHON) -m tqe.evidence.gate_c_build
	npm --prefix apps/replay-proof run build
	npm --prefix apps/replay-proof run verify

gate-a-verify:
	$(PYTHON) -m tqe.verification.gate_a

gate-b-verify:
	$(PYTHON) -m tqe.verification.gate_b

gate-c-verify:
	npm --prefix apps/replay-proof run build
	npm --prefix apps/replay-proof run verify
	$(PYTHON) -m tqe.verification.gate_c

m1-verify:
	$(PYTHON) -m tqe.verification.m1

m1-baseline-freeze:
	$(PYTHON) scripts/baseline/build_m1_baseline.py

test:
	$(PYTHON) -m unittest discover -s tests
