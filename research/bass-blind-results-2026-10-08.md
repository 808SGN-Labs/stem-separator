# Bass blind listening results — Controls 01–03

Date: 2026-10-08
Status: preliminary, single-listener evaluation; all bass scores complete.

## Scope and method

Three control packs, four candidates per pack, five criteria per candidate: 60/60 integer ratings in the range 1–5. Candidate counts and labels match each pack's mapping. Mappings were read for this consolidation only after all scores passed completeness checks. The listener's reveal history was not independently verified.

Criteria: bass isolation, bass integrity, low-end stability, note definition, remix usability. Higher is better. Each control score is the unweighted mean of its five ratings; the aggregate equally weights the three controls. These descriptive averages of ordinal ratings are not objective separation metrics or statistical significance tests.

Sources: scores.json and mapping.secret.json in data/listening/control-01-bass-blind-01, control-02-bass-blind-01 and control-03-bass-blind-01. This report deliberately omits candidate-letter mappings and absolute local source paths. Raw scores and mappings were not modified.

## Results

| Model | Preset | Control 01 | Control 02 | Control 03 | Mean / 5 |
|---|---|---:|---:|---:|---:|
| htdemucs_ft.yaml | maximum | 3.80 | 4.00 | 4.40 | 4.07 |
| htdemucs.yaml | balanced | 4.00 | 3.20 | 4.00 | 3.73 |
| htdemucs_6s.yaml | 6stems | 2.80 | 2.00 | 3.80 | 2.87 |
| hdemucs_mmi.yaml | 4stems | 2.40 | 1.20 | 2.20 | 1.93 |

## Criterion averages across controls

| Model | Isolation | Integrity | Stability | Definition | Remix |
|---|---:|---:|---:|---:|---:|
| htdemucs_ft.yaml | 4.33 | 4.33 | 3.67 | 4.00 | 4.00 |
| htdemucs.yaml | 3.67 | 4.00 | 3.33 | 3.67 | 4.00 |
| htdemucs_6s.yaml | 2.67 | 3.00 | 3.00 | 2.67 | 3.00 |
| hdemucs_mmi.yaml | 1.67 | 2.00 | 1.67 | 2.33 | 2.00 |

## Associated run times

Values below are runtime_seconds recorded in the pack mappings, in seconds. They refer to associated separation runs, not bass-only inference. Benchmark logs were not revalidated during this consolidation.

| Model | Control 01 | Control 02 | Control 03 |
|---|---:|---:|---:|
| htdemucs_ft.yaml | 127.52 | 191.43 | 159.91 |
| htdemucs.yaml | 26.66 | 49.21 | 45.55 |
| htdemucs_6s.yaml | 25.46 | 54.02 | 43.46 |
| hdemucs_mmi.yaml | 15.51 | 32.66 | 23.62 |

## Provisional product decision

- Keep htdemucs / balanced as the practical default candidate for bass-oriented CPU workflows: 3.73/5 overall, winning Control 01 (4.0 versus 3.8 for ft).
- Offer htdemucs_ft / maximum as an optional quality candidate: 4.07/5, winning Controls 02 and 03. Its advantage over balanced is 0.33 points overall, with approximately 3.5–4.8 times the associated runtime across these controls. The current evidence does not justify making it the CPU default.
- Do not promote htdemucs_6s as a bass-quality upgrade: 2.87/5 overall and substantial control dependence. Its value for additional stems requires separate assessment.
- hdemucs_mmi is the fastest of these associated runs but scores lowest for bass (1.93/5). Speed alone is insufficient for a bass-quality recommendation.
- No presets or defaults were changed by this report. Bass results do not establish an overall winner for vocals, drums or other stems.

## Limitations and next release step

One listener, three short controls, no repeat-listener reliability assessment and no reference-stem objective metrics. Do not describe this as a universal model ranking. Existing research/results-v0.1.md covers only the earlier two-control vocal summary and is not a complete current consolidation.

Next: verify current vocal scores including Control 03, consolidate vocal and bass findings, and prepare a minimal CLI research demonstration showing balanced versus maximum quality/runtime trade-offs. Full-stem QC remains separate work. Inspect publication exclusions for raw research assets and mapping.secret.json before any release; no commit or publication was performed.

QC UI: user confirmed local appearance and operation on 2026-10-08.
