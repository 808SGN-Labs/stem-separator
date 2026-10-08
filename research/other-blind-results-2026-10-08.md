# StemLab — Other/Music blind listening results

Date: 2026-10-08
Status: three controls complete; descriptive single-listener pilot.

All 75/75 values are present in the three Other blind packs. The five criteria are music isolation, harmonic integrity, artifact control, reverb/tail integrity and remix usability. Means weight each criterion and control equally. Mapping was read only after the packs were complete; candidate letters and mapping contents are excluded here.

| Model | Control 01 | Control 02 | Control 03 | Mean / 5 |
|---|---:|---:|---:|---:|
| htdemucs_6s | 2.80 | 3.20 | 3.20 | 3.07 |
| htdemucs_ft | 2.60 | 3.20 | 3.40 | 3.07 |
| hdemucs_mmi | 2.60 | 3.20 | 3.20 | 3.00 |
| htdemucs (balanced) | 2.60 | 3.00 | 3.00 | 2.87 |
| MelBand RoFormer | 1.00 | 2.20 | 2.40 | 1.87 |

## Interpretation

All models scored modestly on Other/Music compared with ideal remix-ready separation; no clear winner between htdemucs_6s and htdemucs_ft. The RoFormer output must be checked for semantic comparability: a vocals-oriented model's residual/instrumental output is not necessarily equivalent to Demucs's dedicated Other stem. Do not treat its lower score as a general assessment of its vocal-separation performance.

## Method limits

One listener, three excerpts, ordinal scores, no ground truth, no independent repeat ratings. Source-dependent performance remains substantial. Preserve original scores and secret mappings. Do not publish candidate mappings or uncleared audio. Verify provenance, file identity and intended stem semantics before making release claims.

Next: consolidate all four stem categories into the research overview; decide whether a dedicated Other mode belongs in MVP and whether additional diverse controls are needed.
