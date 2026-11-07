# Plant Sensor CI: GitHub Actions vs Namespace

## Goal

Take an existing project (my Capstone circuit, see [References](#references)) and use GitHub Actions / Namespace to:

- Perform ERC (Electrical Rule Check) validation
- Export netlist / BOM
- Simulate 27 corners + 2000-run Monte Carlo (ngspice)
- Export sim results

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


### Machine Specs

|Specs |GitHub | Namespace |
| --- | --- | --- |
|Name | Debian GNU/Linux 12 (bookworm)| Debian GNU/Linux 12 (bookworm)|
|vCPUs| 4 | 4 |
|Model name|  AMD EPYC 9V45 96-Core Processor| AMD EPYC|
|Thread(s) per core | 2 | 2 |
|Core(s) per socket | 2 | 2 |
|Socket(s) | 1 | 1 |
|L3 cache | 32 MiB | 32 MiB |
|Memory | 15Gi | 7.8 Gi |

In addition, Namespace was given a 50GB Cache Volume

Notes:
I ran this off the free github actions Public repo resources. In hindsight, I should have ran the namespace comparisons with 16GB of RAM, although in deeper comparison it didn't look like that was a limiting factor.

## References

- Our Blueprint report for the Electrome project (the schematic simulated in this project):
  [Listen to Plants: A Multichannel Electrical Sensing Platform for Plant Physiology](docs/Blueprint.pdf)
- Description of the Capstone project:
  [ELEC 498 Capstone project description](https://smithengineering.queensu.ca/ece/undergraduate/courses/elec-498.html)
- [ngspice documentation](https://ngspice.sourceforge.io/)


