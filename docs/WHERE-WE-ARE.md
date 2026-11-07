# Plant Sensor CI: where we are

_Last updated 2026-11-06. This is the state of the project at the end of **Phase 1 (baseline)**, just before
the Namespace work starts._

---

## 1. The 30-second version

- **What this repo is:** a circuit design (a plant sensor front end) plus an automated system that checks
  the design every time you push code. That automated system is called **CI** (continuous integration).
- **Why it exists:** the circuit is just a realistic *workload*. The real goal is to learn **Docker** and
  **Namespace** (a faster, cache-friendly place to run CI) by making this CI faster and cheaper, and measuring
  how much.
- **Where we are:** the CI runs on GitHub's own free machines ("GitHub-hosted runners"), deliberately slowly.
  That gives the **"before"** numbers. Namespace is the **"after"**, and that part is yours to do.

| Thing | Status |
|---|---|
| Schematic passes the electrical rules check (ERC) | ✅ 0 errors, 0 warnings (KiCad 9.0.9) |
| Simulations pass locally | ✅ 27/27 corners, 2000/2000 Monte Carlo runs |
| "Break it on purpose" test fails correctly | ✅ |
| Repo pushed to GitHub (`trevorfar/plant-sensor`) | ✅ |
| `ci-baseline` workflow on GitHub | ✅ first run green: all 3 jobs pass, **~6 min 40 s** end to end (see §6) |
| Docker image built on your laptop | ❌ not yet (Docker is installed, but your user can't access it yet; see §7) |
| Namespace | ⏭️ next phase, yours |

---

## 2. What the circuit does (just enough to follow along)

The board reads tiny electrical signals from a plant through electrodes stuck on a leaf. It has two modes:

1. **Passive mode:** listen to the plant's own voltage signals (microvolts to millivolts). The signal is
   amplified, cleaned of 60 Hz mains hum, low-pass filtered at 20 Hz, then digitised by an **AD7124** ADC.
2. **EIS mode** (electrical impedance spectroscopy): push a tiny known current (≈2 µA) through the leaf
   and measure the voltage, using an **AD5933** chip. This tells you about the tissue.

Five analog switches choose between the two modes. A Raspberry Pi talks to everything.

You don't need to understand the electronics to do the CI work. What matters is that there are **4 analog
blocks** and each one has a simulation with pass/fail limits.

---

## 3. Vocabulary (the words you'll keep seeing)

| Word | Plain meaning |
|---|---|
| **CI** | A robot that runs your checks automatically on every push, so you find breakage immediately. |
| **GitHub Actions** | GitHub's built-in CI system. |
| **Workflow** | One YAML file in `.github/workflows/` that describes what the robot does. Ours: `ci-baseline.yml`. |
| **Job** | One chunk of a workflow that runs on **its own fresh machine**. Jobs share nothing unless you pass files explicitly. |
| **Step** | One command inside a job. Steps in the same job share the same machine and files. |
| **Runner** | The machine that runs a job. `runs-on: ubuntu-latest` = a free GitHub VM (4 vCPU). Namespace sells faster runners. |
| **Docker image** | A frozen, pre-installed "box" of software (an OS + tools). Built from a **Dockerfile** recipe. |
| **Container** | A running copy of an image. Like starting a fresh computer that already has the tools installed. |
| **Registry** | A place that stores images, like Docker Hub or GHCR (GitHub's). CI downloads ("pulls") images from there. |
| **Artifact** | A file a job uploads so a later job (or you) can download it, like the BOM or the report. |
| **Matrix** | "Run this job N times with different inputs, in parallel", e.g. 27 copies, one per corner. |
| **Cache** | Keeping something (a downloaded image, installed packages) around so the next run doesn't redo it. |
| **ERC** | Electrical Rules Check: KiCad checks the schematic for mistakes like unconnected pins or two outputs shorted together. |
| **Netlist / BOM** | Netlist = which pins connect to which. BOM (bill of materials) = the parts list with values and tolerances. |
| **Corner** | One "worst-case" combination: temperature × supply voltage × part tolerance. 3 × 3 × 3 = **27 corners**. |
| **Monte Carlo (MC)** | Simulate many random boards, each part randomly off its nominal value, and count how many pass (the **yield**). |
| **Shard** | One slice of the Monte Carlo work. 2000 runs ÷ 20 shards = 100 runs each. |

---

## 4. Every file and folder, explained

```
plant-sensor/
├── hardware/                  the circuit (KiCad 9 schematic)
├── sim/                       the simulations
│   ├── testbenches/*.cir      4 ngspice circuits, one per analog block
│   ├── models/generic.lib     simplified op-amp / in-amp / switch models
│   ├── corners.yaml           defines the 27 corners
│   └── montecarlo.yaml        2000 runs, 20 shards, seed 42
├── specs/specs.yaml           pass/fail limits for every measured number
├── scripts/                   Python glue
│   ├── run_sim.py             run 1 testbench at 1 corner (or 1 random seed) → JSON
│   ├── check_specs.py         compare JSON results to specs.yaml → table, exit 1 on any fail
│   ├── mc_shard.py            run one Monte Carlo shard, in parallel over CPU cores
│   └── report.py              combine everything → report.md + histogram PNGs
├── Makefile                   short names for the commands above (make erc, make all, …)
├── docker/Dockerfile          recipe for the all-in-one CI image (not used by CI yet!)
├── .github/workflows/
│   └── ci-baseline.yml        ← the ONLY active workflow. Runs on GitHub's machines.
├── docs/
│   ├── reference/ci-namespace.yml   the "answer key" Namespace workflow (INACTIVE, outside .github/)
│   └── WHERE-WE-ARE.md        this file
├── README.md / TODO.md        overview + open items
├── requirements.txt           Python packages for your local venv
└── model_out/                 the raw zip/PDF from the other model (gitignored, not pushed)
```

Folders that exist only on your laptop (gitignored, regenerated by `make`): `.venv/`, `exports/`, `results/`.

### The one idea that ties it all together

**The schematic is the single source of truth for part values.**

```
KiCad schematic ──(kicad-cli export bom)──► BOM CSV ──(run_sim.py)──► ngspice testbench ──► JSON metrics
     C308 = 47n                              C308,47n,2%              .param C308 = 47n       f3db_hz=20.5
```

`run_sim.py` reads the BOM and **overwrites** each `.param C308 = …` line in the testbench before running
ngspice. So if someone changes a capacitor in KiCad, the simulation changes too. You saw this with the red test:
C308 47n → 470n made the filter cutoff drop to 1.55 Hz, and the check failed.

---

## 5. What happens when you `git push`

GitHub sees `.github/workflows/ci-baseline.yml` and starts the workflow `ci-baseline`. It has 3 jobs, in a chain:

```mermaid
flowchart LR
  A["<b>erc</b><br/>is the schematic wired correctly?"] --> B["<b>export</b><br/>make netlist, BOM, PDF"]
  B -- "BOM uploaded as artifact" --> C["<b>sim</b><br/>27 corners + 2000 Monte Carlo<br/>→ report"]
```

`needs: erc` means "don't start until `erc` has passed". That's why they run one after another.

### Job 1: `erc`
| Step | What it really does |
|---|---|
| Set up job | GitHub gives us a brand-new Ubuntu VM. |
| **Initialize containers** | Downloads the `kicad/kicad:9.0.9` image (~0.5 GB) and starts it. **Every job pays this.** |
| checkout | Copies your repo into the container. |
| apt install make | Installs `make`, which the KiCad image doesn't have. |
| `make erc` | Runs `kicad-cli sch erc …`. Exits non-zero (fails the job) if any ERC error exists. |
| upload-artifact | Saves `erc.rpt` so you can download it from the run page. |

### Job 2: `export`
A fresh machine again: pull the image again, checkout again, install `make` again. Then `make export` writes
the netlist, BOM CSV and PDF, and uploads them as the **`exports` artifact**.

### Job 3: `sim`
1. Fresh machine, pull the KiCad image (a third time).
2. **Download the `exports` artifact.** This is how the BOM travels from job 2 to job 3, since jobs don't share disks.
3. **apt install ngspice + Python.** Deliberately done here, every run. This is the waste Namespace should remove.
4. `make corners`: runs all 27 corners **one after another**, writes a pass/fail table into the run's
   **Summary** page.
5. `make mc`: runs the 20 Monte Carlo shards one after another (each shard uses all 4 CPU cores).
6. `make report`: combines everything into `report.md` + histograms, uploaded as the `sim-results` artifact.

**Where to look:** GitHub → your repo → **Actions** tab → `ci-baseline` → click the run. The left side lists the
jobs; click one to see each step's log and duration. Summary tables and artifact downloads are on the run's
main page.

---

## 6. What the first real run showed

Run `42298711465`, commit `d3e8943` ("Launching baseline test"). **All green.** Wall-clock about
**6 min 40 s** from push to finish. Summed job time: 24 + 31 + 338 = **393 s** of runner time.

| Job | Total | Image pull ("Initialize containers") | Other setup | Real work |
|---|---|---|---|---|
| erc | 24 s | 17 s | ~6 s (checkout, apt `make`, upload) | **< 1 s** ERC |
| export | 31 s | 20 s | ~10 s | **~1 s** exports |
| sim | 338 s | 17 s | **33 s apt install** + ~13 s misc | **13 s** corners + **255 s** Monte Carlo + 3 s report |

Inside `sim`, step by step:

```
Initialize containers (pull KiCad image)   17 s  ███
apt install ngspice + Python               33 s  ██████
27 corners (serial)                        13 s  ██
2000-run Monte Carlo (20 shards, 4 cores) 255 s  ██████████████████████████████████████████████
report + upload + misc                     20 s  ███
```

**Two lessons are already visible:**

1. **For the small jobs, setup is the cost.** In `erc`, about 70% of the job is downloading and starting the
   image, and the actual check takes under a second. Across all three jobs, image pulls (54 s) + apt installs
   (~38 s) ≈ **92 s, almost a quarter of all runner time**, spent on things a cached image would make nearly free.
2. **For `sim`, Monte Carlo is the cost.** 255 s on GitHub's 4-core runner vs. 77–140 s on your 16-core laptop.
   It's real CPU work, so **splitting it across machines (the 20-shard matrix) should genuinely help** here,
   unlike the 13 s of corners. In CI, setup overhead often dominates, not the work. Namespace's
pitch (cached images on a cache volume, fast-starting runners, a remote Docker builder with layer cache) goes
straight at this overhead.

---

## 7. Docker on your laptop

### The image recipe (`docker/Dockerfile`), in one breath
Start from the official `kicad/kicad:9.0.9` image (Debian bookworm, has `kicad-cli`) → add ngspice 46 from
Debian's *bookworm-backports* repo (the normal bookworm one is too old) → add Python + numpy/scipy/yaml/matplotlib
+ make + git → set a writable `HOME` so it can run as your user → print the tool versions as a self-test.

Result: **one box with every tool**, so CI would no longer need to apt-install anything per job.

### Important: CI does NOT use this image yet
`ci-baseline.yml` uses the stock KiCad image and installs things by hand on purpose (that's the "before").
Switching CI to *this* image, built on Namespace's remote builder, is one of your Namespace steps.

### Current blocker
Docker is installed, but running it gives `permission denied … /var/run/docker.sock`. Your user isn't allowed
to talk to the Docker service yet. The usual fix on Linux/WSL:

```bash
sudo usermod -aG docker $USER
```

Then close and reopen your terminal (or run `newgrp docker`). If you use Docker Desktop instead, turn on
*Settings → Resources → WSL integration* for your distro. Then:

```bash
cd ~/plant-sensor && time make docker-build && docker images plant-sensor-ci
```
```bash
make docker-all
```

`docker-all` runs the whole pipeline (`make all`) inside the container, with your repo folder mounted at `/work`.
If it passes, the image is good, and the build time and size go in the baseline table.

---

## 8. Running things yourself (local, no Docker)

```bash
make all        # erc → export → corners → mc → report   (~2–3 min here)
```

| Command | What you get |
|---|---|
| `make erc` | `results/erc.rpt` |
| `make export` | `exports/` netlist, BOM CSV, PDF |
| `make corners` | `results/corners/*.json` + `results/corners.md` (the pass/fail table) |
| `make mc` | `results/mc/*.json` (8000 files = 2000 runs × 4 blocks) |
| `make report` | `results/report/report.md` + `results/report/histograms/*.png` |
| `make clean` | deletes `results/` and `exports/` |

---

## 9. Baseline numbers so far

| Measurement | Value |
|---|---|
| ERC, local | 0 errors / 0 warnings, < 2 s |
| 27 corners, serial, local (16-core WSL) | **11 s**, 459/459 checks pass |
| 2000-run Monte Carlo, local | **77–140 s** wall time (varied between runs) |
| One MC shard on 1 core | 17 s → ≈ 350 s if everything ran on a single core |
| CI whole run (GitHub-hosted, push → green) | **~6 min 40 s**, 393 s of runner time |
| CI `erc` job | 24 s (17 s image pull) |
| CI `export` job | 31 s (20 s image pull) |
| CI `sim` job | 338 s |
| CI apt-install step (sim) | 33 s |
| CI 27 corners, serial | 13 s |
| CI 2000-run Monte Carlo, serial shards on 4 cores | 255 s |
| Docker build time / image size | _pending (§7)_ |

**Expectation to keep in mind:** each corner takes only about 0.4 s to simulate. If you split 27 corners
into 27 separate CI jobs, each job pays ~20 s of setup for 0.4 s of work, so the "parallel" version could
easily be **slower** than the serial one. That isn't a failure. It's the exact thing to measure, and
the comparison that makes the Namespace story interesting.

---

## 10. Things that are NOT done / caveats

- **The simulations use simplified "generic" op-amp models.** They pass, but they don't model input range
  or noise. Swapping in TI's real models is `TODO.md` item #1. It's an engineering task, separate from CI.
- **Schematic files are still in KiCad 7 format.** KiCad 9 reads them fine. Open and save once in the KiCad 9
  app at some point to upgrade them.
- **Your doc's design assumptions (items 6–9)** were guessed by the other model: 256 samples/s, −10 to 50 °C,
  tolerances, bare AD7124 chip. They're listed in `TODO.md` for you to confirm.
- `docs/reference/ci-namespace.yml` was written by the other model and **has never run**. Treat it as a
  guide, not as known-good.

---

## 11. What's next: the Namespace phase (yours)

Each step changes one thing, so you can measure what that one change bought you.

| # | Step | What it teaches |
|---|---|---|
| 1 | Install the Namespace GitHub App; create runner profile `plant-sensor` with a cache volume | How Namespace plugs into GitHub Actions |
| 2 | Change `erc` to `runs-on: namespace-profile-plant-sensor` | Same job, different machine: compare the 24 s |
| 3 | Kill the per-job apt install: build `docker/Dockerfile` with Namespace's remote builder, push to GHCR, use it in jobs | Docker images as "pre-installed tools"; layer caching |
| 4 | Split `make corners` into a 27-job matrix | Parallelism vs. per-job overhead (§9 warning) |
| 5 | 20 MC shards as a matrix + one report job that merges them | Fan-out / fan-in; cost in unit-minutes |
| 6 | Break C308 on purpose, debug the failing job live (breakpoint / SSH) | Namespace's debugging tools |
| 7 | (Later) Devbox from the same image; agent fixes a failing spec and opens a PR | Image reuse beyond CI |

For every step, write down **before time, after time, and cost**. That table is your write-up.
