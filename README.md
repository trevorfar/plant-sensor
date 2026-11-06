KiCad 9 schematic, ngspice testbenches, and a CI pipeline that checks the schematic (ERC), exports
netlist/BOM/PDF, simulates every analog block across 27 corners and 2000 Monte Carlo runs, and reports pass/fail
and yield.

Point of this is to apply namespace

Baseline: plain github runners (.github/workflows/ci-baseline.yml)
Namespace: Namespace runners, remote docker builder, cache volumes, matrix fanout

## Quick start (local)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # needs kicad-cli 9 + ngspice >= 42 on PATH
make all          # erc -> export -> corners -> mc -> report  (results/report/report.md)
make docker-build # build the CI image (kicad/kicad:9.0.9 + ngspice 46 + Python)
make docker-all   # the same `make all`, inside the image
```

Single runs (all scripts have `--help`):

 `ngspice -b sim/testbenches/anti_alias.cir` | raw testbench with its nominal `.param` values |
 `scripts/run_sim.py --block all --bom exports/plant-sensor-bom.csv --corner-index 0` | one corner (0..26) |
 `scripts/run_sim.py --block eis_excitation --bom … --seed 1234` | reproduce one MC run (run *i* = seed 42 + *i*) |
 `scripts/mc_shard.py --shard 0 --bom …` | one of the 20 MC shards (100 runs × 4 blocks) |
 `scripts/report.py --corners results/corners --mc results/mc` | aggregate + histograms |

Component values come from the **schematic**: the BOM export carries `Value`/`Tolerance`/`TempCo`, and
`run_sim.py` overwrites every `.param <REFDES>` in the testbenches. Editing a part in KiCad changes the simulation.

## Baseline numbers 

| measurement | value |
|---|---|
| ERC (local, kicad-cli 9.0.9) | 0 errors / 0 warnings, < 2 s |
| 27 corners, serial, local (16-core WSL) | 11 s, 459/459 checks pass |
| 2000-run MC, local (20 shards × 16 workers) | 77–140 s wall (≈ 1000–1900 s summed ngspice time) |
| 1 MC shard, 1 worker | 17 s → ≈ 350 s full serial estimate |
| Red test: C308 47n → 470n | `f3db_hz` 1.55 Hz + `settle_half_lsb_s` 0.59 s fail, exit 1 |
| Docker build time / image size | _not built yet_ |
| `ci-baseline` erc / export / sim job durations | _not run yet_ |
| `ci-baseline` time in apt-install step | _not run yet_ |

## Schematic (hardware/)

Hierarchical, 5 sheets, label-connected (every pin has a stub + net label):

| sheet | contents |
|---|---|
| Power | RH-0505D isolated ±5 V → ferrites → ±5VA; 2 × ADP7118-3.3 → +3V3A (AD7124) / +3V3D (AD5933, isolators, expander) |
| Electrodes | 5 SMA inputs (V+, REF, V−, I+, I−), Rs = 10k 0.1 %, BAV199 clamps to ±5VA, SW1–SW5 = ADG1219 |
| PassiveAFE | INA121 (G = 3.994) → bootstrapped twin-T 60 Hz notch → Sallen-Key 20 Hz LPF → AD7124 AIN0/AIN1; guard driver |
| EIS | AD5933 → C405 → improved Howland VCCS; tetrapolar sense buffers → diff amp (G = 4.02) → R409 → AD5933 VIN |
| Digital | AD7124-8, ADuM1401 (SPI), ADuM1250 (I²C), TCA9534 switch control, Raspberry Pi 40-pin header |

Switch topology follows the block diagram exactly: IN = 0 selects the passive (solid) throw, IN = 1 the EIS (dotted)
throw, and the "x" throws are no-connects. SW_EN low (R206 pull-down, default at power-up) floats every electrode.

### Conventions applied (complete list)
1. Every node a testbench probes has a net label, and the testbench uses the same name: `PASS_INP`, `PASS_INN`,
   `INA_OUT`, `TT_R`, `TT_C`, `TT_OUT`, `NOTCH_OUT`, `BOOT`, `BOOT_DIV`, `LPF_M`, `LPF_P`, `LPF_OUT`, `ADC_AIN0`,
   `ADC_AIN1`, `VCM_DIV`, `VCM_1V25`, `REFOUT_2V5`, `RG_A`, `RG_B`, `GUARD_CM`, `EIS_SENSE_P/N`, `SBUF_P/N`,
   `DA_P/N`, `DIFF_OUT`, `VHALF_DIV`, `VHALF_1V65`, `AD5933_VOUT`, `AD5933_VIN`, `HOW_IN`, `HOW_R3M`, `HOW_P`,
   `HOW_N`, `HOW_VO`, `HOW_L`, `EIS_IOUT`, `E_*`/`EP_*` electrode nodes.
2. Every R and C has a `Tolerance` field and a `TempCo` field. TempCo is empty for X7R/X5R and the 5 % HV resistors,
   which have no linear tempco.
3. `Value` holds SPICE-parsable values (`10k`, `100n`, `10Meg`, `1G`). Mega-ohm values are written `Meg`, because
   SPICE reads `M` as milli. ICs carry the part number in `Value` and `MPN`.
4. Refdes blocks: 1xx power, 2xx electrodes, 3xx passive AFE, 4xx EIS, 5xx digital. Testbench `.param` names = refdes.

## Design decisions (deviations from the BOM guide in **bold**)

- **OPA4192/OPA2192 instead of OPA2140.** OPA140's input CM range ends at (V+) − 3.5 V, which is +1.0 V on a 4.5 V
  rail. That is below the 1.25 V bias the ADC interface needs. OPA192 is RRIO (I_B 20 pA max).
- **ADC guardrails:** INA REF = VCM_1V25 = REFOUT/2, so AIN0 = 1.25 V + 3.994·Vd and AIN1 = 1.25 V. With gain 1
  and buffers on, the AD7124 window is 0.1 to 3.2 V, which allows Vd = −287 mV … +488 mV. The usable range is
  specified as ±250 mV. R315 = 1k + BAV199 to +3V3A/AGND clamps AIN0 if the ±5 V chain rails, and 10 nF C0G
  absorbs ADC kick-back. Rail-dependent offsets cancel because AIN0 and AIN1 share VCM.
- **Guard:** R_G is split into 2 × 8.35k. GUARD_CM = (V+ + REF)/2 comes from the INA input buffers, so the
  electrodes are not loaded. The block diagram's two resistors tapped the electrode lines directly; to keep that
  divider's error below 0.1 % with 1.2 MΩ contacts they would need to be ≥ 1.2 GΩ each.
- **Notch:** twin-T with f0 = 1/(2π · 26.4k · 100n) = 60.3 Hz, bootstrapped at k = 0.901 → Q = 1/(4(1−k)) ≈ 2.5.
- **LPF:** unity-gain Sallen-Key, R = 115k, C1 = 100n, C2 = 47n → fc = 1/(2π · 115k · √(100n · 47n)) = 20.2 Hz,
  Q = ½ · √(C1/C2) = 0.73.
- **Howland:** I = V_exc/R4b = 99 mV / 49.9k = 1.98 µA pk. Balance: R2/R1 = (R4a + R4b)/(R412 + R413 + R_AD5933)
  = 99.8k/99.8k. Simulation found that the AD5933 range-4 output resistance (~600 Ω) alone gave Zout ≈ −17 MΩ;
  **R413 = 49.3k** compensates it and **C405 = 10 µF** keeps Xc ≪ R3. C406 + R418/R419 (100 MΩ) keep DC out
  of the tissue. Compliance: Vo = 2(V_exc + 2·VL)/3 → 2.7 V pk at a 1 MΩ load.
- **Bias returns:** PASS_INP 1 GΩ, PASS_INN (REF) 10 MΩ. Only one low-ish path to AGND exists, so no DC current
  flows through the contacts (simulated loading: 0.02 dB).

## Spec rationale (specs/specs.yaml)
Limits are design requirements derived above, not fitted to results. Re-verified 2026-11-06 (kicad-cli 9.0.9,
ngspice 45.2, generic models): 27/27 corners pass (459/459 checks) and 2000-run MC gives 100 % yield. Tightest margins: `att60_db`
35.6 dB at the all-caps-+2 % corner (limit 35), and EIS `cmrr_1k_db` 67 dB worst MC run (limit 60). Changing
C308 47n → 470n fails `f3db_hz` (1.55 Hz) and `settle_half_lsb_s`, and the report names the corners.

## Phase 2: Namespace 

`docs/reference/ci-namespace.yml` is the target pipeline the schematic model wrote. It is **inactive** and kept
as an answer key. It uses runner profile `namespace-profile-plant-sensor`, `nscloud-setup-buildx-action` (remote
builder with persistent layer cache), an image pushed to GHCR, `nscloud-cache-action` for a cache volume, a 27-job
corner matrix and a 20-shard MC matrix running concurrently, and a report job.

Checklist (from the setup guide):
1. Install the Namespace GitHub App on the repo; create runner profile `plant-sensor` (Linux amd64, 4 vCPU) with a
   cache volume (Container images + Git checkouts).
2. Move `erc` to a Namespace runner: what changed in the YAML, how did time compare?
3. Remove the per-job apt install: remote-builder image vs cache volume. Measure each.
4. Turn the serial corners into the 27-job matrix; compare wall-clock vs the serial number above.
5. 20 MC shards + aggregate job; compare wall-clock and unit-minute cost.
6. Break a job on purpose (C308 → 470n) and debug it live with a breakpoint/SSH.
7. Later: a Devbox from the same image, with an agent fixing a failing spec and opening a PR.

See `TODO.md` for the generic-model limitations, unverified footprints and assumptions to confirm.
