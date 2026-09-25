# StemLab Public Roadmap

## September 24–30, 2026 — v0.1 CLI Foundation
- Freeze initial research scope
- Clean current CLI
- Define experiment/config format
- Separate UI, job/recipe layer, separator backends and audio I/O

## October 1–11 — Benchmark Harness
- Input/checkpoint hashing
- Capture versions and environment
- Runtime and real-time-factor measurement
- Peak memory measurement
- Result caching
- Machine-readable results

## October 12–25 — Benchmark Suite v0.1
- Select legally usable ground-truth material
- Define fixed 10–30 second excerpts
- Implement initial objective metrics
- Document benchmark protocol

## October 26–November 15 — First Model Study
Initial candidates:
- HTDemucs
- HTDemucs-FT
- HTDemucs 6S where relevant
- selected MelBand RoFormer checkpoint(s)
- selected MDX/RoFormer alternatives

## November 16–30 — Analysis
- Quality versus CPU cost
- Repeat questionable results
- Full-song validation of finalists
- Draft model guide

## December 1–14 — Recipe Research
- Single-model baselines
- Multi-stage separation
- Vocal-first workflows
- Instrumental re-separation
- CPU profiles derived from evidence

## December 15–31 — Research Preview v0.5
- Methodology
- Raw CSV/JSON results
- Model registry
- Reproducibility instructions
- Research preview documentation

## January 2027 — GUI Alpha
- PySide6/Qt
- Batch/overnight queue
- Offline-aware model manager
- Producer and Research modes

## February 2027 — Release Candidate
- Producer testing
- Offline testing
- Queue recovery
- UX/documentation
- Bug fixing

## March 2027 — v1.0
- Technical report
- Benchmark release
- Polished GUI
- Flagship demonstration/video

Cross-platform support may follow, but Windows/macOS benchmarking is outside the v1 research scope.
