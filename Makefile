# Same entry points locally, inside the Docker image, and in CI.
#   make all            ERC -> exports -> 27 corners -> 2000-run Monte Carlo -> report
#   make docker-build   build the CI image locally
#   make docker-all     run `make all` inside that image
#
# PY defaults to the repo venv if present (local), else system python3 (Docker / CI).

SCH     := hardware/plant-sensor.kicad_sch
BOM     := exports/plant-sensor-bom.csv
PY      ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
JOBS    ?= $(shell nproc)
SHARDS  ?= $(shell $(PY) -c 'import yaml;print(yaml.safe_load(open("sim/montecarlo.yaml"))["shards"])')
NCORNER ?= $(shell $(PY) -c 'import yaml;c=yaml.safe_load(open("sim/corners.yaml"));print(len(c["temperature_c"])*len(c["supply_v"])*len(c["process"]))')
IMAGE   ?= plant-sensor-ci

.PHONY: all erc export corners mc report clean docker-build docker-all

all: erc export corners mc report

erc:
	mkdir -p results
	kicad-cli sch erc --severity-error --exit-code-violations --format report -o results/erc.rpt $(SCH)

export:
	mkdir -p exports
	kicad-cli sch export netlist -o exports/plant-sensor.net $(SCH)
	kicad-cli sch export bom -o $(BOM) \
	  --fields 'Reference,Value,Footprint,Tolerance,TempCo,MPN,$${QUANTITY}' \
	  --labels 'Reference,Value,Footprint,Tolerance,TempCo,MPN,Qty' \
	  --group-by 'Value,Footprint,Tolerance,TempCo,MPN' --ref-range-delimiter '' \
	  --string-delimiter '"' $(SCH)
	kicad-cli sch export pdf -o exports/plant-sensor.pdf $(SCH)

# Serial on purpose: this is the "before" number that a CI matrix is compared against.
corners: $(BOM)
	rm -rf results/corners
	for i in $$(seq 0 $$(($(NCORNER) - 1))); do \
	  $(PY) scripts/run_sim.py --bom $(BOM) --corner-index $$i --outdir results/corners > /dev/null || exit 1; \
	done
	$(PY) scripts/check_specs.py results/corners > results/corners.md

mc: $(BOM)
	rm -rf results/mc
	for k in $$(seq 0 $$(($(SHARDS) - 1))); do \
	  $(PY) scripts/mc_shard.py --shard $$k --bom $(BOM) --outdir results/mc --jobs $(JOBS) || exit 1; \
	done

report:
	$(PY) scripts/report.py --corners results/corners --mc results/mc --out results/report $(if $(GITHUB_STEP_SUMMARY),--summary $(GITHUB_STEP_SUMMARY))

$(BOM):
	$(MAKE) export

clean:
	rm -rf results exports

docker-build:
	docker build -f docker/Dockerfile -t $(IMAGE) .

docker-all:
	docker run --rm --user "$$(id -u):$$(id -g)" -v "$$PWD":/work -w /work $(IMAGE) make all PY=python3
