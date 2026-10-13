# StemLab Producer Queue — UX / HMI Specification

Status: **implementation in progress / producer alpha, release gates open** · updated 2026-10-13
Scope: Linux-first PySide6 producer GUI; Windows/macOS-compatible interaction patterns where practical.
Source of truth for implementation status: live repository and tests, not this design document.

## Product workflow

**Add audio → choose model per job → process → preview/select stems → drag WAVs into DAW.**

The queue is the main workspace, including for a single file. Remove the redundant standalone Source Audio field and global Separation Mode from the target UI. Do not create a separate stem browser.

## Layout

- Central expandable **queue with columns**: File / Stem, Mode, Status, Actions.
- Track row: source filename, per-job preset selector (default `balanced`), job status; expand/collapse to reveal output stem rows.
- Stem child rows: actual verified output filename, selectable checkbox, readiness state, contextual actions; support multiple selected stems.
- Toolbar: Add Files, Add Folder, Clear Queue, Start Processing (single primary action), Cancel while running.
- Compact overall/job processing feedback; technical process details in collapsible log.
- Adapt from two-column/wide window to single-column/narrow window. No fixed heights that clip inputs. Test DPI/font scaling and keyboard focus.
- Retain the existing dark 808SGN theme; no native-theme rewrite or new UI framework.

## Import

- Accept drag-in of local audio files and **folders** onto the queue; buttons provide equivalent actions.
- Supported extension allowlist: WAV, FLAC, MP3, M4A, OGG, AIFF, AIF (backend validation still applies).
- Folder import: **top-level files only**, no recursive scanning by default.
- Deduplicate normalized/resolved source paths. Show ignored/duplicate counts when useful.
- Disable queue mutations while processing to avoid jobs changing beneath the worker.

## Per-job processing model

Use a job structure such as:
`{source, preset, output_dir, state, stems, error}` rather than just `batch_paths`.
- Default preset: Balanced. Allow mode changes independently for queued jobs; lock the active/completed job until explicitly reset.
- One sequential CPU worker initially; output separated per source and preset.
- Distinguish `Queued`, `Processing`, `Verified`, `Failed`, `Skipped`, `Cancelled`.
- Distinguish a successful **process exit** from validated output. For unsupported validation presets show `Complete — unverified`, not `Verified`.
- Do **not** claim per-stem readiness or a total-percent/ETA until verified by backend signals or completed-file inspection. Models may write outputs only at the end.
- Never overwrite an existing nonempty output directory silently. Make retry/reprocess explicit.

## Expandable track rows

```text
▾ saigon-slides.wav       [Balanced ▾]     Verified
    [x] Vocals.wav                         Ready     ⋯
    [x] Drums.wav                          Ready     ⋯
    [x] Bass.wav                           Ready     ⋯
    [ ] Other.wav                          Ready     ⋯
▸ vocal-demo.mp3         [Vocals ▾]       Queued
```

Track and stem actions differ. Selection and a drag handle should have clear discoverability; use the keyboard/context menu as accessible alternatives.

## Drag OUT to DAW (acceptance tests required)

- Drag a **completed, existing WAV file** from its stem row to Bitwig or a file manager.
- Use Qt `QDrag` + `QMimeData` with local `file://` URLs, **copy semantics**; never move/delete source files via drag-out.
- Support dragging multiple selected completed WAV stems later, after single-stem drag-out succeeds.
- Verify actual compatibility under Linux Mint/Bitwig, including X11 vs Wayland where relevant. Do not claim automatic track assignment without testing.

## Context menu (right-click)

**Track:** Expand/Collapse; Change Preset (queued only); Show Output Folder; Select All Available Stems; Retry/Reprocess (explicit); Remove from Queue.

**Stem:** Preview; Copy File; Copy Path; Show in File Manager; Select for multi-drag. Disable actions when output is unavailable.

- `Remove from Queue` never deletes disk files.
- `Move to Trash` is postponed until safe cross-platform handling and confirmation are implemented.
- `Delete Permanently` is **out of v0.2 scope**. Never delete original source audio via queue actions.
- Disallow destructive actions while processing.
- Preview can use native Qt multimedia after verifying support; do not implement an additional playback engine for the MVP.

## Platform conventions

- Linux Mint / Qt first; use system file dialogs and file manager, not platform-specific Explorer terminology.
- Common shortcuts: open/add files, remove selected row, preview/pause; use platform-appropriate modifiers and visible focus.
- Respect accessibility, contrast, font scaling, window resizing, and keyboard-only operations.
- Maintain native file URL compatibility for Windows/macOS as a future port requirement, not a currently supported release claim.

## Priorities / gates

