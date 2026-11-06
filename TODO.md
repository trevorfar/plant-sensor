# TODO

## Models (constraint: never invent SPICE models)
- [ ] **OPA2192/OPA4192**: replace `OPAMP_GENERIC` with the TI model. The generic model does **not** model the
      input common-mode range or the RRIO transition region (V+ − 3 V … V+ − 1.5 V), noise, or CMRR/PSRR.
      If the TI licence forbids redistribution, download it in `docker/Dockerfile` into `/opt/vendor-models`.
- [ ] **INA121**: replace `INA_GENERIC` with the TI macro-model (input CM range on ±5 V, CMRR vs frequency).
- [ ] **ADG1219**: no vendor model. `SW_ON`/`SW_OFF` uses Ron ≈ 120 Ω read off datasheet Fig. 5 (±5 V); the
      datasheet only *tabulates* ±15 V / +12 V. Measure Ron and leakage at ±5 V on the bench.
- [ ] **AD5933**: output resistance on range 4 assumed 600 Ω (`RAD` in `excitation.cir`). R413 = 49.3k compensates
      it (R412 + R413 + Rout = 99.8k). Verify against the datasheet table/bench; re-trim R413 if different.

## Schematic / layout
- [x] Run ERC in KiCad 9. Done 2026-11-06 with kicad-cli 9.0.9: 0 errors, 0 warnings (all severities).
      Netlist: 86 named nets + 53 no-connect pins, matching the generation-time check.
- [ ] Open the project once in the KiCad 9 GUI and save, to upgrade the file format (still 20230121 / KiCad 7;
      kicad-cli 9.0.9 reads it fine but has no `sch upgrade`). Commit the result separately.
- [ ] Verify footprints before layout: AD7124-8 LFCSP-32 exposed-pad size (placeholder `EP3.5x3.5mm`),
      RH-0505D (placeholder `PinHeader_1x07`, pins 3/4 absent), ADP7118 SOIC-8-EP.
- [ ] AD5933 MCLK: R411 pulls MCLK low and the internal 16.776 MHz oscillator is used. Sweeps below ~1 kHz need
      an external lower-frequency MCLK (add oscillator footprint on AD5933_MCLK).
- [ ] EIS mode: GUARD follows the *passive* common mode (≈ 0 V in EIS), so cable capacitance loads the EIS
      sense/drive lines (modelled as 20 pF → `iout_100k_ratio` ≈ 0.93). Rev B option: switch the shield drive to
      the SBUF outputs in EIS mode.
- [ ] BOM guide lists 2× INA121; the block diagram has one passive channel. Decide whether a second channel
      (AIN2/AIN3 are free) is wanted.
- [ ] D301 clamps AIN0 into +3V3A. Confirm the +3V3A load always exceeds the worst fault current (≈1 mA) so the
      LDO is never back-driven.
- [ ] RH-0505D is unregulated: measure ±5 V at the real load (≈25 mA / 11 mA) — corners assume ±4.5 … ±5.5 V.

## Assumptions to confirm (they feed corners.yaml / testbenches)
- [ ] Operating temperature −10 … 50 °C (greenhouse with margin).
- [ ] AD7124 ODR 256 SPS (FS = 75, sinc4, full power), 24-bit; usable passive input ±250 mV.
- [ ] Tolerances: precision R 0.1 % / 25 ppm, general R 1 % / 100 ppm, C0G 2 % / 30 ppm, X7R 10 %.
- [ ] Electrode contact: 1.2 MΩ per contact (passive, low frequency; Crichton 120 h value), 10 kΩ at EIS frequencies,
      20 pF cable capacitance.
- [ ] 60 Hz mains notch (change R305/R306/R307 for 50 Hz).

## CI
- [ ] Create Namespace runner profile `plant-sensor` with a cache volume (Container images + Git checkouts).
- [x] ngspice source build dropped: SourceForge returned 404 to scripted downloads. The image now installs
      ngspice 46 from bookworm-backports.
- [ ] Build the image locally once (`make docker-build`) and note build time / size. Docker was not installed on
      the machine where the repo was set up, so the image has not been built yet.
- [ ] Push and get `ci-baseline` green on GitHub-hosted runners; record the baseline table (README).
