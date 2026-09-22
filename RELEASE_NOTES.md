# 808SGN Stem Lab v0.1.0 — Linux CPU Benchmark

First public 808SGN Stem Lab release.

Created by **MTM DSP** and published by **808SGN Labs**.

## Included

- Reproducible Linux installation using `uv`
- Seven task-focused separation presets
- CPU benchmark on a Ryzen 7 5700G
- Four-stem Demucs comparison
- MelBand RoFormer vocal workflow
- Specialist DrumSep and vocal de-reverb workflows
- Suno native-stem reconstruction findings
- Bitwig import and comparison guidance

## Main result

`hdemucs_mmi.yaml` is the default four-stem model. It completed a 130.29-second test song in 90 seconds, achieved 38.72 dB reconstruction SNR, and was audibly indistinguishable from standard HTDemucs in this test.

## Known limitations

- Results come from one electronic test track and one CPU-only Linux machine.
- Reconstruction SNR is not a universal perceptual-quality score.
- Output sample rate was 44.1 kHz even when the source was 48 kHz.
- GPU performance is not yet benchmarked.
- No GUI is included in v0.1.0.
