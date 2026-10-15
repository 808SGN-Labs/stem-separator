# 808SGN Stem Lab

[![Historical benchmark](https://img.shields.io/badge/benchmark-v0.1.0-7c3aed)](RELEASE_NOTES.md)
[![Linux](https://img.shields.io/badge/platform-Linux-fcc624)](#installation)
[![Code license](https://img.shields.io/badge/code-MIT-green)](LICENSE-CODE)
[![Docs license](https://img.shields.io/badge/docs-CC%20BY%204.0-blue)](LICENSE-DOCS)

**Private, local AI stem separation for Linux producers.**

Reproducible CPU benchmarks and task-focused wrappers for local music stem
separation. Built by **MTM DSP** and published by **808SGN Labs** for producers
who want private, offline processing rather than another upload service.

## Quick start

```bash
git clone https://github.com/808SGN-Labs/stemlab.git
cd stemlab
chmod +x scripts/install.sh scripts/stem-separate
./scripts/install.sh
./scripts/stem-separate 4stems /path/to/song.wav
```

See all presets:

```bash
./scripts/stem-separate --help
```

This project is an independent benchmark and workflow wrapper. Separation is
performed by the MIT-licensed
[`audio-separator`](https://github.com/nomadkaraoke/python-audio-separator)
project using models made available through the UVR ecosystem. Model weights
are downloaded separately and may have their own terms. 808SGN is not
affiliated with the upstream projects.

**Test date:** 22 September 2026  
**Platform:** Linux Mint 21.3, Ryzen 7 5700G, 60 GB RAM, CPU inference  
**Software:** `audio-separator` 0.47.0, Python 3.12, FFmpeg 4.4.2  
**Test source:** 130.29-second stereo, 48 kHz, 24-bit Suno-generated WAV

## Short version

Local stem separation on Linux is already practical for remixing and production
without dedicated ML acceleration.

Current evidence suggests different models are useful for different tasks:

- `hdemucs_mmi.yaml` is the fastest four-stem option in the current CPU tests
- `htdemucs.yaml` remains a useful balanced four-stem reference
- `htdemucs_6s.yaml` is a strong multi-stem candidate when six-way separation is useful
- `vocals_mel_band_roformer.ckpt` is the strongest dedicated vocal-isolation candidate
  in the current Blind Vocal tests
- `htdemucs_ft.yaml` is substantially slower and has not yet shown a consistent
  vocal-quality advantage in the controlled tests
- specialist drum and de-reverb models remain optional second-stage tools

The latest listening pilot covers three 30-second controls, one listener and
four categories: vocals, bass, drums and Other/Music (270 criterion ratings).
The benchmark workflow uses a warm-up and three measured CPU runs per model.

Observed listening leaders by stem: vocals — MelBand RoFormer (3.87/5),
bass — htdemucs_ft (4.07/5), drums — htdemucs (4.33/5),
Other/Music — htdemucs_6s and htdemucs_ft (both 3.07/5).
These are stem-specific pilot scores, **not** a universal model ranking.
The RoFormer instrumental residual is not directly comparable with a dedicated
Demucs Other stem.

`balanced` (htdemucs) remains the CPU-first general default; `vocals` and
`maximum` are task-specific alternatives. See the
[three-control listening consolidation](research/listening-consolidated-2026-10-08.md)
and [preliminary CPU benchmark](research/results-v0.1.md).

Private listening audio, scores and randomized model mappings are excluded from
publication. The research results are preliminary, with no independent listeners
or statistical significance claim.

## Why this test exists

Suno can export native stems, and commercial services such as Voice.ai can separate uploaded audio. The goal here was different:

1. Run everything locally on Linux.
2. Keep the source audio private.
3. Compare multiple models using the same song.
4. Measure reconstruction, speed and stem behavior—not just judge model names.
5. Find a workflow that is useful inside a DAW, not merely impressive in a demo.

## Test machine

| Component | Specification |
|---|---|
| OS | Linux Mint 21.3 x86_64 |
| Kernel | 5.15 |
| CPU | AMD Ryzen 7 5700G, 8 cores / 16 threads |
| RAM | 60 GB |
| GPU | AMD Cezanne integrated graphics |
| Acceleration | None; CPU mode |
| DAW | Bitwig Studio |
| Source | 130.29 s stereo WAV, 48 kHz, 24-bit |

The timings below are therefore conservative. A supported NVIDIA GPU should be substantially faster.

## Installation (private Linux alpha)

The [v0.2.0-alpha.1 private Producer candidate notes](docs/RELEASE-NOTES-v0.2.0-alpha.1.md)
give the exact source-only ZIP recipe. Historical v0.1.0 benchmark release
notes remain in [RELEASE_NOTES.md](RELEASE_NOTES.md).

Prerequisites: Linux x86_64, Python 3.12 available to `uv`, `uv` on `PATH`,
FFmpeg including `ffprobe` on `PATH`, matching Python 3.12 development headers,
working C/C++ compilers and `make`, and `libxcb-cursor.so.0` for the Qt XCB GUI.
On Linux Mint 22, the missing system packages in the mint1 acceptance run were
`python3.12-dev`, `build-essential`, and `libxcb-cursor0`; install them with your
system package manager before running StemLab. The installer checks these
prerequisites and prints a diagnostic; it does not install system packages.
Install Python dependencies while connected;
the installer does not download models, install system packages, or invoke
`sudo`. From a checkout:

```bash
bash scripts/install.sh
"${XDG_DATA_HOME:-$HOME/.local/share}/808sgn-stem-lab/app/scripts/stemlab-gui"
bash "${XDG_DATA_HOME:-$HOME/.local/share}/808sgn-stem-lab/app/scripts/install-desktop.sh"  # optional menu entry
```

The installer creates one private Python environment for the GUI and CPU
separator in `$XDG_DATA_HOME/808sgn-stem-lab` (or `~/.local/share`), and copies
the GUI, wrapper, launcher, and code license into `app/`. The menu entry points
to this installed copy, so the checkout can move. It refuses to replace a
foreign desktop entry or unowned app directory. No system-wide files are
installed. Remove the matching menu entry with
`bash "${XDG_DATA_HOME:-$HOME/.local/share}/808sgn-stem-lab/app/scripts/install-desktop.sh" --remove`;
this leaves the environment,
outputs, and model cache untouched. `STEM_LAB_GUI_PYTHON` can override the
launcher interpreter for development.

Models are **not bundled**. The wrapper uses
`${XDG_CACHE_HOME:-$HOME/.cache}/808sgn-stem-lab/models` by default, or
`STEM_LAB_MODELS`. The first run of an uncached model may download weights;
prepare an authorized cache before disconnected use. The offline tests use
stubs and do not prove real model inference. Direct Python package versions
are pinned in `scripts/install.sh`, but transitive dependencies and the Python
patch version are not yet locked. One real clean installation and installed-GUI
startup were reported on Linux Mint 22; see
[Producer Alpha acceptance](docs/PRODUCER-ALPHA-ACCEPTANCE.md) for the evidence
and remaining native desktop checks. The CPU-only dependency request also
resolved CUDA-related transitive packages on mint1; the installer does not
currently optimize that dependency closure.

### Offline installer preflight

The installer can be checked without downloading dependencies or changing
the actual user installation. The tests replace `uv` and `ffmpeg` with
temporary stubs and redirect `XDG_DATA_HOME` to a temporary directory:

```bash
python3 -m unittest discover -s tests -p 'test_install_preflight.py' -v
```

These tests verify installation paths, pinned direct dependencies, native-build
and Qt XCB prerequisite diagnostics, the copied GUI, a relocatable desktop
entry, and missing-FFmpeg handling. They do **not**
prove fresh-system compatibility, successful real dependency installation,
Qt audio playback, or offline inference.

### Isolated offline wrapper contract test

Test wrapper routing without networking, downloads or actual model inference:

```bash
python3 -m unittest discover -s tests -p 'test_offline_wrapper.py' -v
```

This uses a disposable stub `audio-separator`, temporary input/output and
model-cache paths. It checks command arguments and failure behavior; it does
**not** demonstrate that the real separator can infer offline from cached
weights. That still requires a sandboxed real run with a preloaded model cache.

## Manual installation (advanced)

The quick-start installer above is recommended. If you use the manual location below, set `STEM_LAB_VENV` so the wrapper can find it. Export this variable again in each new terminal session before using the wrapper.

Install FFmpeg:

```bash
sudo apt update
sudo apt install -y ffmpeg
```

Install `uv`, then create an isolated environment:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

mkdir -p "$HOME/audio-separator"
cd "$HOME/audio-separator"

export STEM_LAB_VENV="$HOME/audio-separator/.venv"

uv venv --python 3.12
source .venv/bin/activate
uv pip install "audio-separator[cpu]"
```

With version 0.47.0, `audioread` was missing from the resolved installation on this machine. The fix was:

```bash
uv pip install audioread
```

Verify the environment:

```bash
audio-separator --env_info
```

## Recommended folder layout

```text
StemSeparator/
├── models/
└── separated/
```

Models can be shared between jobs. Outputs should go into model-specific subfolders so comparisons do not overwrite each other.

## Reusable command pattern

The shell variable must be assigned before it is expanded. Do not place the assignment and the command on the same line like `INPUT=... audio-separator "$INPUT"`; in that form, the current shell expands `$INPUT` before applying the temporary assignment.

```bash
INPUT='/path/to/song.wav'
MODEL_DIR='/path/to/StemSeparator/models'
OUTPUT="$(dirname "$INPUT")/htdemucs"

mkdir -p "$OUTPUT"

audio-separator "$INPUT" \
  --model_filename htdemucs.yaml \
  --model_file_dir "$MODEL_DIR" \
  --output_dir "$OUTPUT" \
  --output_format WAV
```

MP3, WAV and other FFmpeg-supported formats can be used as input. Lossless WAV or FLAC is preferable when available because lossy artifacts can become more audible after separation.

## Results

### Model overview

| Model | Output | CPU time | Reconstruction SNR | Practical verdict |
|---|---:|---:|---:|---|
| `hdemucs_mmi.yaml` | 4 stems | 1:30 | 38.72 dB | Fastest high-quality default candidate |
| `htdemucs.yaml` | 4 stems | 2:40 | 37.28 dB | Excellent balanced reference |
| `htdemucs_ft.yaml` | 4 stems | 8:37 | 27.40 dB | Slow fine-tuned alternative; audition on difficult material |
| `htdemucs_6s.yaml` | 6 stems | 1:56 | 22.71 dB | Experimental; extra stems were weak on this synth-heavy track |
| `vocals_mel_band_roformer.ckpt` | vocals + other | about 10 min on another 218.6 s test | 66.5 dB | Best dedicated vocal split tested |
| `MDX23C-DrumSep-aufr33-jarredou.ckpt` | 6 drum parts | 7:59 | 36.12 dB | Excellent advanced tool after isolating drums |
| `deverb_bs_roformer_8_384dim_10depth.ckpt` | dry vocal + reverb | 33:10 | 70.00 dB | Technically clean but extremely slow specialist pass |

Reconstruction SNR measures how closely the summed stems reproduce the aligned input. It is useful for detecting complementarity and technical residue, but it is **not a complete perceptual quality score**. A model can reconstruct perfectly while still placing sounds in the wrong stem, and a model with lower reconstruction SNR can sometimes produce a more useful isolated stem.

### HDemucs MMI: the speed winner

`hdemucs_mmi.yaml` completed the four-stem split in **1:30**, or about 0.69× real time. It was 44% faster than standard HTDemucs while slightly exceeding its reconstruction score:

- Raw reconstruction SNR: **38.72 dB**
- Gain-fitted reconstruction SNR: **38.74 dB**
- Fitted gains: bass **1.00011**, drums **0.99981**, other **1.00455**, vocals **1.00074**

Compared with standard `htdemucs.yaml`, the correlations were:

| Stem | Correlation with standard HTDemucs |
|---|---:|
| Bass | 0.99276 |
| Drums | 0.99536 |
| Other | 0.94454 |
| Vocals | 0.99643 |

The bass output was not materially more low-frequency focused than standard HTDemucs. MMI placed **82.26%** of measured bass spectral energy below 100 Hz versus **82.13%** for standard HTDemucs. Their bass RMS levels differed by less than 0.01 dB. On this source, MMI is better understood as a faster four-stem alternative—not a uniquely bass-focused extractor.

The objective results make MMI the strongest default candidate. A final perceptual decision still requires checking its `other` stem, where the models differed most.

### Standard HTDemucs: the balanced reference

`htdemucs.yaml` produced bass, drums, other and vocals in 2:40. Compared with the much slower fine-tuned model, the stem correlations were:

| Stem | Correlation with `htdemucs_ft` |
|---|---:|
| Bass | 0.99595 |
| Drums | 0.99741 |
| Other | 0.96895 |
| Vocals | 0.99753 |

For this song, the differences were small enough that the regular model remains an excellent reference. Use the fine-tuned model only when the standard or MMI result has audible leakage, or when preparing a final production where the extra wait is justified.

### Fine-tuned HTDemucs

`htdemucs_ft.yaml` required 8:37 for the same 130-second file. Its bass stem was strongly low-frequency focused, and the four stems remained close to unity gain when fitted back to the source.

The lower reconstruction SNR does **not** automatically mean the individual stems sound worse. It means the regular model happened to produce a more complementary four-way decomposition on this source. Final selection must still be made by listening to leakage and artifacts in context.

### MelBand RoFormer for vocals

`vocals_mel_band_roformer.ckpt` produced the cleanest two-stem reconstruction in the test:

- Raw reconstruction SNR: **66.5 dB**
- Gain-fitted reconstruction SNR: **68.6 dB**
- Vocal correlation with fine-tuned Demucs: **0.9945**

This is the preferred model when the actual requirement is only:

- vocals
- instrumental / other

Do not run a four- or six-stem model merely because it produces more files. Every additional category is another opportunity for leakage.

### Six-stem HTDemucs

`htdemucs_6s.yaml` adds guitar and piano to bass, drums, other and vocals. On this electronic test track:

- Guitar RMS: approximately **−62.4 dBFS**
- Piano RMS: approximately **−42.4 dBFS**
- Guitar was effectively empty.
- Piano contained only quiet fragments.

The extra labels did not create useful musical content. Six-stem separation makes sense when the mix clearly contains identifiable guitar or piano. It should remain an optional preset, not the default.

### Dedicated drum separation

The drum workflow was deliberately two-stage:

1. Separate the full mix using `htdemucs.yaml`.
2. Feed only the isolated drum stem into `MDX23C-DrumSep-aufr33-jarredou.ckpt`.

Command:

```bash
INPUT='/path/to/song_(Drums)_htdemucs.wav'
MODEL_DIR='/path/to/StemSeparator/models'
OUTPUT="$(dirname "$INPUT")/drumsep"

mkdir -p "$OUTPUT"

audio-separator "$INPUT" \
  --model_filename MDX23C-DrumSep-aufr33-jarredou.ckpt \
  --model_file_dir "$MODEL_DIR" \
  --output_dir "$OUTPUT" \
  --output_format WAV
```

It generated kick, snare, toms, hi-hat, ride and crash. Energy distribution for this minimal beat was:

| Drum part | Energy share | RMS |
|---|---:|---:|
| Kick | 95.652% | −24.02 dBFS |
| Snare | 3.874% | −37.95 dBFS |
| Hi-hat | 0.465% | −47.09 dBFS |
| Toms | 0.0018% | −71.28 dBFS |
| Ride | 0.0039% | −67.92 dBFS |
| Crash | 0.0028% | −69.35 dBFS |

That result is believable: the song is dominated by kick, with smaller snare and hi-hat content. The nearly empty tom, ride and crash files are not evidence of failure. They simply have little relevant content to extract.

The six drum parts reconstructed their drum input at **36.12 dB SNR** raw and **38.29 dB** after gain fitting.

## Suno native stems versus local separation

The tested Suno export contained nine stems:

- lead vocals
- backing vocals
- drums
- bass
- guitar
- keyboard
- percussion
- synth
- woodwinds

These stems were approximately 307 ms shorter than the downloaded master and did not sum back to it:

- Raw sum reconstruction SNR: **−0.63 dB**
- Gain-fitted reconstruction SNR: approximately **2.07 dB**

The fitted gains also behaved unlike complementary source separation. The practical conclusion is that Suno native stems should be treated as regenerated or reinterpreted production parts—not phase-accurate components of the exact master.

Suno stems remain useful when their categories are more musically valuable, especially lead versus backing vocals. But avoid casually layering them with locally separated stems and expecting perfect alignment or cancellation.

## Bitwig workflow

For valid comparison:

1. Place every stem at exactly the same timeline position.
2. Use **Raw** playback mode; disable tempo stretching.
3. Set all stem faders to **0 dB** for reconstruction tests.
4. Mute the original while summing the stems.
5. Do not normalize individual stems.
6. Loudness-match model alternatives before judging quality.

After the comparison, mix normally. The unity-gain rule is only for testing reconstruction.

Do not play the original drums underneath the summed DrumSep parts unless intentional layering is the goal. The DrumSep sum already represents the original isolated drum stem.

## Output sample-rate warning

The 48 kHz source produced 44.1 kHz outputs in these tests. The duration stayed correct, but this matters in a 48 kHz production session. Check the rendered files and let the DAW perform one controlled resampling step, or configure the separator explicitly if the installed version and architecture expose a suitable sample-rate option.

## A sensible production workflow

### Fast/default

Use `hdemucs_mmi.yaml` for the fastest high-quality four-stem pass, subject to checking its `other` stem. Use `htdemucs.yaml` as the balanced reference. Both produce:

- bass
- drums
- vocals
- other / music

### Vocal-focused

Use `vocals_mel_band_roformer.ckpt` when clean vocals and instrumental are the priority.

### Maximum audition

Try `htdemucs_ft.yaml` only when the standard model has audible problems. More compute does not guarantee a more useful result on every track.

### Optional specialist passes

- Run DrumSep only on an already isolated drum stem.
- Run vocal de-reverb only when reverb is actually obstructing the remix.
- Try six-stem Demucs when guitar or piano is genuinely important.
- Avoid automatic denoising of already clean AI-generated audio; it can remove transients and texture.

## Vocal de-reverb

A specialist de-reverb pass was run on the isolated RoFormer vocal:

```bash
INPUT='/path/to/song_(vocals)_vocals_mel_band_roformer.wav'
MODEL_DIR='/path/to/StemSeparator/models'
OUTPUT="$(dirname "$INPUT")/vocal_deverb"

mkdir -p "$OUTPUT"

audio-separator "$INPUT" \
  --model_filename deverb_bs_roformer_8_384dim_10depth.ckpt \
  --model_file_dir "$MODEL_DIR" \
  --output_dir "$OUTPUT" \
  --output_format WAV
```

The model produced a `noreverb` vocal and a separate reverb component. Both outputs retained the full 130.29-second duration at 44.1 kHz and 24-bit.

| Measurement | Result |
|---|---:|
| CPU separation time | 33:10 |
| Speed versus real time | 15.3× slower than real time |
| Raw dry + reverb reconstruction SNR | 70.00 dB |
| Gain-fitted reconstruction SNR | 72.96 dB |
| Dry fitted gain | 1.00017 |
| Reverb fitted gain | 1.00068 |
| Dry energy share | 95.83% |
| Reverb energy share | 4.17% |
| Input vocal RMS | −22.12 dBFS |
| Dry vocal RMS | −22.41 dBFS |
| Reverb RMS | −36.03 dBFS |

The near-unity fitted gains and 70 dB raw reconstruction show that this is an exceptionally complementary split: summing the two outputs reproduces the input vocal almost exactly. The dry vocal remained highly correlated with the input (**0.9795**), while the extracted reverb carried relatively little energy.

That does not prove the dry vocal is perceptually artifact-free. Listen specifically for damaged consonants, metallic tails and unstable ambience at phrase endings. Compare the dry result against the original separated vocal at matched loudness.

The practical verdict is straightforward: use de-reverb only when the original ambience obstructs a remix or when a new vocal space is required. At over 33 minutes for a 2:10 vocal on this CPU, it is too expensive for the default pipeline.

## Local GUI MVP

The Qt producer GUI is available alongside the legacy Tkinter GUI. Use the
private alpha installation above for the installed launcher. For source
development with an existing PySide6 environment:

```bash
.venv-gui/bin/python gui/producer_qt.py
```

The Qt producer preview uses a queue-first interface with a preset per job (Balanced by default), drag-in and button-based file/folder import (top-level audio files only), resolved-path deduplication, per-track/preset export paths, process logs, Copy details, and cancellation. Batch processing skips existing nonempty output paths. Expanded track rows show actual nonempty WAV files from the expected output folder. Four-stem presets validate expected outputs, codec, channels and duration; the Drum Parts preset additionally checks its six expected stems and source-matched channels/duration. Other specialist presets still require manual inspection. The current development tree also contains experimental Qt Multimedia double-click preview, safe file-path context actions, and Qt file-URL drag-out, pending real Linux Mint/Bitwig verification. It uses the existing `scripts/stem-separate` backend and shared model cache.

Offscreen Qt regression tests, using a replacement backend and synthetic WAVs, can be run with:

```bash
QT_QPA_PLATFORM=offscreen .venv-gui/bin/python tests/test_producer_queue.py -v
```

These tests require PySide6, Qt Multimedia and `ffprobe`; they do not run separation models. The [Producer Alpha acceptance record](docs/PRODUCER-ALPHA-ACCEPTANCE.md) separates automated checks from user-reported real Mint 22 results. On mint1, the installed GUI produced four verified Balanced stems and skipped existing outputs. On mint0, the user confirmed a 249.16-second Balanced MP3 job with four verified stems, audible preview, individual stem drag into Bitwig, and repeated Cancel followed by Start. A fresh real Drum Parts validation and real backend failure-recovery check remain open; the GUI regression suite uses a replacement backend for those paths. See [Producer Queue UX](docs/PRODUCER-QUEUE-UX.md).

The legacy Tkinter interface remains available at `python3 gui/stem_lab_gui.py` (requires `python3-tk` on some systems).

| Preset | Model | Intended use |
|---|---|---|
| Fast 4 Stems | `hdemucs_mmi.yaml` | Fast everyday separation |
| Balanced 4 Stems | `htdemucs.yaml` | Reference separation |
| Fine-Tuned 4 Stems | `htdemucs_ft.yaml` | Difficult or final material |
| Vocals + Instrumental | `vocals_mel_band_roformer.ckpt` | Vocal extraction |
| Six Stems | `htdemucs_6s.yaml` | Guitar or piano material |
| Drum Parts | DrumSep | Isolated drum input only |
| Vocal De-Reverb | BS-RoFormer de-reverb | Isolated vocal input only |

The legacy Tkinter GUI provides source/output selection and single-job controls. The Qt Producer is queue-first, with per-job presets, expandable file-based results and a collapsible process log. Preview and single-file Source/Stem drag-out into Bitwig have been confirmed on Linux Mint. Reliable whole-batch progress/ETA, a fully locked package, queue recovery and release-grade error UX are not complete.

## Conclusions

The useful lesson is not “one model wins everything.” It is to use the narrowest model that matches the task.

- `hdemucs_mmi.yaml` is the fastest high-quality four-stem model tested and the strongest objective default candidate.
- `htdemucs.yaml` remains the balanced reference, especially if MMI's `other` stem sounds less natural.
- MelBand RoFormer is the strongest tested choice for vocals versus instrumental.
- DrumSep is genuinely useful, but only as a second-stage specialist tool.
- BS-RoFormer de-reverb creates an extremely complementary dry/reverb split, but its CPU cost makes it an optional final pass.
- Six-stem output is not automatically more detailed or more musical.
- Suno native stems offer useful semantic categories, but should not be mistaken for a phase-accurate decomposition of the master.

On a Ryzen 7 5700G with no ML acceleration, the workflow is already viable. A supported GPU would mainly improve iteration speed; it would not remove the need to choose the right model and audition the result.

## Research results

StemLab includes a reproducible CPU benchmark and blind listening workflow.

Current preliminary research covers two 30-second control sources across five
separation configurations using one discarded warm-up plus three measured runs.

Early observations include:

- separation runtime varies substantially with source material, even at equal duration
- MelBand RoFormer achieved 5/5 vocal isolation on both current Blind Vocal controls
- HTDemucs 6s remains a strong multi-stem candidate with substantially lower CPU runtime
  than the tested vocal RoFormer configuration
- Blind Vocal evaluates vocal extraction only and is not a full multi-stem model ranking

See [Preliminary Results v0.1](research/results-v0.1.md) for methodology,
runtime measurements, blind scores, limitations, and next steps.

## Publication notes

Before publishing benchmark audio:

- use only material for which you control the necessary rights;
- label Suno-generated or AI-assisted source material where the platform requires it;
- publish short, loudness-matched examples rather than a complete downloadable song;
- avoid presenting reconstruction SNR as a universal perceptual leaderboard;
- include exact software versions and hardware so readers can reproduce the test.

Repository licensing:

- **Article and documentation:** Creative Commons Attribution 4.0
- **Scripts and GUI code:** MIT License
- **Installed third-party packages:** retain their own licenses; PySide6 reports LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only. Review the selected license and bundled Qt notices before sharing an installer or environment.
- **Audio examples:** Excluded from the repository licenses and all rights reserved unless explicitly licensed otherwise

---

**808SGN — 808 frequency, no boundaries.**

Built by **MTM DSP** for **808SGN Labs**.
