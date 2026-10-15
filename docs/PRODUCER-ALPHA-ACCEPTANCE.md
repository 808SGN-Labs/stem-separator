# Producer Alpha acceptance — Linux Mint 22, mint1 and mint0

Date: 2026-10-15. Scope: private Linux Producer Alpha, x86_64.

## External user-reported acceptance

The following results were supplied by the user from a fresh mint1 checkout at
`f1834b1`. They are firsthand results of that external run, not commands or
observations reproduced in this workspace. No mint1 logs or artifacts were
imported here.

| Check | Reported result |
|---|---|
| Starting platform | Linux Mint 22 x86_64; Python 3.12.3, uv 0.13.1, FFmpeg 6.1.1. |
| Real installer dependencies | First install stopped while compiling `diffq==0.2.4` because `Python.h` was absent. Installing `python3.12-dev` and `build-essential` resolved the build. The rerun installed 82 actual Python packages, including `audio-separator==0.47.0` and `PySide6==6.11.2`. The CPU-only request also resolved CUDA-related transitive packages; dependency optimization is outside this acceptance. |
| Installed GUI startup | The first GUI launch failed to load Qt XCB because `libxcb-cursor.so.0` was missing. Installing `libxcb-cursor0` resolved startup; the installed Producer GUI opened through NoMachine. |
| Real Balanced job | A 10-second synthetic control WAV used `balanced` / `htdemucs.yaml`. The first run downloaded the model, completed real CPU inference, and produced four verified WAV stems. The log reported approximately 47 seconds of separation. |
| File and output behavior | Drag-out from installed StemLab to the Linux desktop was manually confirmed. Re-import showed `Verified Existing` with four `Ready` stems. A second job skipped the existing verified outputs; its log reported that the output was unchanged. |
| Remote preview | Qt Multimedia found a NoMachine Output with preferred 48,000 Hz sample rate but zero channels. Preview failed with `QAudioFormat not supported by QAudioDevice`. This is inconclusive for normal desktop playback, not evidence of an application defect. |

Additional firsthand user reports from mint0 on 2026-10-15 (no logs or audio
artifacts imported into this workspace):

| Check | Reported result |
|---|---|
| Real music separation | A 249.16-second Balanced MP3 track completed on CPU in about 3m55s and produced four verified WAV stems. This is one machine/workload measurement, not a general performance guarantee. |
| Native desktop workflow | StemLab preview was audible; individual stem drag into Bitwig succeeded. |
| Cancellation and restart | Repeated Cancel followed by Start Processing succeeded on the native desktop. A deliberately failing real backend and post-failure retry were not part of this report. |

## Automated checks in this repository

Installer preflight tests use temporary `uv`, Python, FFmpeg, compiler, and Qt
library stubs. They verify installer control flow and diagnostics, not the
mint1 package build, model inference, real audio output, or native GUI playback.
The mint1 results above supply the real-dependency and GUI-startup evidence.
In the local 2026-10-15 regression run, 17 installer preflight tests, 52
offscreen Producer GUI tests, four desktop-installer tests, and three offline
wrapper tests passed. The GUI suite used real local PySide6 and some real
`ffprobe` checks on synthetic WAVs, but substituted the separator backend and
mocked audio playback and drag operations.

The release-candidate regression adds a temporary-fixture backend that writes
one partial stem and exits with code 7. It checks that the queue continues to
a valid second job, the failed partial file stays untouched, and a rerun skips
both existing destinations. This test uses a replacement backend and synthetic
WAV files; it does not constitute real model failure testing.

## Remaining private Alpha limits and follow-up checks

- Reproduce a real backend failure and subsequent recovery on the native
  desktop before treating that path as real-world acceptance. The automated
  failure test covers the deterministic queue and output-safety contract.
- Revalidate six real Drum Parts outputs end-to-end if that preset is claimed
  as validated in the Alpha; otherwise keep it explicitly experimental.
- Record the resolved dependency closure or lock it before claiming a
  reproducible dependency set across fresh machines. The direct installer pins
  alone do not ensure the same transitive packages or Python patch version.

This record does not establish Windows compatibility, model-free offline first
run, audio-device behavior across arbitrary Linux devices, or a fully locked
binary package. See the candidate source-archive recipe in
[v0.2.0-alpha.1 release notes](RELEASE-NOTES-v0.2.0-alpha.1.md).
