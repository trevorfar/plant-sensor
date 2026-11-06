# sim/models — provenance

| File | Origin | Licence | Date | Notes |
|---|---|---|---|---|
| `generic.lib` | Written for this project (not a vendor model) | Same as repository | 2026-11-06 | `OPAMP_GENERIC`, `INA_GENERIC`, `SW_ON`/`SW_OFF`. Parameters are typical values from the OPA192 (TI SBOS620), INA121 (TI SBOS078) and ADG1219 (ADI) datasheets. Clearly labelled **GENERIC** inside the file. |

## Vendor models: status

| Part | Vendor model | Status |
|---|---|---|
| OPA2192 / OPA4192 | TI PSpice model on the product page | Not yet fetched. Check licence; if redistribution is forbidden, download it in `docker/Dockerfile` into `/opt/vendor-models` (see TODO.md) |
| INA121 | TI PSpice macro-model | Not yet fetched (TODO.md) |
| ADG1219 | none known | Generic `SW_ON`/`SW_OFF` used |
| AD5933 | none (mixed-signal IC) | Modelled in testbenches as an ideal source + output resistance |
| AD7124-8 | none | Modelled as an ideal sampler (quantisation/noise belong in Python, not SPICE) |

Do not commit any vendor model whose licence forbids redistribution. Add one row per model to this table (URL, licence, download date).
