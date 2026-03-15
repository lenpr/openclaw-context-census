# openclaw-context-census

`content_census_report.py` is a single-file, read-only CLI for generating a standalone HTML report from a live OpenClaw workspace.

The repo is intentionally minimal:
- one deployable Python file
- direct tests against small synthetic filesystem fixtures
- no checked-in report output
- no checked-in personal snapshot data
- no Python package or build artifacts

## License

This project is open source under the MIT License. See [LICENSE](LICENSE).

## What The Tool Does

The script scans an OpenClaw workspace and its parent OpenClaw root, analyzes files by path semantics, role semantics, Git state, timestamps, size, and known OpenClaw conventions, then writes a standalone HTML report with:

- run summary
- check first
- folders & size
- file explorer
- evidence guide & external links
- external links to OpenClaw and ClawHub references

It does not delete, sync, compress, mutate, or upload anything.

## Requirements

- Python 3.11 or newer is the intended target
- no network access is required for the core report
- no package install step is required

The tool is designed to be copied to an OpenClaw machine and run directly.

## Output

By default the tool writes one standalone HTML file for human review.

You can also choose output formats explicitly:

- JSON for agent and automation use
- Markdown for compact text review or prompt handoff
- all three from one scan when you want both human and agent workflows

If OpenClaw inquiry is available during a live run, the script may also write a sidecar cache file next to the HTML report:

- `content-census-report.inquiry-cache.json`

That cache is local-only and is meant to avoid repeating the same inquiry requests for highlighted files.
Inquiry is optional and only appears when the local OpenClaw instance can be reached from the machine running the script.

The JSON output is the canonical machine-readable format. It includes the full analyzed entry set plus a `cleanup_plan` section that is meant to be consumed by Codex, OpenClaw, or another agent as the basis for cautious repository cleanup planning.

## Run It

```bash
python3 content_census_report.py ~/.openclaw/workspace
```

Write to a specific HTML path:

```bash
python3 content_census_report.py ~/.openclaw/workspace --html reports/content-census-report.html
```

If the OpenClaw root is not the workspace parent:

```bash
python3 content_census_report.py ~/.openclaw/workspace --openclaw-root ~/.openclaw
```

Useful flags:

- `--html [PATH]` to write HTML output
- `--json [PATH]` to write a machine-readable report
- `--markdown [PATH]` to write a Markdown summary
- `--all-formats` to write HTML, JSON, and Markdown from one scan
- `--archive-days` to tune archive-style recommendations
- `--stale-days` to tune stale-file signaling
- `--large-file-mb` to tune the large-file threshold
- `--include-hidden` to include hidden files and directories in the scan

Generate JSON only:

```bash
python3 content_census_report.py ~/.openclaw/workspace --json
```

Generate HTML and Markdown with a shared custom stem:

```bash
python3 content_census_report.py ~/.openclaw/workspace --html reports/content-census-report.html --markdown
```

Generate all formats from one scan:

```bash
python3 content_census_report.py ~/.openclaw/workspace --all-formats
```

See full CLI help with:

```bash
python3 content_census_report.py --help
```

## Report Sections

The HTML report currently includes:

- `Run Summary` for scan facts, source metadata, and runtime context
- `Check First` for the files and recommendation groups worth reviewing first
- `Folders & Size` for rolled-up storage distribution
- `File Explorer` for filtering, sorting, and progressive reveal
- `Evidence Guide & External Links` for recommendation codes, evidence assumptions, and reference links

The JSON output includes:

- full scan metadata and thresholds
- all analyzed entries with recommendation and evidence data
- highlights and known reference metadata
- an explicit `cleanup_plan` queue for agent-assisted repository triage

## Repository Layout

```text
.
├── content_census_report.py
├── README.md
├── .gitignore
└── tests/
```

This repository is intentionally not a Python package. The standalone script is the product.

## Test It

```bash
python3 -m unittest discover -s tests -v
```

The test suite uses synthetic filesystem fixtures created at runtime so no personal OpenClaw snapshot data needs to live in the repository.

## Design Constraints

- read-only
- local and offline by default
- deterministic classification
- transparent reason codes
- recommendations only, never actions

## Development Notes

- The script contains the analyzer, renderer, file knowledge, ClawHub knowledge, and live scan logic in one file on purpose.
- The repository avoids checked-in generated reports and local snapshot exports.
- The tests exercise the shipped standalone file directly instead of a separate package copy.

## GitHub Repository

- `https://github.com/lenpr/openclaw-context-census`
