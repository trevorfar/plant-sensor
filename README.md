# Plant Sensor CI: GitHub Actions vs Namespace

## Goal

Take an existing project (my Capstone circuit, see [References](#references)) and use GitHub Actions / Namespace to:

- Perform ERC (Electrical Rule Check) validation
- Export netlist / BOM
- Simulate 27 corners + 2000-run Monte Carlo (ngspice)
- Export sim results

The same pipeline runs on both platforms on every push. Only the runner changes:

- [`ci-baseline.yml`](.github/workflows/ci-baseline.yml): GitHub-hosted runners (`ubuntu-latest`)
- [`ci-namespace.yml`](.github/workflows/ci-namespace.yml): Namespace runners (`namespace-profile-plant-sensor`)

Each pipeline is explained in [Workflow explanation](#workflow-explanation). Spoiler: Namespace won..

## Results

Three comparisons were run.

### 1. Unoptimized

| Stat | GitHub | Namespace | Namespace vs GitHub |
|---|---:|---:|---:|
| Run ID | 42330906243 | 42330906329 | |
| Commit | `bfe4377` | `bfe4377` | |
| Status | success | success | |
| **Total wall-clock** (first job start → last job end) | 375 s (6.2 min) | 147 s (2.5 min) | **2.55× faster** |
| Total queue before first job | 2 s | 8 s | 4.00× slower |
| Total runner time (sum of all jobs) | 371 s (6.2 min) | 145 s (2.4 min) | 2.56× faster |
| Total jobs | 3 | 3 | |
| Job `erc` wall | 31 s | 8 s | 3.88× faster |
| Job `export` wall | 29 s | 23 s | 1.26× faster |
| Job `sim` wall | 311 s (5.2 min) | 114 s | 2.73× faster |

### 2. Optimized: prebuilt Docker image, cold cache

| Stat | GitHub | Namespace | Namespace vs GitHub |
|---|---:|---:|---:|
| Run ID | 42402137024 | 42402137008 | |
| Commit | `2ada952` | `2ada952` | |
| Status | success | success | |
| **Total wall-clock** (first job start → last job end) | 538 s (9.0 min) | 181 s (3.0 min) | **2.97× faster** |
| Total queue before first job | 2 s | 8 s | 4.00× slower |
| Total runner time (sum of all jobs) | 533 s (8.9 min) | 178 s (3.0 min) | 2.99× faster |
| Total jobs | 4 | 4 | |
| Job `image` wall | 146 s (2.4 min) | 61 s | 2.39× faster |
| Job `erc` wall | 33 s | 18 s | 1.83× faster |
| Job `export` wall | 43 s | 17 s | 2.53× faster |
| Job `sim` wall | 311 s (5.2 min) | 82 s | 3.79× faster |

### 3. Optimized: prebuilt Docker image, warm cache

| Stat | GitHub | Namespace | Namespace vs GitHub |
|---|---:|---:|---:|
| Run ID | 42403222071 | 42403222193 | |
| Commit | `2305f19` | `2305f19` | |
| Status | success | success | |
| **Total wall-clock** (first job start → last job end) | 338 s (5.6 min) | 111 s (1.9 min) | **3.05× faster** |
| Total queue before first job | 3 s | 2 s | 1.50× faster |
| Total runner time (sum of all jobs) | 332 s (5.5 min) | 108 s (1.8 min) | 3.07× faster |
| Total jobs | 4 | 4 | |
| Job `image` wall | 17 s | 13 s | 1.31× faster |
| Job `erc` wall | 35 s | 7 s | 5.00× faster |
| Job `export` wall | 43 s | 9 s | 4.78× faster |
| Job `sim` wall | 237 s (4.0 min) | 79 s | 3.00× faster |

### Machine specs

| Spec | GitHub | Namespace |
|---|---|---|
| Container OS | Debian GNU/Linux 12 (bookworm) | Debian GNU/Linux 12 (bookworm) |
| vCPUs | 4 | 4 |
| Model name | AMD EPYC 9V45 96-Core Processor | AMD EPYC |
| Thread(s) per core | 2 | 2 |
| Core(s) per socket | 2 | 2 |
| Socket(s) | 1 | 1 |
| L3 cache | 32 MiB | 32 MiB |
| Memory | 15 GiB | 7.8 GiB |

In addition, Namespace was given a 50 GB cache volume.

The OS row shows the Docker image the jobs run in (see [1.0 Docker](#10-docker-image)), not the host. Both hosts run Ubuntu 24.04. The CPU, core and memory rows are the real host hardware, because a container shares the host's CPU and kernel.

**Notes:**
I ran this on the free GitHub Actions resources for public repos. In hindsight, I should have run the Namespace comparisons with 16 GB of RAM to match, although on closer comparison it didn't look like RAM was a limiting factor. The simulator is CPU-bound, so increasing the vCPU count would have given a much larger performance increase.

I'm actually kind of confused why the simulation time was improved so much. From the specs, it seems to be very similar hardware. My only guess is GitHub performs some kind of throttling that Namespace does not? Overall, namespace performed much more consistently, with the understanding my sampling size was pretty small.

## Workflow explanation
Both workflows run the same four jobs in a chain. Each job starts on a fresh machine and waits for the previous one (`needs:`):

### 1.0 Docker image

Create a Docker image **per workflow**, thus a unique one for Namespace (`plant-sensor-ci`) and a unique one for GitHub (`plant-sensor-ci-gh`), so the two platforms never share an image or cache. The tag is a hash of the Dockerfile (`hashFiles('docker/Dockerfile')`), so the image is only rebuilt when the Dockerfile changes.

The image ([`docker/Dockerfile`](docker/Dockerfile)) builds off the official KiCad 9.0.9 image ([`kicad/kicad`](https://hub.docker.com/r/kicad/kicad)), which is based on Debian bookworm. It performs all the `apt-get` calls required for our testing:

- **bookworm-backports:** Debian's stable releases freeze package versions, so bookworm's own ngspice is version 39, which is too old. The backports repository provides newer packages built for the same release, so we add it to get ngspice 46.
- **ngspice:** the SPICE circuit simulator (installed from backports)
- **python3 + libs:** numpy, scipy, pandas, PyYAML and matplotlib for the sim scripts and report, plus `make`, `git` and `curl`

It then sets up `VENDOR_MODELS=/opt/vendor-models` as an environment variable for vendor SPICE models. These can't be redistributed, so they aren't committed. The directory is currently empty because the sims use generic models ([`sim/models/generic.lib`](sim/models/generic.lib)). While not ideal, I didn't want to run into any copywright issues thus played it safe. 

Finally, it sets `HOME` to a world-writable directory. `kicad-cli` writes config under `$HOME`, and CI runs the container as the runner's uid, so the default `HOME` would't have been writable.

Putting everything into an image removes the repeated `apt-get install` calls that every job paid for in the [unoptimized run](#1-unoptimized).

**Namespace vs GitHub here:** both jobs log in to the GitHub Container Registry (GHCR) using the `GITHUB_TOKEN` that GitHub gives every run, so no secret is needed. Both then build and push with `docker/build-push-action`. The difference is where the build runs and where its cache lives:

| | GitHub | Namespace |
|---|---|---|
| Builder setup | `docker/setup-buildx-action` creates a builder on the runner itself | `namespacelabs/nscloud-setup-buildx-action` points `docker buildx` at Namespace's remote builder |
| Layer cache | GitHub Actions cache (`cache-from/cache-to: type=gha`), downloaded on each run | stays on the remote builder between runs |
| Image pull in later jobs | every job downloads the full image from GHCR | served from the cache volume |

The last row explains most of the warm-cache difference: on GitHub, the Initialize containers step took a mean of 31s/job while Namespace was in the 1-2s range. This is the benefit of their Ephemeral caching.
### 2.0 ERC

Once our image is created, we pass it down to this job (`container: image: ${{ needs.image.outputs.image }}`). We then clone the repo and run our first make command, [`make erc`](Makefile#L20). This step creates a `results/` dir and runs the `kicad-cli` command:

```bash```
kicad-cli sch erc --severity-error --exit-code-violations --format report -o results/erc.rpt hardware/plant-sensor.kicad_sch

--exit-code-violations makes the command exit with an error if any violation is found, which fails the job and stops the pipeline. The report is uploaded as the erc-report artifact either way.

An ERC (Electrical Rule Check) is an automated verification step in Electronic Design Automation (EDA) software used for integrated circuits or printed circuit boards (PCBs). It checks the schematic’s connections for electrical mistakes, such as unconnected pins, two outputs driving the same net, or power pins with no source. (From google)

3.0 Export
Again, we pass the image down. We then run our second make command, make export. This step creates an exports/ dir and exports:

exports/plant-sensor.net: the schematic’s netlist (every component and what it connects to)
exports/plant-sensor-bom.csv: the BOM (bill of materials), including the Tolerance and TempCo fields the simulations need
exports/plant-sensor.pdf: a PDF of the schematic
We then save exports/ as an artifact to feed into our next step.

4.0 Simulation
Now that we have prepared our inputs (BOM, schematic, netlist) and passed all ERC checks, we can simulate our circuit with ngspice. The job downloads the exports artifact, and the scripts read the BOM and write each component’s value into the four testbenches in sim/testbenches/. This makes the schematic the single source of truth.

The simulation runs in two parts, and each result is checked against the pass/fail limits in specs/specs.yaml.

1) 27 corners (make corners)
   A corner represents a different setup of inputs to the circuit. The 27 corners come from sim/corners.yaml: 3 temperatures (−10, 25, 50 °C) × 3 supply voltages (4.5, 5.0, 5.5 V) × 3 component tolerances (every R/C at min / typical / max). This tests the worst-case combinations.
2) 2000-run Monte Carlo (make mc):
   A Monte Carlo simulation is a computational technique that uses repeated random sampling to estimate the probability of different outcomes in a system that is difficult to predict due to random variables (Google again). Here, each run gives every component a random value within its tolerance (Gaussian, tolerance = 3σ), configured in sim/montecarlo.yaml. The 2000 runs are split into 20 shards of 100, and each shard uses every core on the runner. Run i uses seed 42 + i, so any single run can be reproduced locally. This step is the most CPU-intensive, which is why is shows the largest gap between the two flows.

5.0 Save results
make report collects the corner and Monte Carlo results into results/report/report.md. The report includes pass/fail tables, yield (the percentage of Monte Carlo runs that met every spec), histograms for each metric, and Monte Carlo timing. The same summary is written to the GitHub run page ($GITHUB_STEP_SUMMARY). The whole results/ dir is uploaded as the sim-results artifact. The report step uses if: always(), so it still runs if a spec fails.

Hardware (KiCad schematic)
The hardware/ dir holds the KiCad project for the plant electrophysiology sensor front end described in the Blueprint report. A KiCad schematic can be split into hierarchical sheets. The top-level file, plant-sensor.kicad_sch, contains five sheets:
| Sheet | File | What it does |
| --- | --- | --- |
| Power	| power.kicad_sch| +/- 5V analog rails and the 3.3 V digital supply|
| Electrodes | electrodes.kicad_sch | Connections to the electrodes on the leaf |
| PassiveAFE | passive_afe.kicad_sch | Passive recording path (INA121, filter, ADC) |
| EIS | eis.kicad_sch | Impedance spectroscopy (AD5933, Howland VCSS, opamps) |
| Digital | digital.kicad_sch | AD7124 ADC and digital interface |

The board has two modes: passive recording of the plant’s electrical signals, and EIS (electrical impedance spectroscopy), which injects a small current and measures the response. The other files are:

plant-sensor.kicad_pro: the project settings
sym-lib-table, fp-lib-table, libs/: the project’s custom symbol and footprint libraries

## References
Our Blueprint report for the Electrome project (the schematic simulated in this project):
Listen to Plants: A Multichannel Electrical Sensing Platform for Plant Physiology
Description of the Capstone project:
ELEC 498 Capstone project description
ngspice documentation
KiCad Docker image (kicad/kicad)

# AI Declaration
Not sure if people even do these anymore, but for transparency, AI was used during this in the following areas:
   - Revised my writing + formatted this README (If it's unclear, blame Opus 5.5)
   - Documentation help + compatibility checks for packages in both workflows ( I still handwrote most of the code, as the primary goal for this was learning )
   - Makefile ( 100% AI, I don't have enough experience with KiCad, all my previous simulations have been done with Cadence )
   - verify.py ( 100% AI, lazy )
   - Overall code help, gone are the days of trying to debug error messages.