1. **Gate A:** Validate existing two-file sequential batch, no overwrites and correct failure/cancel behavior.
2. **Gate B:** Replace `QListWidget` with `QTreeView` + `QAbstractItemModel`; remove redundant Source Audio/global preset UI; move preset into each job.
3. **Gate C:** Expanded children reflect only actual outputs; implement selection and safe context menu (Copy Path, Show, Remove).
4. **Gate D:** Single completed WAV drag-out into Bitwig, then multi-stem selection/drag-out.
5. **Gate E:** Stem preview and polished keyboard/accessibility/error UX.

Parking lot: ETA guesses, CPU/RAM dashboards, waveform editing, custom playback engine, full file manager, elaborate animation/skeuomorphism, platform-specific theme clones.

## Current implementation snapshot (2026-10-13)

- `gui/producer_qt.py`: PySide6 two-column interface with a `QTreeWidget` queue, sequential batch processing, file/folder import (top-level only), path deduplication, and a preset selector per queued row.
- Four-stem presets (`balanced`, `4stems`, `maximum`) validate the expected WAV files, codec, channel count, and duration. Other presets now report **Complete — unverified** after a successful process exit; manual output inspection is still required.
- Existing nonempty output directories are skipped. An output-path collision with a regular file is also skipped safely.
- The current queue still uses parallel `batch_paths` / `batch_presets` arrays and hidden legacy source/global-preset controls.
- Expandable stem rows, stem selection, context actions, preview, and drag-out remain design targets, not implemented features.

## Stabilization review (2026-10-13)

### Static review changes

- Fixed completion reporting so a successful run of a preset outside the three validated four-stem modes is not labeled as verified.
- Fixed a queue crash when an expected output directory path already exists as a regular file.
- Propagated the actual resulting status to the queue row, including **Complete — unverified** and **Check output**.

### Verification performed

- Read the live Git status and reviewed the current GUI, separation wrapper, queue UX specification, and roadmap through the stemlab workspace bridge.
- Confirmed the workspace remains uncommitted: `ROADMAP.md` and `gui/producer_qt.py` modified; `docs/PRODUCER-QUEUE-UX.md` untracked.
- No shell, Python execution, Qt runtime, audio fixtures, or GUI automation capability is exposed by the current bridge. Syntax checks, test-suite execution, two-mode separation, folder/drop behavior, cancellation, and export validation therefore remain **not run**. Earlier individual CLI runs do not verify this queue implementation.

### Next gate

Run a local syntax check and the app on Linux Mint, then process two queued files using different presets. Verify output paths and WAVs, a duplicate import, top-level-only folder import, existing-output skip, cancel during a job, and a process failure. Only after these pass should the redundant source/global-mode UI be removed. Keep the current changes uncommitted until explicitly approved.

## Work runtime review (2026-10-13)

This follow-up supersedes the earlier “not run” statement for the checks listed below.
MTM Bridge still exposes no shell or GUI execution on the Linux Mint host. Work
can execute a copied source tree in its own environment; this is not a local
model-separation or Bitwig compatibility test.

### Corrections

- Disable both Browse buttons and guard source/output changes while processing.
- Initialize the queue's preset selector from the actual job preset, including
  jobs imported through the standalone source field.
- Reject a second batch start while a batch is active; lock controls immediately.
- Handle output-directory inspection errors without stranding the queue.
- Recheck batch destinations before launching and refuse newly nonempty paths.
- Preserve earlier jobs' process logs for reviewing mixed-success batches.
- Label validated rows Verified; use a neutral queue-finished summary that asks
  the user to inspect row statuses instead of implying every job succeeded.
- Allow cancellation between jobs; terminate an active process and kill it after
  three seconds if needed. Bind delayed cleanup to that exact process.
- Keep a stable process reference while closing; block queued work from starting
  after the window closes.

### Verification

- Python syntax check and Bash wrapper syntax check passed in Work.
- Eight offscreen PySide6 regression tests passed in Work:
  per-job Balanced/Vocals dispatch and control locking, top-level folder import
  and resolved-path deduplication, existing-file output skip without overwrite,
  legacy preset display, continuation after process failure, forced cancellation
  without launching the next job, closing during processing, and output checks
  covering missing WAVs plus real valid/mismatched-duration WAVs using ffprobe.
- Test entry point: `tests/test_producer_queue.py`. Requires PySide6 and ffprobe.
  Run from the repository: `QT_QPA_PLATFORM=offscreen .venv-gui/bin/python tests/test_producer_queue.py -v`.
- Process tests use a tiny replacement backend. They verify QProcess/queue
  behavior, not model inference or separation quality. WAVs are synthetic.
- The separation wrapper was not modified. Existing uncommitted work was retained.
- No staging, commit, or push performed.

### Still required on Linux Mint — Gate A remains open

