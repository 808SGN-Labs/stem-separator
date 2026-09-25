# Benchmark Protocol

Status: Draft placeholder.

Every official experiment should be reproducible from a configuration file.

Example:

```yaml
experiment: demucs-baseline-001

dataset:
  name: TBD
  split: test

model:
  engine: demucs
  name: htdemucs_ft

inference:
  segment: 7.8
  overlap: 0.25
  shifts: 1

output:
  format: wav
  subtype: float32

metrics:
  - runtime
  - rtf
  - peak_ram
  - sdr
  - si_sdr

environment:
  capture: true
```

## Required output
Each run should generate machine-readable metadata/results plus human-readable logs.

## Cache key
At minimum:
- input content hash
- checkpoint/model hash
- inference configuration
- relevant engine version

Do not silently reuse a cached result if any relevant component changed.
