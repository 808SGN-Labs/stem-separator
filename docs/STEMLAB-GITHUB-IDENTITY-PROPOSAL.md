# StemLab GitHub identity migration proposal

Status: planning only. Product name: **StemLab by 808SGN Labs**. Proposed
repository: `808SGN-Labs/stemlab`, subject to separate user approval. The
Linux `v0.2.0-alpha.1` source ZIP stays private; this proposal does not
publish an alpha or change the existing MIT code and CC BY documentation
licenses. Open Core is an investigation, with no feature split now.

## Confirmed local audit

The audit used tracked files at `125594e` and local Git configuration. Literal
`stem-separator` occurs in three tracked lines:

| Location | Current reference | Proposed handling after rename approval |
|---|---|---|
| `README.md:17` | `git clone https://github.com/808sgn-labs/stem-separator.git` | Update the clone URL to the new slug when the new repository is live. |
| `README.md:18` | `cd stem-separator` | Update to `cd stemlab`. |
| `CITATION.cff:10` | `repository-code: "https://github.com/808sgn-labs/stem-separator"` | Update only `repository-code`; keep its historical v0.1.0 title, version, date and citation context unless separately reviewed. |

Local `origin` fetch and push URLs both currently use
`https://github.com/808SGN-Labs/stem-separator.git`. Exact proposed clone URLs:

```text
Old: https://github.com/808SGN-Labs/stem-separator.git
New: https://github.com/808SGN-Labs/stemlab.git
```

`README.md:3-6` has four static Shields badges for the historical benchmark,
Linux, MIT code and CC BY docs. They do not encode the GitHub repository slug.
The Linux badge links to `#installation`, while the current heading is
`Installation (private Linux alpha)`; its anchor should become
`#installation-private-linux-alpha` in the eventual README edit. The README's
upstream `audio-separator` link and `THIRD_PARTY.md` project links refer to
other projects; they should not be rewritten as StemLab repository URLs.

No tracked installer, launcher, GUI, benchmark script, test, release note, or
research document contains the literal old repository slug. Runtime names
such as `scripts/stem-separate`, `808sgn-stem-lab` XDG paths, desktop IDs,
ownership markers and test fixtures identify a CLI or existing installation;
changing them as part of a GitHub repository rename would risk compatibility.
`RELEASE_NOTES.md` remains the historical public v0.1.0 benchmark record.
`CITATION.cff` currently describes that release, not the private alpha.

This is a local reference audit, not proof about GitHub state. The existing
private ZIP and `docs/CODEX-REVIEW.md` were not opened or changed.

## External references to check at the approval gate

The workspace cannot establish the current repository settings, redirects,
domain availability, or every consumer of the old URL. Before a rename, check
GitHub branch rules, Actions and repository secrets, webhooks, installed apps,
deploy keys, Pages/custom domains, packages, releases and assets, issue/PR
links, forks, badges on other sites, citation indexes, README copies,
submodules, CI dependencies, and downstream Git remotes. Inventory any
hardcoded `808SGN-Labs/stem-separator` references in other repositories and
automation. These are **possible external dependencies**, not confirmed hits.
Do not treat GitHub redirects as permanent or rely on them as the migration
plan; an old slug can later be reused or a consumer may require its URL to be
updated explicitly.

## Proposed rename sequence and rollback

1. Keep the private alpha ZIP private. Obtain explicit approval for the
   GitHub repository rename as a separate action; confirm the desired
   visibility and that `808SGN-Labs/stemlab` is available.
2. Record current repository settings and an inventory of external consumers.
   Prepare README and `CITATION.cff` edits for the new URL, plus updates to
   any confirmed integrations. Keep `RELEASE_NOTES.md`, version tags, and
   runtime XDG/CLI identifiers unchanged.
3. Rename the GitHub repository only after approval. Verify the new clone URL,
   repository settings, Actions, issue/PR links, release/tag pages and any
   integrations that were inventoried. Update the local `origin` and other
   maintained references explicitly; do not depend on the old URL redirect.
4. Review and then publish the producer-first README and citation URL change
   as a separate content change. Do not publish `v0.2.0-alpha.1` as a GitHub
   release. Notify known downstream users to update their remotes.
5. If the new repository name or integrations fail, stop further URL edits;
   restore the old slug **only if it is still available and authorized**,
   restore recorded settings and remote URLs, and verify all affected
   integrations again. A rename back is not guaranteed, so retain the old URL
   inventory and a direct communication path to downstream users.

