PYTHON ?= $(if $(wildcard $(CURDIR)/.venv/bin/python),$(CURDIR)/.venv/bin/python,python3.12)
PYTHONPATH := $(CURDIR)/src
export PYTHONPATH

.PHONY: setup provision-j03woh provision-corpus gate-a-build gate-b-build gate-c-build gate-a-verify gate-b-verify gate-c-verify m1-verify m1-baseline-freeze m1-1-build m1-1-gate-a-verify m1-1-gate-b-verify m1-1-gate-c-verify m1-1-gate-d-verify m1-1-gate-e-verify m1-1-gate-f-verify m1-1-gate-r1-verify m1-1-gate-r2-verify m1-1-gate-r3-verify m1-1-gate-r4-verify m1-1-gate-r5-verify m1-1-gate-s1-verify m1-1-gate-s2-verify m1-1-gate-s3-verify m1-1-gate-s3r-verify m1-1-gate-s4-verify m1-1-gate-s5-verify m1-1-gate-s6-verify m1-1-gate-s7-verify m1-1-gate-s7r-verify m1-1-verify m1-2-gate-s0-verify m1-2-gate-s1-verify m1-2-gate-s2-verify m1-2-gate-s2-sealed-verify m1-2-gate-s2i-verify m1-2-gate-s2ib-verify m1-2-gate-s2ic-verify m1-2-gate-s2id-verify m1-2-gate-s2ie-verify m1-2-gate-s2if-verify n1c-verify n1d-freeze n1d-verify n1d1-verify n1g-verify n1i-verify m2a-s1a-verify m2a-s1b-verify m2a-s1c-verify scp-0-verify scp-1-verify afl-g0-verify afl-g0-gate afl-passport-verify afl-defensive-line-verify afl-relative-position-verify afl-controlled-line-break-verify afl-lane-occupancy-verify afl-support-arrival-verify afl-local-number-verify afl-line-break-support-response-verify afl-09a-verify afl-acceleration-verify afl-substrate-q4-verify workbench-alpha-install workbench-alpha-build workbench-alpha-serve workbench-alpha-verify cloud-alpha-bundle cloud-alpha-smoke m1-2-verify test

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

afl-runtime-reuse-verify:
	$(PYTHON) -m tqe.verification.afl_runtime_reuse

afl-substrate-q3-verify:
	$(PYTHON) -m tqe.verification.afl_substrate_q3

afl-substrate-q4-verify:
	$(PYTHON) -m tqe.verification.afl_substrate_q4

afl-substrate-q5-verify:
	$(PYTHON) -m tqe.verification.afl_substrate_q5

afl-substrate-q6-verify:
	$(PYTHON) -m tqe.verification.afl_substrate_q6

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

.PHONY: afl-time-to-arrival-verify
afl-time-to-arrival-verify:
	$(PYTHON) -m tqe.verification.afl_time_to_arrival

.PHONY: afl-carry-episode-verify
afl-carry-episode-verify:
	$(PYTHON) -m tqe.verification.afl_carry_episode

.PHONY: afl-acceleration-verify
afl-acceleration-verify:
	$(PYTHON) -m tqe.verification.afl_acceleration

.PHONY: afl-substrate-q2-verify
afl-substrate-q2-verify:
	$(PYTHON) -m tqe.verification.afl_substrate_q2

test:
	$(PYTHON) -m unittest discover -s tests

.PHONY: coverage-map
coverage-map:
	$(PYTHON) scripts/coverage_map/aggregate.py

.PHONY: compiler-reachability
compiler-reachability:
	$(PYTHON) scripts/coverage_map/compiler_reachability.py
	$(PYTHON) scripts/coverage_map/aggregate.py

.PHONY: compiler-search-reachability
compiler-search-reachability:
	$(PYTHON) scripts/coverage_map/compiler_search_reachability.py
	$(PYTHON) scripts/coverage_map/aggregate.py

.PHONY: compiler-search-contract-projection
compiler-search-contract-projection:
	$(PYTHON) scripts/coverage_map/project_search_contracts.py

