# StemLab Research Specification v0.1

Status: Draft / research in progress.

## Scope

StemLab investigates practical music source separation on CPU-only consumer hardware for producers who do not have a dedicated AI-capable GPU, do not want to depend on cloud processing, may need offline operation, and want access to modern freely available separation models.

Linux is the v1 reference research platform.

## RQ1 — Primary Research Question

> Which freely available music source-separation models provide the most practical trade-offs between separation quality, processing time and computational resource requirements when executed locally on CPU-only consumer hardware?

The study does not seek a universal "best model." It seeks to characterize useful trade-offs under constrained local compute.

## RQ1.1 — Separation Quality

How does separation quality differ among selected modern architectures/checkpoints on identical source material?

Candidate families:
- Hybrid Transformer Demucs
- MelBand RoFormer
- BS-RoFormer
- MDX
- MDX23C

Use objective metrics where ground-truth stems exist and structured listening evaluation for real-world material.

## RQ1.2 — Computational Cost

Measure:
- wall-clock runtime
- real-time factor (RTF)
- peak RAM
- model-loading time
- checkpoint storage requirement

RTF = processing time / source audio duration.

## RQ1.3 — Quality versus Compute

How much useful quality is gained by more expensive models/configurations?

Examples:
- HTDemucs vs HTDemucs-FT
- selected RoFormer checkpoints
- overlap
- shifts
- segment settings
- ensembles where relevant

## RQ1.4 — Source Dependency

Do models differ systematically by task/material?

Investigate, where feasible:
- vocals
- drums
- bass
- guitar
- dense/sparse mixes
- acoustic/electronic material
- male/female vocals
- heavily processed vocals
- AI-generated music

## RQ1.5 — Multi-Stage Workflows

Can combinations of specialized models provide useful improvements over a single general-purpose pass, after accounting for computational cost?

Example:
mixture -> specialized vocal separation -> instrumental remainder -> multi-stem separation.

## RQ1.6 — Practical Offline Operation

After application and checkpoints are installed:
1. disconnect network
2. launch StemLab
3. load local audio
4. run installed model
5. export stems
6. run another installed model
7. execute batch/recipe

Core separation must not depend on network access.

## Reproducibility

Each official run should record at minimum:
- StemLab version
- OS/kernel
- CPU
- RAM
- Python/PyTorch/backend versions
- model architecture
- exact checkpoint and hash
- input hash
- input format/sample rate
- inference parameters
- output format
- runtime
- RTF
- peak memory
- evaluation metrics

Results lacking sufficient provenance do not enter the official benchmark.

## Reference Hardware

v1 intentionally uses one fixed Linux CPU-only reference workstation.

Absolute timings describe that machine only. Relative compute costs can be compared within the controlled environment. Cross-machine performance claims require later standardized community or multi-system testing.

## Evaluation Material

### Controlled dataset
Material with ground-truth isolated sources for objective evaluation.

### Real-world producer material
Finished mixes for artifact/usability evaluation. Material without ground truth must not be presented as objective separation-accuracy evidence.

## CPU-Efficient Experimental Funnel

### Stage A — Screening
Fixed 10–30 s excerpts; many models/settings.

### Stage B — Controlled Benchmark
Promising configurations on the larger controlled set.

### Stage C — Full-Track Validation
Finalists only, for practical runtime and production behavior.

Cache completed runs by input hash + checkpoint hash + inference configuration.

## Success Criteria

A v1 user should be able to:
1. install on a supported Linux CPU-only machine
2. install supported models
3. disconnect from the Internet
4. separate audio successfully
5. understand the evidence behind model/profile recommendations
6. reproduce a published benchmark configuration
7. inspect benchmark evidence
8. queue multiple jobs unattended

An independent user should be able to reproduce the documented experiment on comparable hardware.
