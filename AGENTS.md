# StemLab repository instructions

Keep existing coding instructions, user constraints, and security boundaries in force. These handover rules add reporting requirements; they do not authorize downloads, elevated access, commits, pushes, or changes outside the requested scope.

After every completed coding, testing, audit, or release task:

1. Show a compact final report in the Codex terminal.
2. Write the same report to `docs/CODEX-HANDOFF.md`, replacing the previous report. Do not modify `docs/CODEX-REVIEW.md` for handovers.
3. Include the task and outcome (`PASS`, `PARTIAL`, or `BLOCKED`); exact changed files and Git status; exact test commands with passed, failed, and skipped counts and exit codes; which checks used real dependencies versus mocks or stubs; the `git diff --check` outcome; remaining risks, blockers, and the next suggested step; and whether downloads, permissions, commits, or pushes occurred.
4. Claim a test passed only when its output confirms that result. Mark tests not run as not run, with no invented counts or exit codes.
5. If the handoff file cannot be written, say so explicitly in the terminal. Never bypass the sandbox to write it.
6. Exclude secrets, credentials, personal audio filenames, and sensitive absolute paths from both reports.
7. Never commit or push automatically.
8. Do not add tools, scripts, services, or dependencies solely for reporting.

Keep the handoff in this repository's `docs/` directory so it is available through the existing MTM Bridge workspace. It is ignored by Git to keep it out of normal release staging.