.PHONY: compiler-bare-atlas-contract-sample
compiler-bare-atlas-contract-sample:
	$(PYTHON) scripts/coverage_map/bare_atlas_contract_sample.py prepare
	TQE_SEARCH_TARGETS=generated/compiler-search-bare-atlas/bare-atlas-targets.v0.json \
	TQE_SEARCH_LEDGER=generated/compiler-search-bare-atlas/bare-atlas-coverage-ledger.json \
	TQE_SEARCH_OUT_DIR=generated/compiler-search-bare-atlas/search-run \
	TQE_SEARCH_REPORT=artifacts/autonomous/compiler-bare-atlas-search-report.json \
	TQE_SEARCH_UPDATE_LEDGER=0 \
	$(PYTHON) scripts/coverage_map/compiler_search_reachability.py
	$(PYTHON) scripts/coverage_map/bare_atlas_contract_sample.py assess

.PHONY: compiler-search-cache-equivalence
compiler-search-cache-equivalence:
	$(PYTHON) scripts/coverage_map/bare_atlas_contract_sample.py prepare
	TQE_SEARCH_SHARED_NODE_CACHE=0 \
	TQE_SEARCH_TARGETS=generated/compiler-search-bare-atlas/bare-atlas-targets.v0.json \
	TQE_SEARCH_LEDGER=generated/compiler-search-bare-atlas/bare-atlas-coverage-ledger.json \
	TQE_SEARCH_OUT_DIR=generated/compiler-search-bare-atlas/search-run-no-shared \
	TQE_SEARCH_REPORT=artifacts/autonomous/compiler-bare-atlas-search-no-shared-report.json \
	TQE_SEARCH_UPDATE_LEDGER=0 \
	$(PYTHON) scripts/coverage_map/compiler_search_reachability.py
	TQE_SEARCH_SHARED_NODE_CACHE=1 \
	TQE_SEARCH_TARGETS=generated/compiler-search-bare-atlas/bare-atlas-targets.v0.json \
	TQE_SEARCH_LEDGER=generated/compiler-search-bare-atlas/bare-atlas-coverage-ledger.json \
	TQE_SEARCH_OUT_DIR=generated/compiler-search-bare-atlas/search-run-shared \
	TQE_SEARCH_REPORT=artifacts/autonomous/compiler-bare-atlas-search-shared-report.json \
	TQE_SEARCH_UPDATE_LEDGER=0 \
	$(PYTHON) scripts/coverage_map/compiler_search_reachability.py
	$(PYTHON) scripts/coverage_map/compare_search_cache_equivalence.py

.PHONY: compiler-search-persistent-cache-equivalence
compiler-search-persistent-cache-equivalence:
	$(PYTHON) scripts/coverage_map/bare_atlas_contract_sample.py prepare
	rm -rf artifacts/autonomous/compiler-search-node-cache/persistent-equivalence
	TQE_SEARCH_SHARED_NODE_CACHE=0 \
	TQE_SEARCH_TARGETS=generated/compiler-search-bare-atlas/bare-atlas-targets.v0.json \
	TQE_SEARCH_LEDGER=generated/compiler-search-bare-atlas/bare-atlas-coverage-ledger.json \
	TQE_SEARCH_OUT_DIR=generated/compiler-search-bare-atlas/search-run-persistent-baseline \
	TQE_SEARCH_REPORT=artifacts/autonomous/compiler-bare-atlas-search-persistent-baseline-report.json \
	TQE_SEARCH_UPDATE_LEDGER=0 \
	$(PYTHON) scripts/coverage_map/compiler_search_reachability.py
	TQE_SEARCH_SHARED_NODE_CACHE=1 \
	TQE_SEARCH_PERSISTENT_NODE_CACHE=1 \
	TQE_SEARCH_NODE_CACHE_NAMESPACE=persistent-equivalence \
	TQE_SEARCH_NODE_CACHE_ROOT=artifacts/autonomous/compiler-search-node-cache \
	TQE_SEARCH_TARGETS=generated/compiler-search-bare-atlas/bare-atlas-targets.v0.json \
	TQE_SEARCH_LEDGER=generated/compiler-search-bare-atlas/bare-atlas-coverage-ledger.json \
	TQE_SEARCH_OUT_DIR=generated/compiler-search-bare-atlas/search-run-persistent-cold \
	TQE_SEARCH_REPORT=artifacts/autonomous/compiler-bare-atlas-search-persistent-cold-report.json \
	TQE_SEARCH_UPDATE_LEDGER=0 \
	$(PYTHON) scripts/coverage_map/compiler_search_reachability.py
	TQE_SEARCH_SHARED_NODE_CACHE=1 \
	TQE_SEARCH_PERSISTENT_NODE_CACHE=1 \
	TQE_SEARCH_NODE_CACHE_NAMESPACE=persistent-equivalence \
	TQE_SEARCH_NODE_CACHE_ROOT=artifacts/autonomous/compiler-search-node-cache \
	TQE_SEARCH_TARGETS=generated/compiler-search-bare-atlas/bare-atlas-targets.v0.json \
	TQE_SEARCH_LEDGER=generated/compiler-search-bare-atlas/bare-atlas-coverage-ledger.json \
	TQE_SEARCH_OUT_DIR=generated/compiler-search-bare-atlas/search-run-persistent-warm \
	TQE_SEARCH_REPORT=artifacts/autonomous/compiler-bare-atlas-search-persistent-warm-report.json \
	TQE_SEARCH_UPDATE_LEDGER=0 \
	$(PYTHON) scripts/coverage_map/compiler_search_reachability.py
	TQE_SEARCH_BASELINE_ROW_LEDGER=generated/compiler-search-bare-atlas/search-run-persistent-baseline/row-ledger.json \
	TQE_SEARCH_CACHED_ROW_LEDGER=generated/compiler-search-bare-atlas/search-run-persistent-warm/row-ledger.json \
	TQE_SEARCH_CACHED_REPORT=artifacts/autonomous/compiler-bare-atlas-search-persistent-warm-report.json \
	TQE_SEARCH_CACHE_EQUIVALENCE_REPORT=artifacts/autonomous/compiler-search-persistent-cache-equivalence-report.json \
	TQE_REQUIRE_PERSISTENT_DISK_HITS=1 \
	$(PYTHON) scripts/coverage_map/compare_search_cache_equivalence.py

