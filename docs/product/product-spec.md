# StemLab Product Specification v0.1

## Product principle

Publish the science. Make the implementation of that knowledge convenient.

## Free / Research Core

Candidate free functionality:
- benchmark/research framework
- published methodology and results
- model/checkpoint provenance
- CLI
- basic local single-file separation
- enough functionality to reproduce published claims

## Pro candidate functionality

Commercial value should come primarily from saved producer time:
- native polished GUI
- persistent batch/overnight queue
- recipes
- model chaining
- smart task/profile selection
- advanced A/B/QC workflow
- queue recovery/retry
- organized DAW-oriented export
- advanced workflow presets

Separation quality should not be artificially degraded for free users.

## User modes

### Producer Mode
Task-oriented:
- extract vocals
- remove vocals
- full mix separation
- fast CPU
- balanced
- highest practical CPU quality

### Research Mode
Expose:
- architecture/checkpoint
- segment/overlap/shifts
- backend/version
- RTF/RAM
- benchmark evidence
- experiment metadata

## CPU profiles

Potential evidence-derived profiles:
- FAST
- BALANCED
- QUALITY
- OVERNIGHT

## Offline requirement

Once application and selected models are installed, core separation must work without Internet access.

Model downloads, update checks and online metadata are separate from inference.
