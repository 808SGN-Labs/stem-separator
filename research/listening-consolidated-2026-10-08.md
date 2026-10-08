# StemLab listening consolidation — Controls 01–03

Date: 2026-10-08
Status: preliminary research; one listener, three source controls, Linux CPU workflow.

## Evidence and method

Verified 75/75 vocal, 60/60 bass, 60/60 drums and 75/75 Other/Music ratings: 270 criterion ratings across three source controls. Each stem was assessed with five criteria scored 1–5 (higher is better). Score labels match the corresponding model mappings. Means equally weight criteria and controls. The 270 individual ratings are not 270 independent observations: they come from one listener and three source excerpts.

Sources: data/listening/control-01-vocals-blind-02, control-02-vocals-blind-01, control-03-vocals-blind-01 and control-01/02/03-{bass,drums,other}-blind-01 (each shorthand denotes three directories). Each supplies scores.json and mapping.secret.json. No candidate-letter mapping or absolute local audio path is included here. Scores and mappings are unchanged. Reveal history was not independently verified.

This report supersedes the two-control listening summary in results-v0.1.md for current listening conclusions; it does not replace or revalidate its runtime benchmark tables. Stem details: [bass](bass-blind-results-2026-10-08.md), [drums](drums-blind-results-2026-10-08.md), [Other/Music](other-blind-results-2026-10-08.md).

## Vocal scores

| Model | Control 01 | Control 02 | Control 03 | Mean / 5 |
|---|---:|---:|---:|---:|
| vocals_mel_band_roformer.ckpt | 4.20 | 4.00 | 3.40 | 3.87 |
| htdemucs_6s.yaml | 4.20 | 3.60 | 3.00 | 3.60 |
| htdemucs_ft.yaml | 3.00 | 2.80 | 4.60 | 3.47 |
| htdemucs.yaml | 3.20 | 2.80 | 3.80 | 3.27 |
| hdemucs_mmi.yaml | 2.80 | 2.80 | 3.40 | 3.00 |

## Vocal detail — Control 03

| Model | Isolation | Integrity | Artifact control | Low-level detail | Remix usability |
|---|---:|---:|---:|---:|---:|
| vocals_mel_band_roformer.ckpt | 4 | 3 | 3 | 4 | 3 |
| htdemucs_6s.yaml | 3 | 3 | 3 | 3 | 3 |
| htdemucs_ft.yaml | 5 | 5 | 4 | 4 | 5 |
| htdemucs.yaml | 4 | 4 | 3 | 4 | 4 |
| hdemucs_mmi.yaml | 4 | 3 | 3 | 3 | 4 |

## Stem-specific comparison

These are separate stem ratings, not a combined overall quality score. A dash means the model was not evaluated for that stem.

| Model | Vocal / 5 | Bass / 5 | Drums / 5 | Other / 5 |
|---|---:|---:|---:|---:|
| vocals_mel_band_roformer.ckpt | 3.87 | — | — | 1.87* |
| htdemucs_6s.yaml | 3.60 | 2.87 | 3.93 | 3.07 |
| htdemucs_ft.yaml | 3.47 | 4.07 | 3.80 | 3.07 |
| htdemucs.yaml | 3.27 | 3.73 | 4.33 | 2.87 |
| hdemucs_mmi.yaml | 3.00 | 1.93 | 4.07 | 3.00 |

* RoFormer instrumental residual is not necessarily semantically comparable to a dedicated Demucs Other stem; do not interpret as a like-for-like Other quality ranking.\n\n## Interpretation and provisional preset guide

| Use case | Existing preset / model | Evidence and qualification |
|---|---|---|
| CPU starting point for bass-oriented four-stem work | balanced / htdemucs | Bass 3.73; faster than ft in all associated runs. Drums 4.33 (highest observed mean), Other 2.87 (below alternatives); this is a general CPU-first default, not a universal stem winner. |
| Vocal extraction | vocals / MelBand RoFormer | Highest vocal mean, 3.87; tied first on Control 01 and first on Control 02. Not best on Control 03. |
| Optional slower bass comparison | maximum / htdemucs_ft | Highest bass mean, 4.07; +0.33 over balanced at roughly 3.5–4.8 times the associated run time. Not a proven universal advantage. |
| Alternative for Control-03-like material | maximum / htdemucs_ft | Vocal score 4.60 on Control 03 versus 3.40 for RoFormer. Source dependence must be tested on new material before generalizing. |
| Six-stem requirement / lower-runtime vocal alternative | 6stems / htdemucs_6s | Vocal mean 3.60, bass 2.87. Extra stem quality is not yet assessed. |
| Speed-oriented baseline | 4stems / hdemucs_mmi | Lowest associated runtime, but bass mean 1.93 and vocal mean 3.00; do not recommend on speed alone. |

Control 03 changes the earlier picture: ft's vocal result rises from 3.0/2.8 on Controls 01/02 to 4.6 on Control 03, while RoFormer falls from 4.2/4.0 to 3.4. A single universal winner is not supported. No preset implementation or default was changed. A mixed-model production recipe remains untested and is not recommended as an established result.

## MVP recommendation after four stem tests\n\nKeep the implemented `balanced` preset as the CPU-first default. Offer the existing vocal-specialist workflow for vocal extraction and `maximum` only as an explicitly slower bass-oriented alternative. Do not claim one model wins all four stem categories. For Other/Music, `htdemucs_6s` and `htdemucs_ft` tie at 3.07/5; there is no strong quality lead. The blind-listening results do not validate mixing different model outputs into one phase-coherent four-stem set. Preserve all existing presets and score files; release readiness depends on reproducibility, rights and exclusion of secret mappings.\n\n## Minimal research-preview scope

A CLI demonstration can show: one input excerpt → existing task preset → local separation → audition of stem outputs → this per-control evidence and CPU trade-off. Use only audio cleared for public demonstration. Present the current result as a three-control, single-listener pilot. A producer GUI release, paid product readiness, full-stem superiority and statistical significance are outside this evidence.

Before publication: review source diffs and reproducibility commands, verify documented run provenance, and inspect the exact publication file set to keep blind mappings and uncleared research audio private. No commit or publication is authorized by this report.

## Next concrete work: Controls 04–06

Select three different tracks before evaluating model outputs; use the same excerpts for every model and both stem tests. Keep excerpt duration at the established 30 seconds for comparability.

| Control | Selection target | Main stress case |
|---|---|---|
| 04 | Different drill/trap production; male rap | Distorted/gliding 808 overlapping a strong kick |
| 05 | Sparse R&B or acoustic production; breathy singing | Quiet vocal detail/reverb plus real bass if available |
| 06 | Dense dance/pop production; layered vocals | Short synthbass notes, kick overlap and vocal layering |

These targets are a proposal; files have not been selected. Avoid three variants of the same source. Record source identity/hash, provenance and rights, production type and excerpt bounds. Retain the established warm-up plus three measured runs. Generate fresh blind packs, keep model identities hidden until scoring is complete, and leave Controls 01–03 unchanged.

At six controls, reassess per-control differences and runtime trade-offs. Ten to twelve diverse controls is a pragmatic later development target, not a statistical guarantee. Independent listeners and prespecified precision/effect-size requirements are needed before stronger general claims. Repeat assessments should use newly randomized copies and preserve original scores.

## Remaining limitations

Single listener; small and deliberately selected material set; no ground-truth separation metrics; ordinal ratings; no formal significance or reliability analysis. Vocals, bass, drums and Other/Music were evaluated; dedicated piano/guitar and full-song behavior remain unevaluated.
