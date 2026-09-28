# StemLab Preliminary Results v0.1

Status: preliminary research  
Platform: Linux / CPU-only  
Benchmark protocol: 1 warm-up run + 3 measured runs per model and control  
Audio excerpt duration: 30 seconds

These results are intended to characterize practical runtime and perceived stem
quality for StemLab's target workflows. They are not intended as universal model
rankings.

## Test material

### Control 01

- ID: `control-01`
- Material: male rap / drill
- Source: Suno-generated production
- Duration: 30 s

### Control 02

- ID: `control-02`
- Material: Vietnamese female rap
- Source: original production
- AI-generated: no
- Duration: 30 s
- Format: 44.1 kHz / stereo / 16-bit PCM
- SHA-256:
  `b5e430166dfd8656ae49cd69c03279d33510cd19ee43408f2dae694420bab667`

## Runtime benchmark

Runtime values are medians of three measured CPU runs after one discarded
warm-up run.

### Control 01

| Model | Preset | Stems | Median | Min | Max | Median RTF | Peak RAM |
|---|---|---:|---:|---:|---:|---:|---:|
| `hdemucs_mmi.yaml` | `4stems` | 4 | 15.51 s | 14.69 s | 16.48 s | 0.517 | 3.25 GiB |
| `htdemucs.yaml` | `balanced` | 4 | 26.66 s | 26.34 s | 26.68 s | 0.889 | 1.97 GiB |
| `htdemucs_6s.yaml` | `6stems` | 6 | 25.46 s | 25.29 s | 25.86 s | 0.849 | 1.99 GiB |
| `htdemucs_ft.yaml` | `maximum` | 4 | 127.52 s | 122.15 s | 144.95 s | 4.251 | 2.46 GiB |
| `vocals_mel_band_roformer.ckpt` | `vocals` | 2 | 89.20 s | 87.48 s | 90.21 s | 2.973 | 3.03 GiB |

### Control 02

| Model | Preset | Stems | Median | Min | Max | Median RTF | Peak RAM |
|---|---|---:|---:|---:|---:|---:|---:|
| `hdemucs_mmi.yaml` | `4stems` | 4 | 32.66 s | 29.77 s | 33.89 s | 1.089 | 3.09 GiB |
| `htdemucs.yaml` | `balanced` | 4 | 49.21 s | 48.30 s | 50.97 s | 1.640 | 1.89 GiB |
| `htdemucs_6s.yaml` | `6stems` | 6 | 54.02 s | 47.23 s | 59.87 s | 1.801 | 1.97 GiB |
| `htdemucs_ft.yaml` | `maximum` | 4 | 191.43 s | 189.55 s | 205.16 s | 6.381 | 2.43 GiB |
| `vocals_mel_band_roformer.ckpt` | `vocals` | 2 | 123.38 s | 122.27 s | 125.75 s | 4.113 | 2.97 GiB |

## Aggregate CPU measurements

The aggregate table combines the three measured runs from each of the two
controls. It is useful as a broad CPU baseline but should not replace
per-control reporting because runtime is source-dependent.

| Model | Preset | N | Median | Min | Max | Median RTF | Peak RAM |
|---|---|---:|---:|---:|---:|---:|---:|
| `hdemucs_mmi.yaml` | `4stems` | 6 | 23.12 s | 14.69 s | 33.89 s | 0.771 | 3.25 GiB |
| `htdemucs.yaml` | `balanced` | 6 | 37.49 s | 26.34 s | 50.97 s | 1.250 | 1.97 GiB |
| `htdemucs_6s.yaml` | `6stems` | 6 | 36.55 s | 25.29 s | 59.87 s | 1.218 | 1.99 GiB |
| `htdemucs_ft.yaml` | `maximum` | 6 | 167.25 s | 122.15 s | 205.16 s | 5.575 | 2.46 GiB |
| `vocals_mel_band_roformer.ckpt` | `vocals` | 6 | 106.24 s | 87.48 s | 125.75 s | 3.541 | 3.03 GiB |

## Source-dependent runtime

The benchmark shows that equal-duration inputs can require substantially
different processing time.

For example:

| Model | Control 01 | Control 02 |
|---|---:|---:|
| `hdemucs_mmi.yaml` | 15.51 s | 32.66 s |
| `htdemucs.yaml` | 26.66 s | 49.21 s |
| `htdemucs_6s.yaml` | 25.46 s | 54.02 s |
| `htdemucs_ft.yaml` | 127.52 s | 191.43 s |
| `vocals_mel_band_roformer.ckpt` | 89.20 s | 123.38 s |