.PHONY: compiler-search-parallel-cache-equivalence
compiler-search-parallel-cache-equivalence:
	$(PYTHON) scripts/coverage_map/bare_atlas_contract_sample.py prepare
	rm -rf artifacts/autonomous/compiler-search-node-cache/parallel-equivalence
	TQE_SEARCH_WORKERS=1 \
	TQE_SEARCH_SHARED_NODE_CACHE=0 \
	TQE_SEARCH_TARGETS=generated/compiler-search-bare-atlas/bare-atlas-targets.v0.json \
	TQE_SEARCH_LEDGER=generated/compiler-search-bare-atlas/bare-atlas-coverage-ledger.json \
	TQE_SEARCH_OUT_DIR=generated/compiler-search-bare-atlas/search-run-parallel-baseline \
	TQE_SEARCH_REPORT=artifacts/autonomous/compiler-bare-atlas-search-parallel-baseline-report.json \
	TQE_SEARCH_UPDATE_LEDGER=0 \
	$(PYTHON) scripts/coverage_map/compiler_search_reachability.py
	TQE_SEARCH_WORKERS=4 \
	TQE_SEARCH_SHARED_NODE_CACHE=1 \
	TQE_SEARCH_PERSISTENT_NODE_CACHE=1 \
	TQE_SEARCH_NODE_CACHE_NAMESPACE=parallel-equivalence \
	TQE_SEARCH_NODE_CACHE_ROOT=artifacts/autonomous/compiler-search-node-cache \
	TQE_SEARCH_TARGETS=generated/compiler-search-bare-atlas/bare-atlas-targets.v0.json \
	TQE_SEARCH_LEDGER=generated/compiler-search-bare-atlas/bare-atlas-coverage-ledger.json \
	TQE_SEARCH_OUT_DIR=generated/compiler-search-bare-atlas/search-run-parallel-cold \
	TQE_SEARCH_REPORT=artifacts/autonomous/compiler-bare-atlas-search-parallel-cold-report.json \
	TQE_SEARCH_UPDATE_LEDGER=0 \
	$(PYTHON) scripts/coverage_map/compiler_search_reachability.py
	TQE_SEARCH_WORKERS=4 \
	TQE_SEARCH_SHARED_NODE_CACHE=1 \
	TQE_SEARCH_PERSISTENT_NODE_CACHE=1 \
	TQE_SEARCH_NODE_CACHE_NAMESPACE=parallel-equivalence \
	TQE_SEARCH_NODE_CACHE_ROOT=artifacts/autonomous/compiler-search-node-cache \
	TQE_SEARCH_TARGETS=generated/compiler-search-bare-atlas/bare-atlas-targets.v0.json \
	TQE_SEARCH_LEDGER=generated/compiler-search-bare-atlas/bare-atlas-coverage-ledger.json \
	TQE_SEARCH_OUT_DIR=generated/compiler-search-bare-atlas/search-run-parallel-warm \
	TQE_SEARCH_REPORT=artifacts/autonomous/compiler-bare-atlas-search-parallel-warm-report.json \
	TQE_SEARCH_UPDATE_LEDGER=0 \
	$(PYTHON) scripts/coverage_map/compiler_search_reachability.py
	TQE_SEARCH_BASELINE_ROW_LEDGER=generated/compiler-search-bare-atlas/search-run-parallel-baseline/row-ledger.json \
	TQE_SEARCH_CACHED_ROW_LEDGER=generated/compiler-search-bare-atlas/search-run-parallel-warm/row-ledger.json \
	TQE_SEARCH_CACHED_REPORT=artifacts/autonomous/compiler-bare-atlas-search-parallel-warm-report.json \
	TQE_SEARCH_CACHE_EQUIVALENCE_REPORT=artifacts/autonomous/compiler-search-parallel-cache-equivalence-report.json \
	TQE_REQUIRE_PERSISTENT_DISK_HITS=1 \
	$(PYTHON) scripts/coverage_map/compare_search_cache_equivalence.py

