PYTHON ?= $(if $(wildcard $(CURDIR)/.venv/bin/python),$(CURDIR)/.venv/bin/python,python3.12)
PYTHONPATH := $(CURDIR)/src
export PYTHONPATH

.PHONY: setup provision-j03woh provision-corpus gate-a-build gate-b-build gate-c-build gate-a-verify gate-b-verify gate-c-verify m1-verify m1-baseline-freeze m1-1-build m1-1-gate-a-verify m1-1-gate-b-verify m1-1-gate-c-verify m1-1-gate-d-verify m1-1-gate-e-verify m1-1-gate-f-verify m1-1-gate-r1-verify m1-1-gate-r2-verify m1-1-gate-r3-verify m1-1-gate-r4-verify m1-1-gate-r5-verify m1-1-gate-s1-verify m1-1-gate-s2-verify m1-1-gate-s3-verify m1-1-gate-s3r-verify m1-1-gate-s4-verify m1-1-gate-s5-verify m1-1-gate-s6-verify m1-1-gate-s7-verify m1-1-gate-s7r-verify m1-1-verify m1-2-gate-s0-verify m1-2-gate-s1-verify m1-2-gate-s2-verify m1-2-gate-s2-sealed-verify m1-2-gate-s2i-verify m1-2-gate-s2ib-verify m1-2-gate-s2ic-verify m1-2-gate-s2id-verify workbench-alpha-install workbench-alpha-build workbench-alpha-serve workbench-alpha-verify m1-2-verify test

setup:
	python3.12 -m venv .venv
	$(CURDIR)/.venv/bin/python -m pip install --upgrade pip
	$(CURDIR)/.venv/bin/python -m pip install -e .
	npm --prefix apps/replay-proof install
	npm --prefix apps/workbench-alpha install

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

m1-1-build:
	$(PYTHON) scripts/m1_1/build_gate_a_artifacts.py

m1-1-gate-a-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_a

m1-1-gate-b-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_b

m1-1-gate-c-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_c

m1-1-gate-d-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_d

m1-1-gate-e-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_e

m1-1-gate-f-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_f

m1-1-gate-r1-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_r1

m1-1-gate-r2-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_r2

m1-1-gate-r3-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_r3

m1-1-gate-r4-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_r4

m1-1-gate-r5-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_r5

m1-1-gate-s1-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_s1

m1-1-gate-s2-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_s2

m1-1-gate-s3-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_s3

m1-1-gate-s3r-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_s3r

m1-1-gate-s4-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_s4

m1-1-gate-s5-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_s5

m1-1-gate-s6-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_s6

m1-1-gate-s7-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_s7

m1-1-gate-s7r-verify:
	$(PYTHON) -m tqe.verification.m1_1_gate_s7r

m1-1-verify:
	$(PYTHON) -m tqe.verification.m1_1

m1-2-gate-s0-verify:
	$(PYTHON) -m tqe.verification.m1_2_gate_s0

m1-2-gate-s1-verify:
	$(PYTHON) -m tqe.verification.m1_2_gate_s1

m1-2-gate-s2-verify:
	$(PYTHON) -m tqe.verification.m1_2_gate_s2

m1-2-gate-s2-sealed-verify:
	$(PYTHON) -m tqe.verification.m1_2_gate_s2_sealed

m1-2-gate-s2i-verify:
	$(PYTHON) -m tqe.verification.m1_2_gate_s2i

m1-2-gate-s2ib-verify:
	$(PYTHON) -m tqe.verification.m1_2_gate_s2ib

m1-2-gate-s2ic-verify:
	$(PYTHON) -m tqe.verification.m1_2_gate_s2ic

m1-2-gate-s2id-verify:
	$(PYTHON) -m tqe.verification.m1_2_gate_s2id

workbench-alpha-install:
	npm --prefix apps/workbench-alpha install

workbench-alpha-build:
	npm --prefix apps/workbench-alpha run build

workbench-alpha-serve: workbench-alpha-build
	$(PYTHON) -m tqe.workshop.app_service --host 127.0.0.1 --port 8765

workbench-alpha-verify:
	npm --prefix apps/workbench-alpha run test:acceptance

m1-2-verify:
	$(PYTHON) -m tqe.verification.m1_2

test:
	$(PYTHON) -m unittest discover -s tests
