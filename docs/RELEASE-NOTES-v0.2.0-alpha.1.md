# 808SGN StemLab v0.2.0-alpha.1 — private Linux Producer candidate

**Candidate only; not published or tagged.** This version identifies the
source-based Linux Producer alpha. The historical v0.1.0 CPU benchmark release
and its [release notes](../RELEASE_NOTES.md) remain unchanged.

## Included and acceptance basis

- Linux x86_64 Producer GUI with a queue, per-job preset, verified four-stem
  output status, safe skip of existing output, cancellation, Qt preview, and
  single-stem file drag into a desktop or DAW.
- The user reported a fresh Linux Mint 22 installation on mint1 with actual
  `audio-separator==0.47.0` and `PySide6==6.11.2`, installed GUI startup,
  real Balanced CPU inference, four verified WAV stems, desktop drag-out,
  re-import, and skip/no-overwrite. The first run downloaded model weights.
- The user reported on mint0 a 249.16-second Balanced MP3 track producing
  four verified WAV stems in about 3m55s, audible preview, individual stem
  drag into Bitwig, and repeated Cancel followed by successful Start.
- These are firsthand external reports. Local automated tests use temporary
  files and replacement backends for queue behavior; they do not repeat the
  real separation or native desktop checks. See
  [acceptance evidence](PRODUCER-ALPHA-ACCEPTANCE.md).

## Supported scope and limitations

Balanced (`htdemucs.yaml`) has the strongest real installation and workflow
evidence. Fast (`hdemucs_mmi.yaml`) is a supported four-stem option with prior
real batch evidence and automated four-stem validation, but the mint0 and mint1
acceptance measurements above are Balanced only. Maximum, Vocals, Six Stems,
Drum Parts, and Deverb remain experimental for this candidate; a fresh real
six-output Drum Parts validation is pending. CPU runtime varies by hardware,
source length, and model; the two reported timings are examples, not targets.

Python 3.12, `uv`, FFmpeg with `ffprobe`, matching Python development headers,
working C/C++ compilers and `make`, and Linux Qt XCB's
`libxcb-cursor.so.0` are required. On Mint 22, mint1 needed `python3.12-dev`,
`build-essential`, and `libxcb-cursor0`. The installer checks prerequisites but
does not install system packages. Direct Python packages are pinned in
`scripts/install.sh`; transitive dependencies and the Python patch version are
not locked. The CPU request resolved CUDA-related transitive packages on
mint1. First use of an uncached preset may download model weights; weights are
not included in the source package. NoMachine's zero-channel virtual output
made its preview result inconclusive; mint0 supplied native audible-preview
evidence. Windows packaging and compatibility are outside this candidate.

## Private source distribution recipe

After review, use a commit containing this candidate's files as
`<reviewed-commit>`. From a clean repository checkout, make this **source-only**
ZIP with Git's built-in archive command. The explicit paths exclude tests,
audio, local environments, caches, model weights, and `.git`:

```bash
git archive --format=zip --prefix=stemlab-v0.2.0-alpha.1/ \
  --output=stemlab-v0.2.0-alpha.1-source.zip <reviewed-commit> \
  README.md RELEASE_NOTES.md LICENSE-CODE LICENSE-DOCS \
  docs/PRODUCER-ALPHA-ACCEPTANCE.md docs/RELEASE-NOTES-v0.2.0-alpha.1.md \
  gui/producer_qt.py \
  scripts/install.sh scripts/install-desktop.sh scripts/stem-separate scripts/stemlab-gui
```

The current working tree is not committed by this preparation task, so **no
candidate ZIP is produced here**. Confirm the reviewed commit includes the
regression and documentation before creating a distributable archive. Share
only with authorized private testers. On a Linux x86_64 test machine with the
prerequisites above, extract the ZIP, enter its top-level directory, and run:

```bash
bash scripts/install.sh
"${XDG_DATA_HOME:-$HOME/.local/share}/808sgn-stem-lab/app/scripts/stemlab-gui"
```

The installer creates an app-owned virtual environment and copies the GUI and
launchers into XDG data storage; the installed GUI can launch after the source
directory moves. The optional desktop menu command is documented in README.
Python packages are fetched by `uv` from the configured index during install,
so this is a network-requiring source installer, not an offline or dependency-
locked bundle. Model downloads are separate and should be authorized by the
tester. Do not place private audio in the archive.

## License and notice boundary

The ZIP recipe includes this repository's MIT code license and CC BY 4.0
documentation notice. It bundles no Python wheels, Qt libraries, FFmpeg
binaries, or model weights. Components installed separately retain their own
licenses and notices; `audio-separator`, PySide6/Qt, FFmpeg, native libraries,
and each model must be reviewed individually before any redistribution of
their binaries or weights. The existing README records PySide6's alternative
license expressions; no choice or downstream compliance conclusion is made
here. Repository audio examples are excluded from the ZIP and from the code
and documentation licenses.

## Open release work

- Record the resolved transitive dependency set if the private alpha needs
  byte-for-byte repeatable environments across machines.
- Perform a native real-backend failure/recovery check if that behavior must be
  accepted beyond the deterministic regression test.
- Validate real Drum Parts outputs before promoting that experimental preset.

This document prepares a release candidate; it does not publish, tag, or
approve redistribution of third-party components.