.PHONY: compiler-search-atlas-scale-sample
compiler-search-atlas-scale-sample:
	$(PYTHON) scripts/coverage_map/atlas_scale_contract_sample.py prepare
	TQE_SEARCH_WORKERS=4 \
	TQE_SEARCH_SHARED_NODE_CACHE=1 \
	TQE_SEARCH_PERSISTENT_NODE_CACHE=1 \
	TQE_SEARCH_TARGETS=generated/compiler-search-atlas-scale-sample/atlas-scale-targets.v0.json \
	TQE_SEARCH_LEDGER=generated/compiler-search-atlas-scale-sample/atlas-scale-coverage-ledger.json \
	TQE_SEARCH_OUT_DIR=generated/compiler-search-atlas-scale-sample/search-run \
	TQE_SEARCH_REPORT=artifacts/autonomous/compiler-atlas-scale-search-report.json \
	TQE_SEARCH_UPDATE_LEDGER=0 \
	$(PYTHON) scripts/coverage_map/compiler_search_reachability.py
	$(PYTHON) scripts/coverage_map/atlas_scale_contract_sample.py assess

.PHONY: compiler-search-supported-broad-draw
compiler-search-supported-broad-draw:
	TQE_ATLAS_SCALE_SAMPLE_POLICY=supported_broad_draw_with_known_good_controls_v0 \
	TQE_ATLAS_SCALE_POSITIVE_CONCEPTS=48 \
	TQE_ATLAS_SCALE_POSITIVES_PER_TEMPLATE=4 \
	TQE_ATLAS_SCALE_INCLUDE_KNOWN_GOOD_CONTROLS=1 \
	TQE_ATLAS_SCALE_OUT_DIR=generated/compiler-search-supported-broad-draw \
	TQE_ATLAS_SCALE_TARGETS_FILENAME=supported-broad-draw-targets.v0.json \
	TQE_ATLAS_SCALE_LEDGER_FILENAME=supported-broad-draw-coverage-ledger.json \
	TQE_ATLAS_SCALE_PREP_REPORT=artifacts/autonomous/compiler-supported-broad-draw-prep-report.json \
	TQE_ATLAS_SCALE_ASSESS_REPORT=artifacts/autonomous/compiler-supported-broad-draw-assessment-report.json \
	$(PYTHON) scripts/coverage_map/atlas_scale_contract_sample.py prepare
	TQE_SEARCH_WORKERS=4 \
	TQE_SEARCH_SHARED_NODE_CACHE=1 \
	TQE_SEARCH_PERSISTENT_NODE_CACHE=1 \
	TQE_SEARCH_TARGETS=generated/compiler-search-supported-broad-draw/supported-broad-draw-targets.v0.json \
	TQE_SEARCH_LEDGER=generated/compiler-search-supported-broad-draw/supported-broad-draw-coverage-ledger.json \
	TQE_SEARCH_OUT_DIR=generated/compiler-search-supported-broad-draw/search-run \
	TQE_SEARCH_REPORT=artifacts/autonomous/compiler-supported-broad-draw-search-report.json \
	TQE_SEARCH_UPDATE_LEDGER=0 \
	$(PYTHON) scripts/coverage_map/compiler_search_reachability.py
	TQE_ATLAS_SCALE_SAMPLE_POLICY=supported_broad_draw_with_known_good_controls_v0 \
	TQE_ATLAS_SCALE_INCLUDE_KNOWN_GOOD_CONTROLS=1 \
	TQE_ATLAS_SCALE_OUT_DIR=generated/compiler-search-supported-broad-draw \
	TQE_ATLAS_SCALE_TARGETS_FILENAME=supported-broad-draw-targets.v0.json \
	TQE_ATLAS_SCALE_LEDGER_FILENAME=supported-broad-draw-coverage-ledger.json \
	TQE_ATLAS_SCALE_PREP_REPORT=artifacts/autonomous/compiler-supported-broad-draw-prep-report.json \
	TQE_ATLAS_SCALE_ASSESS_REPORT=artifacts/autonomous/compiler-supported-broad-draw-assessment-report.json \
	$(PYTHON) scripts/coverage_map/atlas_scale_contract_sample.py assess

