PYTHON ?= $(if $(wildcard $(CURDIR)/.venv/bin/python),$(CURDIR)/.venv/bin/python,python3.12)
PYTHONPATH := $(CURDIR)/src
export PYTHONPATH

.PHONY: setup provision-j03woh provision-corpus gate-a-build gate-b-build gate-c-build gate-a-verify gate-b-verify gate-c-verify m1-verify m1-baseline-freeze m1-1-build m1-1-gate-a-verify m1-1-gate-b-verify m1-1-gate-c-verify m1-1-gate-d-verify m1-1-gate-e-verify m1-1-gate-f-verify m1-1-gate-r1-verify m1-1-gate-r2-verify m1-1-gate-r3-verify m1-1-gate-r4-verify m1-1-gate-r5-verify m1-1-gate-s1-verify m1-1-gate-s2-verify m1-1-gate-s3-verify m1-1-gate-s3r-verify m1-1-gate-s4-verify m1-1-gate-s5-verify m1-1-gate-s6-verify m1-1-gate-s7-verify m1-1-gate-s7r-verify m1-1-verify m1-2-gate-s0-verify m1-2-gate-s1-verify m1-2-gate-s2-verify m1-2-gate-s2-sealed-verify m1-2-gate-s2i-verify m1-2-gate-s2ib-verify m1-2-gate-s2ic-verify m1-2-gate-s2id-verify m1-2-gate-s2ie-verify m1-2-gate-s2if-verify n1c-verify n1d-freeze n1d-verify n1d1-verify n1g-verify n1i-verify m2a-s1a-verify m2a-s1b-verify m2a-s1c-verify scp-0-verify scp-1-verify afl-g0-verify afl-g0-gate afl-passport-verify afl-defensive-line-verify afl-relative-position-verify afl-controlled-line-break-verify afl-lane-occupancy-verify afl-support-arrival-verify afl-local-number-verify afl-line-break-support-response-verify afl-09a-verify workbench-alpha-install workbench-alpha-build workbench-alpha-serve workbench-alpha-verify cloud-alpha-bundle cloud-alpha-smoke m1-2-verify test

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

m1-2-gate-s2ie-verify:
	$(PYTHON) -m tqe.verification.m1_2_gate_s2ie

m1-2-gate-s2if-verify:
	$(PYTHON) -m tqe.verification.m1_2_gate_s2if

n1c-verify:
	$(PYTHON) -m tqe.verification.n1c

n1d-freeze:
	$(PYTHON) -m tqe.verification.n1d --freeze

n1d-verify:
	$(PYTHON) -m tqe.verification.n1d

n1d1-verify:
	$(PYTHON) -m tqe.verification.n1d1

n1g-verify:
	$(PYTHON) -m tqe.verification.n1g

n1i-verify:
	$(PYTHON) -m tqe.verification.n1i

m2a-s1a-verify:
	$(PYTHON) -m tqe.verification.m2a_s1a_controlled_pass_verify

m2a-s1b-verify:
	$(PYTHON) -m tqe.verification.m2a_s1b_pass_bypass_verify

m2a-s1c-verify:
	$(PYTHON) -m tqe.verification.m2a_s1c_high_bypass_verify

scp-0-verify:
	$(PYTHON) -m tqe.verification.scp0
	$(PYTHON) -m unittest tests.test_scp0_semantic_registry

scp-1-verify:
	$(PYTHON) -m tqe.verification.scp1
	$(PYTHON) -m unittest tests.test_scp1_semantic_compiler

afl-g0-verify:
	$(PYTHON) -m tqe.verification.afl_g0
	$(PYTHON) -m unittest tests.test_afl_g0_contract

afl-g0-gate:
	$(PYTHON) -m tqe.verification.afl_gate
	$(PYTHON) -m unittest tests.test_afl_gate

afl-passport-verify:
	$(PYTHON) -m tqe.verification.afl_passport
	$(PYTHON) -m unittest tests.test_scp0_semantic_registry

afl-defensive-line-verify:
	$(PYTHON) -m tqe.verification.afl_defensive_line
	$(PYTHON) -m unittest tests.test_defensive_line_model

afl-relative-position-verify:
	$(PYTHON) -m tqe.verification.afl_relative_position
	$(PYTHON) -m unittest tests.test_relative_position_to_line

afl-controlled-line-break-verify:
	$(PYTHON) -m tqe.verification.afl_controlled_line_break
	$(PYTHON) -m unittest tests.test_controlled_line_break

afl-lane-occupancy-verify:
	$(PYTHON) -m tqe.verification.afl_lane_occupancy
	$(PYTHON) -m unittest tests.test_lane_occupancy

afl-support-arrival-verify:
	$(PYTHON) -m tqe.verification.afl_support_arrival
	$(PYTHON) -m unittest tests.test_support_arrival

afl-local-number-verify:
	$(PYTHON) -m tqe.verification.afl_local_number
	$(PYTHON) -m unittest tests.test_local_number_relation

afl-line-break-support-response-verify:
	$(PYTHON) -m tqe.verification.afl_line_break_support_response

afl-09a-verify:
	$(PYTHON) -m tqe.verification.afl_09a
	$(PYTHON) -m unittest tests.test_afl_validation_factory

afl-one-touch-pass-chain-verify:
	$(PYTHON) -m tqe.verification.afl_one_touch_pass_chain
	$(PYTHON) -m unittest tests.test_one_touch_pass_chain

workbench-alpha-install:
	npm --prefix apps/workbench-alpha install

workbench-alpha-build:
	npm --prefix apps/workbench-alpha run build

workbench-alpha-serve: workbench-alpha-build
	$(PYTHON) -m tqe.workshop.app_service --host 127.0.0.1 --port 8765

workbench-alpha-verify:
	npm --prefix apps/workbench-alpha run test:acceptance

cloud-alpha-bundle:
	$(PYTHON) scripts/create-demo-data-bundle.py

cloud-alpha-smoke:
	$(PYTHON) scripts/cloud-smoke.py --base-url "$$BASE_URL" --token "$$DEMO_ACCESS_TOKEN"

m1-2-verify:
	$(PYTHON) -m tqe.verification.m1_2

test:
	$(PYTHON) -m unittest discover -s tests