Runtime therefore should not be treated as a function of audio duration alone.

## Blind Vocal evaluation

Blind Vocal is a subjective vocal-extraction test.

Candidates are anonymized as A-E during scoring. Model identities are revealed
only after all criteria have been scored.

Scale:

- 1 = poor
- 2 = weak
- 3 = acceptable
- 4 = good
- 5 = excellent

Criteria:

- vocal isolation
- vocal integrity
- artifact control
- low-level detail
- remix usability

Blind Vocal evaluates only the vocal stem. It must not be interpreted as a
complete evaluation of multi-stem separation quality.

## Blind Vocal — Control 01

| Model | Isolation | Integrity | Artifacts | Detail | Remix | Mean |
|---|---:|---:|---:|---:|---:|---:|
| `vocals_mel_band_roformer.ckpt` | 5 | 4 | 4 | 3 | 5 | 4.2 |
| `htdemucs_6s.yaml` | 4 | 4 | 4 | 4 | 5 | 4.2 |
| `htdemucs.yaml` | 3 | 4 | 3 | 3 | 3 | 3.2 |
| `htdemucs_ft.yaml` | 3 | 3 | 2 | 3 | 4 | 3.0 |
| `hdemucs_mmi.yaml` | 2 | 3 | 2 | 3 | 4 | 2.8 |

## Blind Vocal — Control 02

| Model | Isolation | Integrity | Artifacts | Detail | Remix | Mean |
|---|---:|---:|---:|---:|---:|---:|
| `vocals_mel_band_roformer.ckpt` | 5 | 4 | 4 | 4 | 3 | 4.0 |
| `htdemucs_6s.yaml` | 3 | 3 | 4 | 4 | 4 | 3.6 |
| `htdemucs.yaml` | 2 | 3 | 3 | 4 | 2 | 2.8 |
| `htdemucs_ft.yaml` | 3 | 3 | 3 | 3 | 2 | 2.8 |
| `hdemucs_mmi.yaml` | 3 | 3 | 2 | 3 | 3 | 2.8 |

## Cross-control Blind Vocal summary

| Model | Control 01 | Control 02 | Mean |
|---|---:|---:|---:|
| `vocals_mel_band_roformer.ckpt` | 4.2 | 4.0 | 4.1 |
| `htdemucs_6s.yaml` | 4.2 | 3.6 | 3.9 |
| `htdemucs.yaml` | 3.2 | 2.8 | 3.0 |
| `htdemucs_ft.yaml` | 3.0 | 2.8 | 2.9 |
| `hdemucs_mmi.yaml` | 2.8 | 2.8 | 2.8 |

## Preliminary observations

### Vocal isolation

`vocals_mel_band_roformer.ckpt` received a vocal-isolation score of 5/5 on
both controls.

Across the first two controls it also produced the most consistent overall
Blind Vocal scores: 4.2 and 4.0.

### Multi-stem trade-off

`htdemucs_6s.yaml` scored 4.2 and 3.6 in Blind Vocal while also producing six
stems.

On Control 02 its median CPU runtime was 54.02 s compared with 123.38 s for
the two-stem MelBand RoFormer vocal model.

This makes it an important candidate for practical multi-stem workflows, but
the current Blind Vocal results do not evaluate the quality of its non-vocal
stems.

### Maximum preset

`htdemucs_ft.yaml` had the highest runtime in both controls but did not achieve
higher Blind Vocal scores in these tests.

This result should be tested on additional material before drawing broader
conclusions.

## Limitations

This dataset is intentionally small.

Current limitations include:

- two 30-second controls
- one human listener
- one workstation
- CPU-only execution
- Blind Vocal evaluates vocals only
- no ground-truth reference stems for these real mixed recordings
- subjective scores should not be interpreted as SDR or SI-SDR
- different model families produce different numbers of stems

Accordingly, these findings are preliminary and should not be presented as a
universal model ranking.

## Next steps

1. Add a third representative control source.
2. Repeat Blind Vocal using the same protocol.
3. Expand full-stem QC for bass, drums, other and additional stems.
4. Add reference-stem fixtures for objective quality metrics.
5. Use accumulated evidence to define practical StemLab product presets.
