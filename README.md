# 808SGN Stem Lab

[![Release](https://img.shields.io/badge/release-v0.1.0-7c3aed)](RELEASE_NOTES.md)
[![Linux](https://img.shields.io/badge/platform-Linux-fcc624)](#installation)
[![Code license](https://img.shields.io/badge/code-MIT-green)](LICENSE-CODE)
[![Docs license](https://img.shields.io/badge/docs-CC%20BY%204.0-blue)](LICENSE-DOCS)

**Private, local AI stem separation for Linux producers.**

Reproducible CPU benchmarks and task-focused wrappers for local music stem
separation. Built by **MTM DSP** and published by **808SGN Labs** for producers
who want private, offline processing rather than another upload service.

## Quick start

```bash
git clone https://github.com/808sgn-labs/stem-separator.git
cd stem-separator
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

Local stem separation on Linux is already good enough for serious remixing and production—even without a dedicated GPU.

- **Fastest high-quality four-stem model:** `hdemucs_mmi.yaml`
- **Balanced reference four-stem model:** `htdemucs.yaml`
- **Best maximum-quality four-stem model tested:** `htdemucs_ft.yaml`
- **Best vocals/instrumental split tested:** `vocals_mel_band_roformer.ckpt`
- **Best detailed drum split tested:** `MDX23C-DrumSep-aufr33-jarredou.ckpt`
- **Six-stem Demucs:** useful when guitar or piano is genuinely present, but not automatically better
- **Suno native stems:** useful creative exports, but not phase-accurate components of the downloaded master

For this test song, HDemucs MMI produced the highest four-stem reconstruction score while also finishing fastest. Its individual stems remained very close to regular and fine-tuned HTDemucs. Subject to listening for artifacts, it is the strongest default candidate.

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

## Installation

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
| `htdemucs_ft.yaml` | 4 stems | 8:37 | 27.40 dB | Slow maximum-quality alternative; audition on difficult material |
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

## Proposed local GUI

A lightweight Linux GUI could turn this workflow into a practical desktop tool without hiding the model choices:

| Preset | Model | Intended use |
|---|---|---|
| Fast 4 Stems | `hdemucs_mmi.yaml` | Fast everyday separation |
| Balanced 4 Stems | `htdemucs.yaml` | Reference separation |
| Maximum 4 Stems | `htdemucs_ft.yaml` | Difficult/final material |
| Vocals + Instrumental | `vocals_mel_band_roformer.ckpt` | Vocal extraction |
| Experimental 6 Stems | `htdemucs_6s.yaml` | Guitar/piano material |
| Drum Parts | DrumSep | Isolated drum input only |
| Vocal De-Reverb | BS-RoFormer de-reverb | Isolated vocal input only |

Useful GUI requirements:

- drag-and-drop WAV, FLAC and MP3
- same-folder or custom output
- automatic model-specific subfolders
- visible CPU/GPU mode
- elapsed time and progress
- displayed input and output sample rates
- persistent shared model directory
- no shell activation requirement; call the virtual environment executable directly

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

## Publication notes

Before publishing benchmark audio:

- use only material for which you control the necessary rights;
- label Suno-generated or AI-assisted source material where the platform requires it;
- publish short, loudness-matched examples rather than a complete downloadable song;
- avoid presenting reconstruction SNR as a universal perceptual leaderboard;
- include exact software versions and hardware so readers can reproduce the test.

Suggested license structure:

- **Article and documentation:** Creative Commons Attribution 4.0
- **Scripts or future GUI code:** MIT License
- **Audio examples:** All rights reserved unless explicitly licensed otherwise

---

**808SGN — 808 frequency, no boundaries.**

Built by **MTM DSP** for **808SGN Labs**.