No step above has been executed in this task.

## Proposed GitHub About metadata

Description: **StemLab by 808SGN Labs — local Linux stem separation for
producers, with verified WAV exports, preview and DAW drag-out.**

Suggested topics: `stem-separation`, `audio-source-separation`,
`music-production`, `linux`, `python`, `pyside6`, `local-first`,
`audio-research`. These describe the current project; avoid `windows`,
`offline-installer`, or universal quality claims. Topics and description are
proposals, not edits to GitHub.

## Producer-first README draft

The following is proposed replacement **opening content only**. Preserve the
existing benchmark tables, methodology, model caveats, research links,
publication notes and historical v0.1.0 notes below the producer introduction
when editing the actual README. Keep the private alpha install distinct from
the historical public benchmark release. No screenshots are claimed.

> # StemLab by 808SGN Labs
>
> **Separate music into stems on your own Linux machine, then bring verified
> WAV files into your production session.** StemLab gives producers a local
> queue, CPU-first presets, preview and file drag-out. Source audio is handled
> locally; package installation and first use of an uncached model can require
> network access. No cloud upload service is part of this workflow.
>
> ## What the Producer GUI does
>
> - Import audio files or a folder's top-level audio files, queue multiple
>   tracks and choose a preset for each job. Balanced is the default; Fast is
>   the other supported four-stem option in this private alpha.
> - Start sequential CPU jobs, view process logs, cancel a run, and inspect
>   WAV stems. Supported four-stem outputs are checked for expected files and
>   basic audio metadata before they appear as verified.
> - Re-import existing results. StemLab skips an occupied output destination
>   and does not overwrite partial or unrecognized files automatically.
> - Preview stems with Qt Multimedia and drag individual verified stem files
>   into a file manager or DAW. On Linux Mint, a user confirmed audible
>   preview and individual stem drag into Bitwig. Follow the
>   [acceptance record](PRODUCER-ALPHA-ACCEPTANCE.md) for the exact reported
>   scope; automated tests use a replacement backend.
>
> ## Private Linux alpha install
>
> `v0.2.0-alpha.1` is a privately shared source ZIP, not a public GitHub
> release. On Linux x86_64, install Python 3.12, `uv`, FFmpeg with `ffprobe`,
> matching Python development headers, a working C/C++ toolchain and `make`,
> and `libxcb-cursor.so.0`. Extract the authorized ZIP, open its top-level
> directory, then run:
>
> ```bash
> bash scripts/install.sh
> "${XDG_DATA_HOME:-$HOME/.local/share}/808sgn-stem-lab/app/scripts/stemlab-gui"
> ```
>
> The installer pins direct Python dependencies, but the transitive set is
> not locked. Model weights are not bundled. First use of an uncached model
> may download weights; CPU time varies by machine and track. Other presets
> remain experimental for this candidate. See the
> [candidate notes](RELEASE-NOTES-v0.2.0-alpha.1.md) and
> [third-party notices](../THIRD_PARTY.md).
>
> ## Research and the v0.1.0 benchmark
>
> StemLab also contains CPU benchmarks and a blind listening pilot. Results
> are source-dependent and are not a universal model-quality ranking. Keep
> the existing [v0.1.0 release notes](../RELEASE_NOTES.md),
> [preliminary benchmark](../research/results-v0.1.md), and
> [listening consolidation](../research/listening-consolidated-2026-10-08.md)
> linked here, followed by the full existing benchmark and research content.

The relative links in this quoted draft are written from this `docs/`
planning file for local validation. When moving the text to root `README.md`,
adjust them to root-relative paths: `docs/PRODUCER-ALPHA-ACCEPTANCE.md`,
`docs/RELEASE-NOTES-v0.2.0-alpha.1.md`, `THIRD_PARTY.md`,
`RELEASE_NOTES.md`, and `research/...`.

## Open Core boundary

The published code is MIT licensed, and the documentation notice is CC BY
4.0. The MIT text grants recipients broad rights to use, copy, modify,
distribute, sublicense and sell copies, subject to preserving the copyright
and permission notice. A future Open Core business model cannot retract
those rights from copies already released under MIT or promise exclusive
control over those previously released features. A future separately
developed commercial offering may be explored only after checking ownership,
contribution rights and third-party obligations. No current feature is
reclassified, paywalled or relicensed by this proposal.
