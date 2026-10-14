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

Producer queue UX / HMI target and implementation gates: [docs/PRODUCER-QUEUE-UX.md](docs/PRODUCER-QUEUE-UX.md).

## October 2026 — Producer GUI Alpha (implemented ahead of schedule)

- [x] PySide6 / Qt producer interface
- [x] Drag-and-drop import and per-file presets
- [x] CPU batch processing, process progress and cancellation
- [x] Stem preview and Bitwig-compatible source/stem drag-out
- [x] Four-stem WAV metadata validation and synthetic six-part drum validation
- [x] Existing-output inspection and safe non-overwrite behavior
- [x] Eight persistent appearance themes
- [x] Source-checkout GUI launcher and Linux Mint desktop menu integration
- [ ] Revalidate six real Drum Parts WAVs end-to-end
- [ ] Verify fresh Linux installation (clean-machine acceptance)
- [x] Verify real Balanced CPU inference with network namespace disabled
- [x] Validate four real Balanced offline output WAV metadata (44.1 kHz, stereo, 10.00 s, PCM 16-bit)
- [x] Verify cached-model inference with read-only cache (Balanced, Linux mount + network namespaces)
- [ ] Produce a distributable, reproducible Linux package
- [ ] Offline-aware model manager (future capability)

Acceptance evidence as of 2026-10-14: 22 producer GUI regression tests were
reported passing on Linux Mint, plus two desktop-installer tests. A real
three-file CPU batch (Drum Parts, Fast, Balanced) generated 14 WAVs. Four-stem
outputs and Bitwig drag/preview were checked in a live producer workflow.
A new real six-part metadata validation run and fresh-machine installation
remain open. On 2026-10-14, a 10-second synthetic stereo WAV was separated
using `balanced` / `htdemucs.yaml`, audio-separator 0.47.0 and Python 3.12.14
inside `sudo unshare --net`, running inference as the normal user. CPU inference
finished in 12 seconds and emitted four WAV files (Bass, Drums, Other, Vocals)
using the existing ~1.9 GB cache. This confirms one real network-disconnected
inference path, not full GUI/preset offline acceptance. The cache was writable. A subsequent network-isolated Balanced run produced
four WAVs independently checked with ffprobe: PCM 16-bit, 44.1 kHz, stereo,
10.00 seconds each. A third Balanced separation completed on 2026-10-14
inside isolated mount and network namespaces with a bind-mounted read-only
model cache; four stems were produced and the local command reported PASS.
The read-only check applies to the namespace, not persistent host mounts.
Synthetic tests do not replace release acceptance. See `docs/PRODUCER-QUEUE-UX.md`.

## January 2027 — Producer UX Follow-up

- [ ] Resolve findings from multi-file desktop visual acceptance
- [ ] Evaluate persistent queue restoration only if workflows require it
- [ ] Review UI accessibility and scaling
- [ ] Validate extended/overnight producer sessions

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
