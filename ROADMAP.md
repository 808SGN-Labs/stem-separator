# StemLab Public Roadmap

StemLab is a Linux-first, local/offline stem-separation research and production
workflow built around reproducible benchmarking and practical producer use cases.

## September 2026 — v0.1 Foundation

### Completed

- [x] Clean CLI wrapper
- [x] Shared model cache
- [x] Preset-based separation
- [x] Reproducible experiment/config format
- [x] Input hashing
- [x] Model/checkpoint provenance capture
- [x] Software/environment capture
- [x] End-to-end runtime measurement
- [x] Real-time-factor measurement
- [x] Peak memory measurement
- [x] Machine-readable `result.json`
- [x] Warm-up versus measured-run tagging
- [x] Official protocol: 1 warm-up + 3 measured runs
- [x] Per-control benchmark summaries
- [x] Aggregate cross-control summaries
- [x] Control 01 benchmark
- [x] Control 02 benchmark
- [x] Blind Vocal listening workflow
- [x] QC GUI
- [x] Multi-pack Blind Vocal selector
- [x] Preliminary Results v0.1

### Current baseline models

- `hdemucs_mmi.yaml`
- `htdemucs.yaml`
- `htdemucs_6s.yaml`
- `htdemucs_ft.yaml`
- `vocals_mel_band_roformer.ckpt`

## October 2026 — Expand Evidence Set

- [ ] Add Control 03
- [ ] Increase source diversity
- [ ] Repeat Blind Vocal using the same protocol
- [ ] Full-stem QC for bass, drums, vocals and other
- [ ] Define stem-specific listening criteria
- [ ] Repeat questionable/high-variance measurements
- [ ] Document source-dependent runtime behavior
- [ ] Add benchmark result export suitable for publication

Control sources should represent materially different production conditions,
vocal types and musical content rather than repeated variants of one track.

## October–November 2026 — Objective Quality Research

- [ ] Select legally usable reference material with known stems
- [ ] Build fixed reference-stem fixtures
- [ ] Add objective metrics where ground truth exists
- [ ] Evaluate SDR / SI-SDR or appropriate alternatives
- [ ] Compare objective metrics with blind listening results
- [ ] Document cases where reconstruction metrics and perceived isolation diverge

Real mixed recordings without reference stems remain useful for practical
listening tests, but they must not be presented as ground-truth SDR benchmarks.

## November 2026 — Model and Recipe Study

- [ ] Add selected MDX23C candidate
- [ ] Evaluate additional MelBand / BS-RoFormer candidates
- [ ] Test vocal-first workflows
- [ ] Test instrumental re-separation
- [ ] Evaluate multi-stage specialist workflows
- [ ] Full-song validation of finalists
- [ ] Draft evidence-based model guide

The goal is not to declare one universal model winner. StemLab should identify
models and recipes appropriate to specific producer tasks.

## December 2026 — Research Preview

- [ ] Publish benchmark methodology
- [ ] Publish normalized result tables
- [ ] Publish model registry
- [ ] Publish reproducibility instructions
- [ ] Publish limitations and known confounders
- [ ] Produce StemLab research/demo video

The public research layer should explain why particular StemLab workflows and
presets exist.

## January 2027 — Producer GUI Alpha

- [ ] PySide6 / Qt producer interface
- [ ] Drag-and-drop input
- [ ] Evidence-based task presets
- [ ] Separation progress and cancellation
- [ ] Stem audition
- [ ] Aligned WAV export
- [ ] Bitwig-friendly drag/export workflow
- [ ] Batch / overnight queue
- [ ] Offline-aware model manager

Research/QC tools and the producer-facing workflow should remain separable.

## February 2027 — Release Candidate

- [ ] Producer testing
- [ ] Offline testing
- [ ] Queue recovery
- [ ] Error/recovery UX
- [ ] Packaging
- [ ] Documentation
- [ ] Bug fixing

## March 2027 — v1.0

- [ ] Technical report
- [ ] Benchmark release
- [ ] Polished Linux GUI
- [ ] Flagship demonstration/video

Cross-platform support may follow, but Windows/macOS benchmarking remains
outside the v1 research scope.