.PHONY: compiler-search-supported-blind-draw
compiler-search-supported-blind-draw:
	TQE_ATLAS_SCALE_SAMPLE_POLICY=supported_blind_draw_with_calibration_v0 \
	TQE_ATLAS_SCALE_BLIND_SUPPORTED_DRAW=1 \
	TQE_ATLAS_SCALE_BLIND_CONCEPTS=64 \
	TQE_ATLAS_SCALE_INCLUDE_KNOWN_GOOD_CONTROLS=1 \
	TQE_ATLAS_SCALE_OUT_DIR=generated/compiler-search-supported-blind-draw \
	TQE_ATLAS_SCALE_TARGETS_FILENAME=supported-blind-draw-targets.v0.json \
	TQE_ATLAS_SCALE_LEDGER_FILENAME=supported-blind-draw-coverage-ledger.json \
	TQE_ATLAS_SCALE_PREP_REPORT=artifacts/autonomous/compiler-supported-blind-draw-prep-report.json \
	TQE_ATLAS_SCALE_ASSESS_REPORT=artifacts/autonomous/compiler-supported-blind-draw-assessment-report.json \
	$(PYTHON) scripts/coverage_map/atlas_scale_contract_sample.py prepare
	TQE_SEARCH_WORKERS=4 \
	TQE_SEARCH_SHARED_NODE_CACHE=1 \
	TQE_SEARCH_PERSISTENT_NODE_CACHE=1 \
	TQE_SEARCH_TARGETS=generated/compiler-search-supported-blind-draw/supported-blind-draw-targets.v0.json \
	TQE_SEARCH_LEDGER=generated/compiler-search-supported-blind-draw/supported-blind-draw-coverage-ledger.json \
	TQE_SEARCH_OUT_DIR=generated/compiler-search-supported-blind-draw/search-run \
	TQE_SEARCH_REPORT=artifacts/autonomous/compiler-supported-blind-draw-search-report.json \
	TQE_SEARCH_UPDATE_LEDGER=0 \
	$(PYTHON) scripts/coverage_map/compiler_search_reachability.py
	TQE_ATLAS_SCALE_SAMPLE_POLICY=supported_blind_draw_with_calibration_v0 \
	TQE_ATLAS_SCALE_BLIND_SUPPORTED_DRAW=1 \
	TQE_ATLAS_SCALE_BLIND_CONCEPTS=64 \
	TQE_ATLAS_SCALE_INCLUDE_KNOWN_GOOD_CONTROLS=1 \
	TQE_ATLAS_SCALE_OUT_DIR=generated/compiler-search-supported-blind-draw \
	TQE_ATLAS_SCALE_TARGETS_FILENAME=supported-blind-draw-targets.v0.json \
	TQE_ATLAS_SCALE_LEDGER_FILENAME=supported-blind-draw-coverage-ledger.json \
	TQE_ATLAS_SCALE_PREP_REPORT=artifacts/autonomous/compiler-supported-blind-draw-prep-report.json \
	TQE_ATLAS_SCALE_ASSESS_REPORT=artifacts/autonomous/compiler-supported-blind-draw-assessment-report.json \
	$(PYTHON) scripts/coverage_map/atlas_scale_contract_sample.py assess