1. Start the GUI and import two real audio files. Set different presets per row
   (Balanced and Fast exercise two validated four-stem modes).
2. Process both sequentially; inspect each source/preset output directory and
   confirm four aligned WAVs and Verified row statuses.
3. Exercise physical file/folder drag-in, duplicate import, nonempty-output skip,
   cancellation, and a failing input. Confirm no next job starts after Cancel.
4. Check window/font scaling and visual interaction on the actual desktop.

The standalone Source Audio and global Mode controls were visible at this earlier review; they were subsequently hidden and the queue became the main workspace. Expandable stems and drag-out were added later on 2026-10-13. The following current-state addendum supersedes these historical notes.

## Current state addendum — 2026-10-13 (after real batch)

### Evidence verified on Linux Mint

- User reported 11/11 local Qt regression tests passing before the latest preview/drag-out changes.
- Real sequential batch processed `3.wav` (Drum Parts, 6:37), `2.wav` (Fast, 1:23), and `17.wav` (Balanced, 1:34): successful process exits and 14 actual WAV output files.
- Fast and Balanced completed existing four-stem verification; Drum Parts was `Complete — Unverified` under the earlier validator. GUI screenshots show expanded track rows with real output paths.
- The queue-first layout hides the redundant source/global mode/output panels; per-row presets and file/folder drag-in are implemented.

### Present in uncommitted source; NOT yet accepted on desktop

- Expanded WAV stem rows with shortened display labels but unchanged actual filenames.
- Qt Multimedia (`QMediaPlayer`/`QAudioOutput`) double-click stem preview confirmed working by the user. Right-click actions are implemented but not independently acceptance-tested.
- Single-file Qt file-URL drag-out with CopyAction from child rows. Initial attempt failed; corrected mouse-motion drag handling was subsequently confirmed working by the user directly from StemLab to Bitwig. Nemo drag-out remains unverified.
- Drum Parts six-file validation plus metadata checks (channels/duration), with new synthetic fixture tests.
- Process Details clipboard copy, shown only when details are expanded. Source-row and stem-row file-URL drag-out to Bitwig both confirmed by the user. No deletion features.

### Deviations from target specification

- Uses `QTreeWidget`, not `QTreeView` plus `QAbstractItemModel`; no demonstrated need to refactor before the MVP works.
- Still maintains parallel `batch_paths` / `batch_presets` arrays and hidden compatibility widgets; backlog item, not release blocker unless bugs emerge.
- No per-stem checkboxes, multi-selection drag, per-stem inline action buttons, track remove/retry, shortcut set, or queue persistence.
- Four-stem validator checks codec/channel/duration; Drum Parts validator currently checks presence, nonempty, channels and duration (not codec/sample-rate or perceptual isolation).
- Drum Parts is not automatically restricted to isolated drum inputs.

### Immediate acceptance sequence

1. Refreshed local offscreen regression tests PASSED on 2026-10-13: 16/16 in 3.976s, including synthetic Drum Parts validation, Copy details visibility and Source-row drag path. These tests do not run the real separation model.
2. Real WAV preview and Source/Stem drag-out to Bitwig confirmed by user on Linux Mint; dedicated playback-state/stop regression remains open.
3. Direct single-stem drag from StemLab into Bitwig is confirmed on Linux Mint. Verify Nemo drag-out and unchanged source files separately.
4. Run a fresh Drum Parts separation for a `Verified` row and verify all six files. Do not rerun old jobs destructively.
5. Exercise Cancel mid-process, duplicate/folder drag import and nonempty-output skip; verify error messages and status integrity.

**Decision:** GO for end-to-end producer workflow acceptance; PARK model/view refactor, multi-drag, waveform/FFT, ETA and extra design work. No commit or release claim until acceptance and explicit approval.

## Recovery classification prototype (uncommitted)

- `inspect_existing_output` distinguishes missing source, empty destination (READY), directory/file conflicts (BLOCKED), incomplete/unknown data, and four expected nonempty WAVs (EXISTING STEMS).
- An output marked EXISTING STEMS is **not** audio-metadata verified merely by filename/size; future recovery must re-probe audio before showing Verified.
- Existing or partial outputs are skipped without modifying data; no automatic retry, overwrite, cleanup or persistent queue restore.
- Synthetic tests cover interrupted/empty/complete-looking/zero-byte outputs and no-overwrite behavior. They still need to run on Linux Mint.

## Post-alpha hardening (uncommitted)

- Fixed cancellation during the queued-but-not-started interval: release Add/Clear/Start controls and preset combos, retain `CANCELLED` status, and prevent the scheduled next job from starting.
- Added `test_cancel_between_jobs_restores_queue_controls` covering this case.
- This is a new change after commit `52b7171`; local regression execution is still required before committing.