.PHONY: compiler-search-frontier-draw
compiler-search-frontier-draw:
	TQE_ATLAS_SCALE_SAMPLE_POLICY=frontier_partial_gap_draw_with_controls_v0 \
	TQE_ATLAS_SCALE_FRONTIER_PARTIAL_DRAW=1 \
	TQE_ATLAS_SCALE_FRONTIER_CONCEPTS=48 \
	TQE_ATLAS_SCALE_INCLUDE_KNOWN_GOOD_CONTROLS=1 \
	TQE_ATLAS_SCALE_OUT_DIR=generated/compiler-search-frontier-draw \
	TQE_ATLAS_SCALE_TARGETS_FILENAME=frontier-draw-targets.v0.json \
	TQE_ATLAS_SCALE_LEDGER_FILENAME=frontier-draw-coverage-ledger.json \
	TQE_ATLAS_SCALE_PREP_REPORT=artifacts/autonomous/compiler-frontier-draw-prep-report.json \
	TQE_ATLAS_SCALE_ASSESS_REPORT=artifacts/autonomous/compiler-frontier-draw-assessment-report.json \
	$(PYTHON) scripts/coverage_map/atlas_scale_contract_sample.py prepare
	TQE_SEARCH_WORKERS=4 \
	TQE_SEARCH_SHARED_NODE_CACHE=1 \
	TQE_SEARCH_PERSISTENT_NODE_CACHE=1 \
	TQE_SEARCH_TARGETS=generated/compiler-search-frontier-draw/frontier-draw-targets.v0.json \
	TQE_SEARCH_LEDGER=generated/compiler-search-frontier-draw/frontier-draw-coverage-ledger.json \
	TQE_SEARCH_OUT_DIR=generated/compiler-search-frontier-draw/search-run \
	TQE_SEARCH_REPORT=artifacts/autonomous/compiler-frontier-draw-search-report.json \
	TQE_SEARCH_UPDATE_LEDGER=0 \
	$(PYTHON) scripts/coverage_map/compiler_search_reachability.py
	TQE_ATLAS_SCALE_SAMPLE_POLICY=frontier_partial_gap_draw_with_controls_v0 \
	TQE_ATLAS_SCALE_FRONTIER_PARTIAL_DRAW=1 \
	TQE_ATLAS_SCALE_FRONTIER_CONCEPTS=48 \
	TQE_ATLAS_SCALE_INCLUDE_KNOWN_GOOD_CONTROLS=1 \
	TQE_ATLAS_SCALE_OUT_DIR=generated/compiler-search-frontier-draw \
	TQE_ATLAS_SCALE_TARGETS_FILENAME=frontier-draw-targets.v0.json \
	TQE_ATLAS_SCALE_LEDGER_FILENAME=frontier-draw-coverage-ledger.json \
	TQE_ATLAS_SCALE_PREP_REPORT=artifacts/autonomous/compiler-frontier-draw-prep-report.json \
	TQE_ATLAS_SCALE_ASSESS_REPORT=artifacts/autonomous/compiler-frontier-draw-assessment-report.json \
	$(PYTHON) scripts/coverage_map/atlas_scale_contract_sample.py assess

.PHONY: scl0-verify scl1-verify
scl0-verify:
	$(PYTHON) scripts/coverage_map/semantic_contract_scl0.py prepare
	TQE_SEARCH_WORKERS=4 \
	TQE_SEARCH_SHARED_NODE_CACHE=1 \
	TQE_SEARCH_PERSISTENT_NODE_CACHE=1 \
	TQE_SEARCH_TARGETS=generated/semantic-contract-scl0/scl0-search-targets.v0.json \
	TQE_SEARCH_LEDGER=generated/semantic-contract-scl0/scl0-coverage-ledger.json \
	TQE_SEARCH_OUT_DIR=generated/semantic-contract-scl0/search-run \
	TQE_SEARCH_REPORT=artifacts/autonomous/scl0-meaning-contract-search-report.json \
	TQE_SEARCH_UPDATE_LEDGER=0 \
	$(PYTHON) scripts/coverage_map/compiler_search_reachability.py
	$(PYTHON) scripts/coverage_map/semantic_contract_scl0.py assess

scl1-verify: scl0-verify
