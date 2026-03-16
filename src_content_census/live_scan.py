# --- Begin inlined module: live_scan.py ---
import argparse
import getpass
import json
import os
import platform
import re
import shutil
import socket
import stat
import subprocess
import sys
import threading
import time
from collections import Counter
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath



DEFAULT_EXCLUDED_DIR_NAMES = (".git", ".venv", "__pycache__", "node_modules", "venv")
DEFAULT_HASH_MAX_BYTES = 4 * 1024 * 1024
DEFAULT_PREVIEW_BYTES = 1500
DEFAULT_INQUIRY_BATCH_SIZE = 10
DEFAULT_INQUIRY_TIMEOUT_SECONDS = 180
# Backward-compatible aliases while the old naming is phased out.
DEFAULT_SLEUTH_BATCH_SIZE = DEFAULT_INQUIRY_BATCH_SIZE
DEFAULT_SLEUTH_TIMEOUT_SECONDS = DEFAULT_INQUIRY_TIMEOUT_SECONDS
LIVE_SCAN_SCHEMA_VERSION = "live-scan-0.1"
AUTO_OUTPUT_PATH = "__AUTO_OUTPUT_PATH__"


@dataclass(frozen=True)
class _GitRepoIndex:
    repo_root: Path
    tracked: set[str]
    ignored: set[str]
    untracked: set[str]
    modified: set[str]
    staged: set[str]


@dataclass(frozen=True)
class _ScanPlan:
    paths: list[tuple[Path, str]]
    skipped_hidden_count: int
    skipped_excluded_count: int


class _ProgressBar:
    def __init__(self, stream = None) -> None:
        self.stream = stream or sys.stderr
        self.is_tty = bool(getattr(self.stream, "isatty", lambda: False)())
        self.width = 28
        self.current = 0
        self.total = 0
        self.label = ""
        self.mode = "idle"
        self.spinner_index = 0
        self.last_percent = -1
        self.last_tick = 0.0

    def phase(self, label: str) -> None:
        self.label = label
        self.mode = "phase"
        self.current = 0
        self.total = 0
        self.last_percent = -1
        self._render_phase()

    def start_count(self, label: str, total: int | None = None) -> None:
        self.label = label
        self.mode = "count"
        self.current = 0
        self.total = max(total or 0, 0)
        self.last_percent = -1
        self.last_tick = 0.0
        self._render_count(force=True)

    def count_tick(self, increment: int = 1, *, force: bool = False) -> None:
        self.current += increment
        self._render_count(force=force)

    def tick(self) -> None:
        if self.mode == "count":
            self._render_count()

    def set_label(self, label: str, *, force: bool = False) -> None:
        self.label = label
        if self.mode == "count":
            self._render_count(force=force)
        elif self.mode == "progress":
            self._render_progress(force=force)
        elif self.mode == "phase":
            self._render_phase()

    def start(self, label: str, total: int) -> None:
        self.label = label
        self.mode = "progress"
        self.current = 0
        self.total = max(total, 1)
        self.last_percent = -1
        self._render_progress(force=True)

    def advance(self, increment: int = 1) -> None:
        self.current += increment
        self._render_progress()

    def finish(self, label: str) -> None:
        if self.mode == "progress" and self.total:
            self.current = self.total
            self._render_progress(force=True)
        self._write_line(label)
        self.mode = "idle"

    def _render_phase(self) -> None:
        self._write_line(f"[phase] {self.label}")

    def _render_count(self, *, force: bool = False) -> None:
        count_text = f"{self.current:,}/{self.total:,}" if self.total else f"{self.current:,} paths"
        if self.is_tty:
            now = time.monotonic()
            if not force and now - self.last_tick < 0.08:
                return
            self.last_tick = now
            spinner = ["-", "\\", "|", "/"][self.spinner_index % 4]
            self.spinner_index += 1
            self._write_inline(f"[{spinner}] {self.label} ({count_text})")
            return

        should_write = force
        if self.total:
            should_write = should_write or self.current in {0, self.total}
        else:
            should_write = should_write or self.current in {1, 25} or self.current % 250 == 0
        if should_write:
            self._write_line(f"[count] {self.label}: {count_text}")

    def _render_progress(self, *, force: bool = False) -> None:
        percent = int((self.current / self.total) * 100) if self.total else 100
        if not force and percent == self.last_percent:
            return
        self.last_percent = percent

        if self.is_tty:
            filled = int(self.width * min(self.current, self.total) / self.total)
            bar = "#" * filled + "-" * (self.width - filled)
            self._write_inline(f"[{bar}] {percent:3d}% {self.label} ({self.current:,}/{self.total:,})")
            return

        if force or percent in {0, 100} or percent % 10 == 0:
            self._write_line(f"[progress] {percent:3d}% {self.label} ({self.current:,}/{self.total:,})")

    def _write_inline(self, message: str) -> None:
        self.stream.write("\r" + message.ljust(96))
        self.stream.flush()

    def _write_line(self, message: str) -> None:
        if self.is_tty:
            self.stream.write("\r" + " " * 96 + "\r")
        self.stream.write(message + "\n")
        self.stream.flush()


def build_live_snapshot(
    workspace_path: str | Path,
    *,
    openclaw_root: str | Path | None = None,
    include_hidden: bool = False,
    hash_max_bytes: int = DEFAULT_HASH_MAX_BYTES,
    preview_bytes: int = DEFAULT_PREVIEW_BYTES,
    excluded_dir_names: tuple[str, ...] = DEFAULT_EXCLUDED_DIR_NAMES,
    progress: _ProgressBar | None = None,
) -> SnapshotDocument:
    """Scan a live OpenClaw workspace and root into the internal snapshot model."""
    workspace = Path(workspace_path).expanduser().resolve()
    if not workspace.exists():
        raise ValueError(f"Workspace path does not exist: {workspace}")
    if not workspace.is_dir():
        raise ValueError(f"Workspace path is not a directory: {workspace}")

    effective_openclaw_root = Path(openclaw_root).expanduser().resolve() if openclaw_root else workspace.parent.resolve()
    if not effective_openclaw_root.exists():
        raise ValueError(f"OpenClaw root does not exist: {effective_openclaw_root}")
    if not effective_openclaw_root.is_dir():
        raise ValueError(f"OpenClaw root is not a directory: {effective_openclaw_root}")

    generated_at_utc = datetime.now(UTC)
    host = SnapshotHost(
        hostname=socket.gethostname(),
        platform=platform.platform(),
        python_version=sys.version.split()[0],
        user_name=getpass.getuser(),
        openclaw_version=_detect_openclaw_version(effective_openclaw_root),
    )
    scan = SnapshotScan(
        workspace=str(workspace),
        openclaw_root=str(effective_openclaw_root),
        include_hidden=include_hidden,
        hash_max_bytes=hash_max_bytes,
        preview_bytes=preview_bytes,
        excluded_dir_names=excluded_dir_names,
    )

    if progress:
        progress.phase("Indexing Git state")
    repo_indexes = _build_git_indexes([workspace, effective_openclaw_root], include_hidden, excluded_dir_names)
    errors: list[dict[str, str]] = []
    entries: list[SnapshotEntry] = []
    excluded_dir_set = set(excluded_dir_names)

    if progress:
        progress.start_count("Counting paths")
    scan_plans = {
        "workspace": _iter_scan_paths(
            root_path=workspace,
            include_hidden=include_hidden,
            excluded_dir_names=excluded_dir_set,
            progress=progress,
        ),
        "openclaw": _iter_scan_paths(
            root_path=effective_openclaw_root,
            include_hidden=include_hidden,
            excluded_dir_names=excluded_dir_set,
            progress=progress,
        ),
    }
    total_paths = sum(len(plan.paths) for plan in scan_plans.values())
    skipped_hidden_count = sum(plan.skipped_hidden_count for plan in scan_plans.values())
    skipped_excluded_count = sum(plan.skipped_excluded_count for plan in scan_plans.values())
    if progress:
        progress.start("Scanning filesystem", total_paths)

    for root_type, root_path in (("workspace", workspace), ("openclaw", effective_openclaw_root)):
        entries.extend(
            _scan_root(
                root_type=root_type,
                root_path=root_path,
                planned_paths=scan_plans[root_type].paths,
                generated_at_utc=generated_at_utc,
                hash_max_bytes=hash_max_bytes,
                preview_bytes=preview_bytes,
                repo_indexes=repo_indexes,
                errors=errors,
                progress=progress,
            )
        )

    summary = SnapshotSummary(
        entry_count=len(entries),
        error_count=len(errors),
        root_counts=dict(_ordered_counts(Counter(entry.root_type for entry in entries))),
        kind_counts=dict(_ordered_counts(Counter(entry.kind for entry in entries), ["file", "dir", "symlink"])),
        role_counts=dict(_ordered_counts(Counter(entry.role for entry in entries))),
        skipped_count=skipped_hidden_count + skipped_excluded_count,
        skipped_hidden_count=skipped_hidden_count,
        skipped_excluded_count=skipped_excluded_count,
    )

    synthetic_source = effective_openclaw_root / "content-census-live-scan.json"
    return SnapshotDocument(
        source_path=str(synthetic_source),
        schema_version=LIVE_SCAN_SCHEMA_VERSION,
        generated_at_utc=generated_at_utc,
        host=host,
        scan=scan,
        summary=summary,
        errors=tuple(errors),
        entries=tuple(sorted(entries, key=lambda item: (item.root_type, item.relative_path, item.kind, item.name))),
    )


def build_live_analysis_result(
    workspace_path: str | Path,
    *,
    openclaw_root: str | Path | None = None,
    include_hidden: bool = False,
    hash_max_bytes: int = DEFAULT_HASH_MAX_BYTES,
    preview_bytes: int = DEFAULT_PREVIEW_BYTES,
    inquiry_cache_path: str | Path | None = None,
    inquiry_batch_size: int = DEFAULT_INQUIRY_BATCH_SIZE,
    excluded_dir_names: tuple[str, ...] = DEFAULT_EXCLUDED_DIR_NAMES,
    config: AnalysisConfig | None = None,
    sleuth_cache_path: str | Path | None = None,
    sleuth_batch_size: int | None = None,
    progress: _ProgressBar | None = None,
) -> tuple[SnapshotDocument, AnalysisResult]:
    """Run a live scan, analyze it, optionally attach inquiry data, and return the snapshot and result."""
    snapshot = build_live_snapshot(
        workspace_path,
        openclaw_root=openclaw_root,
        include_hidden=include_hidden,
        hash_max_bytes=hash_max_bytes,
        preview_bytes=preview_bytes,
        excluded_dir_names=excluded_dir_names,
        progress=progress,
    )
    if progress:
        progress.phase("Analyzing entries")
    effective_inquiry_cache_path = inquiry_cache_path or sleuth_cache_path
    effective_inquiry_batch_size = sleuth_batch_size if sleuth_batch_size is not None else inquiry_batch_size
    result = analyze_snapshots([snapshot], config=config or AnalysisConfig())
    result = _attach_openclaw_inquiry(
        result,
        openclaw_root=Path(snapshot.scan.openclaw_root),
        cache_path=Path(effective_inquiry_cache_path).expanduser() if effective_inquiry_cache_path else None,
        batch_size=effective_inquiry_batch_size,
        timeout_seconds=DEFAULT_INQUIRY_TIMEOUT_SECONDS,
        progress=progress,
    )
    return snapshot, result


def render_live_html_report(
    workspace_path: str | Path,
    *,
    openclaw_root: str | Path | None = None,
    include_hidden: bool = False,
    hash_max_bytes: int = DEFAULT_HASH_MAX_BYTES,
    preview_bytes: int = DEFAULT_PREVIEW_BYTES,
    inquiry_cache_path: str | Path | None = None,
    inquiry_batch_size: int = DEFAULT_INQUIRY_BATCH_SIZE,
    excluded_dir_names: tuple[str, ...] = DEFAULT_EXCLUDED_DIR_NAMES,
    config: AnalysisConfig | None = None,
    sleuth_cache_path: str | Path | None = None,
    sleuth_batch_size: int | None = None,
    progress: _ProgressBar | None = None,
) -> str:
    """Run a live scan, analyze it, optionally attach inquiry data, and return standalone HTML."""
    snapshot, result = build_live_analysis_result(
        workspace_path,
        openclaw_root=openclaw_root,
        include_hidden=include_hidden,
        hash_max_bytes=hash_max_bytes,
        preview_bytes=preview_bytes,
        inquiry_cache_path=inquiry_cache_path,
        inquiry_batch_size=inquiry_batch_size,
        excluded_dir_names=excluded_dir_names,
        config=config,
        sleuth_cache_path=sleuth_cache_path,
        sleuth_batch_size=sleuth_batch_size,
        progress=progress,
    )
    if progress:
        progress.phase("Rendering HTML")
    return _rewrite_html_for_live_scan(render_html_report(result), snapshot)


def _default_output_base() -> Path:
    return Path("content-census-report")


def _default_output_path(suffix: str) -> Path:
    return _default_output_base().with_suffix(suffix)


def _output_auto_base(args) -> Path:
    for value in (args.html_path, args.json_path, args.markdown_path):
        if value is not None and value != AUTO_OUTPUT_PATH:
            return Path(value).expanduser().with_suffix("")
    return _default_output_base()


def _resolve_requested_output_path(value: str | None, *, suffix: str, auto_base: Path) -> Path | None:
    if value is None:
        return None
    if value == AUTO_OUTPUT_PATH:
        return auto_base.with_suffix(suffix)
    return Path(value).expanduser()


def _selected_output_paths(args) -> tuple[Path | None, Path | None, Path | None]:
    auto_base = _output_auto_base(args)
    html_path = _resolve_requested_output_path(args.html_path, suffix=".html", auto_base=auto_base)
    json_path = _resolve_requested_output_path(args.json_path, suffix=".json", auto_base=auto_base)
    markdown_path = _resolve_requested_output_path(args.markdown_path, suffix=".md", auto_base=auto_base)

    if args.all_formats:
        html_path = html_path or auto_base.with_suffix(".html")
        json_path = json_path or auto_base.with_suffix(".json")
        markdown_path = markdown_path or auto_base.with_suffix(".md")
    elif html_path is None and json_path is None and markdown_path is None:
        html_path = _default_output_path(".html")

    return html_path, json_path, markdown_path


def _inquiry_cache_output_base(
    html_path: Path | None,
    json_path: Path | None,
    markdown_path: Path | None,
) -> Path:
    for candidate in (html_path, json_path, markdown_path):
        if candidate is not None:
            return candidate
    return _default_output_path(".html")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the standalone content census script."""
    parser = argparse.ArgumentParser(
        prog="content_census_report.py",
        description=(
            "Scan an OpenClaw workspace read-only and write HTML, JSON, and/or Markdown content census reports."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "workspace",
        help="Path to the OpenClaw workspace directory, typically ~/.openclaw/workspace.",
    )
    parser.add_argument(
        "--openclaw-root",
        dest="openclaw_root",
        help="Path to the OpenClaw root directory. Defaults to the parent of the workspace path.",
    )
    parser.add_argument(
        "--html",
        dest="html_path",
        nargs="?",
        const=AUTO_OUTPUT_PATH,
        metavar="PATH",
        help="Optional HTML output path. If PATH is omitted, use the current output stem with a .html suffix.",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        nargs="?",
        const=AUTO_OUTPUT_PATH,
        metavar="PATH",
        help="Optional machine-readable JSON output path. If PATH is omitted, use the current output stem with a .json suffix.",
    )
    parser.add_argument(
        "--markdown",
        dest="markdown_path",
        nargs="?",
        const=AUTO_OUTPUT_PATH,
        metavar="PATH",
        help="Optional Markdown summary output path. If PATH is omitted, use the current output stem with a .md suffix.",
    )
    parser.add_argument(
        "--all-formats",
        action="store_true",
        help="Write HTML, JSON, and Markdown outputs from the same scan using default paths unless specific paths are provided.",
    )
    parser.add_argument(
        "--archive-days",
        type=int,
        default=30,
        help="Age threshold used for archive-style recommendations. Default: 30.",
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=180,
        help="Age threshold used for stale-file reason codes. Default: 180.",
    )
    parser.add_argument(
        "--large-file-mb",
        type=int,
        default=25,
        help="Large file threshold in MiB. Default: 25.",
    )
    parser.add_argument(
        "--hash-max-bytes",
        type=int,
        default=DEFAULT_HASH_MAX_BYTES,
        help=f"Maximum file size to hash in bytes. Default: {DEFAULT_HASH_MAX_BYTES}.",
    )
    parser.add_argument(
        "--preview-bytes",
        type=int,
        default=DEFAULT_PREVIEW_BYTES,
        help=f"Maximum bytes to capture for text previews. Default: {DEFAULT_PREVIEW_BYTES}.",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden files and directories during scanning.",
    )
    parser.epilog = (
        "Examples:\n"
        "  python3 content_census_report.py ~/.openclaw/workspace\n"
        "  python3 content_census_report.py ~/.openclaw/workspace --json\n"
        "  python3 content_census_report.py ~/.openclaw/workspace --html reports/content-census-report.html\n"
        "  python3 content_census_report.py ~/.openclaw/workspace --all-formats\n"
        "  python3 content_census_report.py ~/.openclaw/workspace --openclaw-root ~/.openclaw\n"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for generating an HTML report from a live OpenClaw workspace."""
    parser = build_parser()
    args = parser.parse_args(argv)

    html_path, json_path, markdown_path = _selected_output_paths(args)
    for output_path in (html_path, json_path, markdown_path):
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
    inquiry_base_path = _inquiry_cache_output_base(html_path, json_path, markdown_path)
    inquiry_cache_path = inquiry_base_path.with_name(f"{inquiry_base_path.stem}.inquiry-cache.json")

    config = AnalysisConfig(
        archive_days=args.archive_days,
        stale_days=args.stale_days,
        large_file_bytes=args.large_file_mb * 1024 * 1024,
    )

    progress = _ProgressBar()
    snapshot, result = build_live_analysis_result(
        args.workspace,
        openclaw_root=args.openclaw_root,
        include_hidden=args.include_hidden,
        hash_max_bytes=args.hash_max_bytes,
        preview_bytes=args.preview_bytes,
        inquiry_cache_path=inquiry_cache_path,
        config=config,
        progress=progress,
    )
    selected_output_count = sum(path is not None for path in (html_path, json_path, markdown_path))
    render_label = "Rendering reports" if selected_output_count > 1 else "Rendering report"
    progress.phase(render_label)
    html_report = _rewrite_html_for_live_scan(render_html_report(result), snapshot) if html_path else None
    json_report = render_json_report(result) if json_path else None
    markdown_report = render_markdown_report(result) if markdown_path else None
    write_label = "Writing reports" if selected_output_count > 1 else "Writing report"
    progress.phase(write_label)
    if html_path and html_report is not None:
        html_path.write_text(html_report, encoding="utf-8")
    if json_path and json_report is not None:
        json_path.write_text(json_report, encoding="utf-8")
    if markdown_path and markdown_report is not None:
        markdown_path.write_text(markdown_report, encoding="utf-8")
    completion_labels: list[str] = []
    if html_path:
        completion_labels.append(f"HTML report: {html_path}")
    if json_path:
        completion_labels.append(f"JSON report: {json_path}")
    if markdown_path:
        completion_labels.append(f"Markdown report: {markdown_path}")
    progress.finish("Finished. " + " | ".join(completion_labels))
    for label in completion_labels:
        print(label)
    return 0


def _request_openclaw_inquiry_batch_with_progress(
    cli_path: Path,
    *,
    agent_id: str,
    batch: list[dict[str, object]],
    timeout_seconds: int,
    progress: _ProgressBar | None,
):
    if progress is None:
        return _request_openclaw_inquiry_batch(
            cli_path,
            agent_id=agent_id,
            batch=batch,
            timeout_seconds=timeout_seconds,
        )

    result_holder: dict[str, dict[str, dict[str, object]]] = {}
    error_holder: dict[str, Exception] = {}

    def worker() -> None:
        try:
            result_holder["value"] = _request_openclaw_inquiry_batch(
                cli_path,
                agent_id=agent_id,
                batch=batch,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:  # pragma: no cover - exercised via caller behavior
            error_holder["value"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    while thread.is_alive():
        progress.tick()
        thread.join(0.08)

    if "value" in error_holder:
        raise error_holder["value"]
    return result_holder.get("value", {})


def _attach_openclaw_inquiry(
    result,
    *,
    openclaw_root: Path,
    cache_path: Path | None,
    batch_size: int,
    timeout_seconds: int,
    progress: _ProgressBar | None,
):
    targets = _collect_highlight_targets(result.highlights)
    summary: dict[str, object] = {
        "status": "unavailable",
        "requested": len(targets),
        "completed": 0,
        "failed": 0,
        "cached": 0,
        "queried": 0,
        "agent_id": None,
        "cli_path": None,
        "reason": None,
    }
    if not targets:
        summary["status"] = "empty"
        return replace(result, highlights={**result.highlights, "inquiry_summary": summary})

    cli_path = _discover_openclaw_cli(openclaw_root)
    if cli_path is None:
        summary["reason"] = "OpenClaw CLI was not found on this machine."
        return replace(result, highlights={**result.highlights, "inquiry_summary": summary})

    summary["cli_path"] = str(cli_path)
    agent_id = _discover_default_agent_id(cli_path, timeout_seconds=timeout_seconds) or "main"
    summary["agent_id"] = agent_id

    cache_items = _load_inquiry_cache(cache_path)
    inquiry_by_key: dict[str, dict[str, object]] = {}
    pending: list[dict[str, object]] = []

    for target in targets:
        cache_key = _inquiry_target_key(target)
        cached = cache_items.get(cache_key)
        if cached:
            inquiry_by_key[cache_key] = cached
            summary["cached"] = int(summary["cached"]) + 1
            continue
        pending.append(target)

    batches = list(_chunked(pending, max(batch_size, 1)))
    summary["queried"] = len(pending)
    if progress and batches:
        progress.start_count("Querying highlight files", total=len(pending))

    processed_count = 0
    for batch_index, batch in enumerate(batches, start=1):
        if progress:
            progress.set_label(
                f"Querying highlight files ({processed_count:,}/{len(pending):,} complete, batch {batch_index}/{len(batches)})",
                force=True,
            )
        try:
            results_by_path = _request_openclaw_inquiry_batch_with_progress(
                cli_path,
                agent_id=agent_id,
                batch=batch,
                timeout_seconds=timeout_seconds,
                progress=progress,
            )
        except Exception as exc:  # pragma: no cover - defensive path
            for target in batch:
                summary["failed"] = int(summary["failed"]) + 1
                inquiry_by_key[_inquiry_target_key(target)] = {
                    "status": "error",
                    "message": str(exc),
                }
            if progress:
                progress.count_tick(len(batch), force=True)
                processed_count += len(batch)
            continue

        for target in batch:
            cache_key = _inquiry_target_key(target)
            explanation = results_by_path.get(str(target["absolute_path"]))
            if explanation:
                inquiry_by_key[cache_key] = explanation
                cache_items[cache_key] = explanation
                summary["completed"] = int(summary["completed"]) + 1
            else:
                summary["failed"] = int(summary["failed"]) + 1
                inquiry_by_key[cache_key] = {
                    "status": "error",
                    "message": "OpenClaw did not return a structured explanation for this file.",
                }
        if progress:
            progress.count_tick(len(batch), force=True)
            processed_count += len(batch)

    if progress and batches:
        progress.finish("Highlight file inquiry complete")

    if cache_path and cache_items:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_payload = {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "cli_path": str(cli_path),
            "agent_id": agent_id,
            "items": cache_items,
        }
        cache_path.write_text(json.dumps(cache_payload, indent=2, ensure_ascii=True), encoding="utf-8")

    if summary["completed"] and summary["failed"]:
        summary["status"] = "partial"
    elif summary["completed"] or summary["cached"]:
        summary["status"] = "ok"
    else:
        summary["status"] = "failed"
        summary["reason"] = summary["reason"] or "OpenClaw did not return any structured highlight explanations."

    highlights = dict(result.highlights)
    for key in ("largest_files", "stalest_files", "notable_unknown_files", "symlinks"):
        if isinstance(highlights.get(key), list):
            highlights[key] = [_highlight_with_inquiry(item, inquiry_by_key) for item in highlights[key]]
    top_buckets = highlights.get("top_recommendations_by_bucket")
    if isinstance(top_buckets, dict):
        highlights["top_recommendations_by_bucket"] = {
            bucket: [_highlight_with_inquiry(item, inquiry_by_key) for item in items]
            for bucket, items in top_buckets.items()
        }
    highlights["inquiry_summary"] = summary
    return replace(result, highlights=highlights)


def _highlight_with_inquiry(item: dict[str, object], inquiry_by_key: dict[str, dict[str, object]]) -> dict[str, object]:
    enriched = dict(item)
    inquiry = inquiry_by_key.get(_inquiry_target_key(item))
    if inquiry:
        enriched["inquiry"] = inquiry
    return enriched


def _collect_highlight_targets(highlights: dict[str, object]) -> list[dict[str, object]]:
    targets: list[dict[str, object]] = []
    seen: set[str] = set()

    def add_items(items: object) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            absolute_path = str(item.get("absolute_path") or "").strip()
            if not absolute_path or item.get("kind") == "dir":
                continue
            cache_key = _inquiry_target_key(item)
            if cache_key in seen:
                continue
            seen.add(cache_key)
            targets.append(item)

    for key in ("largest_files", "stalest_files", "notable_unknown_files", "symlinks"):
        add_items(highlights.get(key))

    top_buckets = highlights.get("top_recommendations_by_bucket")
    if isinstance(top_buckets, dict):
        for items in top_buckets.values():
            add_items(items)

    return targets


def _inquiry_target_key(item: dict[str, object]) -> str:
    return "|".join(
        [
            str(item.get("absolute_path") or ""),
            str(item.get("modified_time_utc") or ""),
            str(item.get("size_bytes") or ""),
        ]
    )


def _load_inquiry_cache(cache_path: Path | None) -> dict[str, dict[str, object]]:
    for candidate in _inquiry_cache_candidates(cache_path):
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items = payload.get("items")
        if isinstance(items, dict):
            return items
    return {}


def _inquiry_cache_candidates(cache_path: Path | None) -> list[Path]:
    if cache_path is None:
        return []
    candidates = [cache_path]
    if cache_path.name.endswith(".inquiry-cache.json"):
        legacy_path = cache_path.with_name(cache_path.name.replace(".inquiry-cache.json", ".sleuth-cache.json"))
        if legacy_path != cache_path:
            candidates.append(legacy_path)
    return [candidate for candidate in candidates if candidate.exists()]


def _discover_openclaw_cli(openclaw_root: Path) -> Path | None:
    candidate_strings: list[str] = []
    explicit = os.environ.get("OPENCLAW_CLI")
    if explicit:
        candidate_strings.append(explicit)
    detected = shutil.which("openclaw")
    if detected:
        candidate_strings.append(detected)

    home_root = openclaw_root.expanduser().resolve().parent if openclaw_root.name == ".openclaw" else Path.home()
    candidate_paths = [
        home_root / ".npm-global" / "bin" / "openclaw",
        home_root / ".local" / "bin" / "openclaw",
        home_root / "bin" / "openclaw",
        Path("/usr/local/bin/openclaw"),
        Path("/usr/bin/openclaw"),
    ]
    candidate_strings.extend(str(path) for path in candidate_paths)

    seen: set[str] = set()
    for candidate in candidate_strings:
        resolved = str(Path(candidate).expanduser())
        if resolved in seen:
            continue
        seen.add(resolved)
        path = Path(resolved)
        if path.exists() and os.access(path, os.X_OK):
            return path.resolve()
    return None


def _discover_default_agent_id(cli_path: Path, *, timeout_seconds: int) -> str | None:
    try:
        status = _run_openclaw_json_command([str(cli_path), "status", "--json"], timeout_seconds=min(timeout_seconds, 20))
    except ValueError:
        status = None

    if isinstance(status, dict):
        heartbeat = status.get("heartbeat")
        if isinstance(heartbeat, dict):
            default_agent_id = heartbeat.get("defaultAgentId")
            if isinstance(default_agent_id, str) and default_agent_id.strip():
                return default_agent_id.strip()
        agents = status.get("agents")
        if isinstance(agents, dict):
            default_agent_id = agents.get("defaultId")
            if isinstance(default_agent_id, str) and default_agent_id.strip():
                return default_agent_id.strip()

    try:
        agents_payload = _run_openclaw_json_command([str(cli_path), "agents", "list", "--json"], timeout_seconds=min(timeout_seconds, 20))
    except ValueError:
        return None

    if isinstance(agents_payload, list):
        for item in agents_payload:
            if isinstance(item, dict):
                agent_id = item.get("id")
                if isinstance(agent_id, str) and agent_id.strip():
                    return agent_id.strip()
    return None


def _request_openclaw_inquiry_batch(
    cli_path: Path,
    *,
    agent_id: str,
    batch: list[dict[str, object]],
    timeout_seconds: int,
) -> dict[str, dict[str, object]]:
    payload = _run_openclaw_json_command(
        [
            str(cli_path),
            "agent",
            "--agent",
            agent_id,
            "--message",
            _build_inquiry_prompt(batch),
            "--json",
        ],
        timeout_seconds=timeout_seconds,
    )
    result = payload.get("result") if isinstance(payload, dict) else None
    meta = result.get("meta") if isinstance(result, dict) else {}
    agent_meta = meta.get("agentMeta") if isinstance(meta, dict) else {}
    payloads = result.get("payloads") if isinstance(result, dict) else []
    response_text = "\n".join(
        str(item.get("text") or "")
        for item in payloads
        if isinstance(item, dict) and item.get("text")
    ).strip()
    parsed_items = _parse_inquiry_payload_text(response_text)
    captured_at_utc = datetime.now(UTC).isoformat()

    results: dict[str, dict[str, object]] = {}
    for item in parsed_items:
        absolute_path = str(item.get("absolute_path") or "").strip()
        if not absolute_path:
            continue
        evidence_basis = item.get("evidence_basis")
        if isinstance(evidence_basis, list):
            evidence_basis = [str(value).strip() for value in evidence_basis if str(value).strip()]
        else:
            evidence_basis = []

        recommended_action = str(item.get("recommended_action") or "").strip().lower()
        if recommended_action == "delete":
            recommended_action = "purge_candidate"
        if not recommended_action:
            recommended_action = "review"

        action_reason = str(item.get("action_reason") or item.get("keep_note") or "unsure")
        results[absolute_path] = {
            "status": "ok",
            "what_it_is": str(item.get("what_it_is") or "unsure"),
            "why_it_exists": str(item.get("why_it_exists") or "unsure"),
            "authorship": str(item.get("authorship") or "unsure"),
            "importance": str(item.get("importance") or "unknown"),
            "if_deleted": str(item.get("if_deleted") or "unsure"),
            "recommended_action": recommended_action,
            "action_reason": action_reason,
            "archive_note": str(item.get("archive_note") or "not_needed"),
            "standardness": str(item.get("standardness") or "unknown"),
            "evidence_basis": evidence_basis,
            "keep_note": str(item.get("keep_note") or action_reason),
            "confidence": str(item.get("confidence") or "medium").lower(),
            "model": str(agent_meta.get("model") or ""),
            "session_id": str(agent_meta.get("sessionId") or ""),
            "duration_ms": int(meta.get("durationMs") or 0) if isinstance(meta, dict) else 0,
            "captured_at_utc": captured_at_utc,
        }
    return results


def _build_inquiry_prompt(batch: list[dict[str, object]]) -> str:
    lines = [
        "You are investigating files inside the current OpenClaw installation from the perspective of a cautious system administrator.",
        "Your goal is to help a human understand whether each file should be kept, archived, reviewed, or considered a purge candidate, and why.",
        "",
        "Important rules:",
        "- Use the provided metadata as hints, not as guaranteed truth.",
        '- If something is unclear, say "unsure" instead of inventing details.',
        "- Be conservative about purge recommendations.",
        '- Prefer "review" over "purge_candidate" when evidence is weak.',
        "- Explain why the file likely exists in operational terms.",
        "- Explain how important it is and what would likely happen if it were missing.",
        "- Distinguish between files needed for operation, files mainly useful for history/debugging/audit, and files that appear disposable.",
        "",
        "Return JSON only. Do not use markdown fences.",
        "Return one array with one object per file.",
        'Each object must include: "absolute_path", "what_it_is", "why_it_exists", "authorship", "importance", "if_deleted", "recommended_action", "action_reason", "archive_note", "standardness", "evidence_basis", "confidence".',
        'The "authorship" field must be one of: "likely_openclaw", "likely_openclaw_subsystem", "likely_user_authored", "likely_external_tool", "unknown".',
        'The "importance" field must be one of: "critical", "important", "useful_but_not_required", "low", "unknown".',
        'The "recommended_action" field must be one of: "keep", "archive", "review", "purge_candidate".',
        'The "standardness" field must be one of: "official_standard", "common_convention", "local_custom", "unknown".',
        'The "evidence_basis" field must be an array of short strings chosen from: "path", "role", "preview", "symlink_target", "known_openclaw_file", "known_skill", "unknown".',
        'Confidence must be one of: "high", "medium", "low".',
        "Use \"not_needed\" for archive_note when archiving does not apply.",
        "Keep every field concise and concrete.",
        'Do not use vague wording like "might be something important" unless you also say "unsure".',
        "",
        "Files:",
    ]

    for item in batch:
        lines.append(f"- absolute_path: {item['absolute_path']}")
        lines.append(f"  role: {item.get('role') or 'unknown'}")
        lines.append(f"  recommendation: {item.get('recommendation') or 'review'}")
        lines.append(f"  semantic_category: {item.get('semantic_category') or 'unknown'}")
        if item.get("symlink_target"):
            lines.append(f"  symlink_target: {item['symlink_target']}")
        preview = _trim_inquiry_preview(_sanitize_brand_mentions(item.get("text_preview")))
        if preview:
            lines.append("  preview_bytes: |")
            for preview_line in preview.splitlines():
                lines.append(f"    {preview_line}")
        else:
            lines.append("  preview_bytes: none")
        lines.append("")

    return "\n".join(lines).strip()


def _trim_inquiry_preview(value: object, *, max_chars: int = 420, max_lines: int = 8) -> str:
    if not isinstance(value, str):
        return ""
    trimmed_lines = [line.rstrip() for line in value.strip().splitlines()[:max_lines]]
    trimmed = "\n".join(trimmed_lines).strip()
    if len(trimmed) <= max_chars:
        return trimmed
    return trimmed[: max_chars - 1].rstrip() + "…"


def _parse_inquiry_payload_text(response_text: str) -> list[dict[str, object]]:
    text = response_text.strip()
    if not text:
        return []
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL).strip()

    candidates = [text]
    array_match = re.search(r"(\[\s*\{.*\}\s*\])", text, flags=re.DOTALL)
    if array_match:
        candidates.append(array_match.group(1))
    object_match = re.search(r"(\{\s*\"results\".*\})", text, flags=re.DOTALL)
    if object_match:
        candidates.append(object_match.group(1))

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        if isinstance(payload, dict):
            if isinstance(payload.get("results"), list):
                payload = payload["results"]
            elif payload and all(isinstance(value, dict) for value in payload.values()):
                payload = [{"absolute_path": key, **value} for key, value in payload.items()]
            else:
                payload = [payload]

        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]

    return []


# Backward-compatible aliases for the older internal naming.
_attach_openclaw_sleuth = _attach_openclaw_inquiry
_highlight_with_sleuth = _highlight_with_inquiry
_sleuth_target_key = _inquiry_target_key
_load_sleuth_cache = _load_inquiry_cache
_request_openclaw_sleuth_batch = _request_openclaw_inquiry_batch
_build_sleuth_prompt = _build_inquiry_prompt
_trim_sleuth_preview = _trim_inquiry_preview
_parse_sleuth_payload_text = _parse_inquiry_payload_text


def _run_openclaw_json_command(command: list[str], *, timeout_seconds: int) -> dict[str, object] | list[object]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise ValueError(str(exc)) from exc

    output = (completed.stdout or "").strip()
    error_output = (completed.stderr or "").strip()
    if completed.returncode != 0:
        raise ValueError(error_output or output or f"command failed with exit code {completed.returncode}")
    if not output:
        raise ValueError("command returned no JSON output")
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON output: {exc}") from exc


def _chunked(items: list[dict[str, object]], size: int) -> list[list[dict[str, object]]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def _scan_root(
    *,
    root_type: str,
    root_path: Path,
    planned_paths: list[tuple[Path, str]],
    generated_at_utc: datetime,
    hash_max_bytes: int,
    preview_bytes: int,
    repo_indexes: tuple[_GitRepoIndex, ...],
    errors: list[dict[str, str]],
    progress: _ProgressBar | None,
) -> list[SnapshotEntry]:
    entries: list[SnapshotEntry] = []
    for path, relative_path in planned_paths:
        try:
            stat_result = path.lstat()
        except OSError as exc:
            errors.append({"path": str(path), "error": str(exc)})
            if progress:
                progress.advance()
            continue

        mode = stat_result.st_mode
        if stat.S_ISLNK(mode):
            kind = "symlink"
        elif stat.S_ISDIR(mode):
            kind = "dir"
        else:
            kind = "file"

        name = path.name
        extension = path.suffix or None
        is_hidden = _is_hidden_path(relative_path, root_path.name if relative_path == "." else None)
        modified_time_utc = datetime.fromtimestamp(stat_result.st_mtime, UTC)
        metadata_change_time_utc = datetime.fromtimestamp(stat_result.st_ctime, UTC)
        symlink_target = None
        if kind == "symlink":
            try:
                symlink_target = os.readlink(path)
            except OSError:
                symlink_target = None

        role = _infer_role(root_type, relative_path, kind)
        git = _git_snapshot_for_path(path, kind, repo_indexes)
        size_bytes = stat_result.st_size
        line_count = None
        text_preview = None
        file_hash = None

        if kind == "file":
            try:
                file_hash, line_count, text_preview = _inspect_file(
                    path,
                    extension=extension,
                    size_bytes=size_bytes,
                    hash_max_bytes=hash_max_bytes,
                    preview_bytes=preview_bytes,
                )
            except OSError as exc:
                errors.append({"path": str(path), "error": str(exc)})

        entries.append(
            SnapshotEntry(
                source_path=str(root_path / "content-census-live-scan.json"),
                snapshot_generated_at_utc=generated_at_utc,
                root_type=root_type,
                root_path=str(root_path),
                absolute_path=str(path),
                relative_path=relative_path,
                name=name,
                role=role,
                is_hidden=is_hidden,
                mode_octal=oct(stat.S_IMODE(mode)),
                size_bytes=size_bytes,
                modified_time_utc=modified_time_utc,
                metadata_change_time_utc=metadata_change_time_utc,
                kind=kind,
                extension=extension,
                sha256=file_hash,
                git=git,
                line_count=line_count,
                symlink_target=symlink_target,
                text_preview=text_preview,
            )
        )
        if progress:
            progress.advance()
    return entries


def _iter_scan_paths(
    *,
    root_path: Path,
    include_hidden: bool,
    excluded_dir_names: set[str],
    progress: _ProgressBar | None,
) -> _ScanPlan:
    planned_paths: list[tuple[Path, str]] = []
    skipped_hidden_count = 0
    skipped_excluded_count = 0

    def visit(path: Path, relative_path: str, is_dir: bool) -> None:
        nonlocal skipped_hidden_count, skipped_excluded_count
        planned_paths.append((path, relative_path))
        if progress:
            progress.count_tick()

        if not is_dir:
            return

        try:
            with os.scandir(path) as iterator:
                children = sorted(list(iterator), key=lambda item: item.name.lower())
        except OSError:
            return

        for child in children:
            if not include_hidden and child.name.startswith("."):
                skipped_hidden_count += 1
                continue
            child_is_dir = child.is_dir(follow_symlinks=False)
            if child.name in excluded_dir_names and child_is_dir:
                skipped_excluded_count += 1
                continue
            child_relative = child.name if relative_path == "." else f"{relative_path}/{child.name}"
            visit(Path(child.path), child_relative, child_is_dir)

    visit(root_path, ".", True)
    return _ScanPlan(
        paths=planned_paths,
        skipped_hidden_count=skipped_hidden_count,
        skipped_excluded_count=skipped_excluded_count,
    )


def _inspect_file(
    path: Path,
    *,
    extension: str | None,
    size_bytes: int,
    hash_max_bytes: int,
    preview_bytes: int,
) -> tuple[str | None, int | None, str | None]:
    digest = None
    line_count = None
    text_preview = None

    should_read = size_bytes <= hash_max_bytes or (extension or "").lower() in {".md", ".txt", ".json", ".jsonl", ".toml", ".yaml", ".yml", ".py", ".js", ".ts", ".sh", ".env", ".vcf", ".url"}
    if not should_read:
        return digest, line_count, text_preview

    with path.open("rb") as handle:
        content = handle.read(hash_max_bytes + 1)

    truncated = len(content) > hash_max_bytes or size_bytes > hash_max_bytes
    if not truncated:
        digest = sha256(content).hexdigest()

    decoded = _decode_text_preview(content[:preview_bytes], extension)
    if decoded is not None:
        text_preview = decoded
        if not truncated:
            line_count = content.count(b"\n") + (1 if content and not content.endswith(b"\n") else 0)

    return digest, line_count, text_preview


def _decode_text_preview(content: bytes, extension: str | None) -> str | None:
    if not content:
        return None

    likely_text = (extension or "").lower() in {
        ".cfg",
        ".conf",
        ".css",
        ".csv",
        ".env",
        ".html",
        ".ics",
        ".ini",
        ".js",
        ".json",
        ".jsonl",
        ".key",
        ".log",
        ".md",
        ".mml",
        ".py",
        ".sh",
        ".sql",
        ".svg",
        ".toml",
        ".ts",
        ".tsv",
        ".txt",
        ".url",
        ".vcf",
        ".xml",
        ".yaml",
        ".yml",
    }
    if not likely_text and b"\x00" in content:
        return None

    try:
        return content.decode("utf-8").strip() or None
    except UnicodeDecodeError:
        return None


def _infer_role(root_type: str, relative_path: str, kind: str) -> str:
    path = PurePosixPath(relative_path)
    lower_path = relative_path.lower()
    name = path.name

    if root_type == "workspace":
        if relative_path == "AGENTS.md":
            return "workspace_bootstrap_agents"
        if relative_path == "HEARTBEAT.md":
            return "workspace_bootstrap_heartbeat"
        if relative_path == "IDENTITY.md":
            return "workspace_bootstrap_identity"
        if relative_path == "SOUL.md":
            return "workspace_bootstrap_soul"
        if relative_path == "TOOLS.md":
            return "workspace_bootstrap_tools"
        if relative_path == "USER.md":
            return "workspace_bootstrap_user"
        if path.parent.as_posix() == "memory" and len(name) == 13 and name.endswith(".md"):
            return "memory_daily"
        if relative_path == "skills" or lower_path.startswith("skills/"):
            return "skill_manifest" if name == "SKILL.md" else "skill_file"
        return "workspace_file"

    if relative_path == "openclaw.json":
        return "openclaw_config"
    if relative_path == "memory" or lower_path.startswith("memory/"):
        return "memory_index_or_plugin_data"
    if relative_path == "browser" or lower_path.startswith("browser/"):
        return "browser_data"
    if relative_path == "telegram" or lower_path.startswith("telegram/"):
        return "telegram_data"
    if relative_path == "credentials" or lower_path.startswith("credentials/"):
        return "credentials"
    if relative_path == "media" or lower_path.startswith("media/"):
        return "media"
    if lower_path == "agents/main/sessions/sessions.json":
        return "session_store"
    if lower_path.startswith("agents/main/sessions/"):
        if ".deleted." in lower_path or ".reset." in lower_path or ".orig" in lower_path or ".backup" in lower_path:
            return "session_artifact"
        if name.endswith(".jsonl"):
            return "session_transcript"
    if lower_path.startswith("cron/runs/") and name.endswith(".jsonl"):
        return "cron_run_log"
    return "openclaw_file"


def _build_git_indexes(
    roots: list[Path],
    include_hidden: bool,
    excluded_dir_names: tuple[str, ...],
) -> tuple[_GitRepoIndex, ...]:
    repo_roots: set[Path] = set()
    for root in roots:
        top_level = _git_toplevel(root)
        if top_level is not None:
            repo_roots.add(top_level)
        repo_roots.update(_discover_nested_git_repos(root, include_hidden, set(excluded_dir_names)))

    return tuple(sorted((_index_repo(repo_root) for repo_root in repo_roots), key=lambda item: len(str(item.repo_root)), reverse=True))


def _discover_nested_git_repos(root: Path, include_hidden: bool, excluded_dir_names: set[str]) -> set[Path]:
    repo_roots: set[Path] = set()
    for current_dir, dirnames, _filenames in os.walk(root):
        current_path = Path(current_dir)
        kept_dirnames: list[str] = []
        for dirname in dirnames:
            if dirname == ".git":
                repo_roots.add(current_path.resolve())
                continue
            if dirname in excluded_dir_names:
                continue
            if not include_hidden and dirname.startswith("."):
                continue
            kept_dirnames.append(dirname)
        dirnames[:] = kept_dirnames
    return repo_roots


def _git_toplevel(path: Path) -> Path | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if completed.returncode != 0:
        return None
    top_level = completed.stdout.strip()
    return Path(top_level).resolve() if top_level else None


def _detect_openclaw_version(openclaw_root: Path) -> str | None:
    commands: list[list[str]] = []
    cli_path = _discover_openclaw_cli(openclaw_root)
    if cli_path is not None:
        commands.append([str(cli_path), "--version"])
    commands.extend(
        [
            ["openclaw", "--version"],
            [sys.executable, "-m", "openclaw", "--version"],
        ]
    )

    for command in commands:
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
        output = (completed.stdout or completed.stderr).strip()
        if output:
            return output.splitlines()[0]

    try:
        completed = subprocess.run(
            ["git", "-C", str(openclaw_root), "describe", "--tags", "--always", "--dirty"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    output = completed.stdout.strip()
    return f"git {output}" if output else None


def _index_repo(repo_root: Path) -> _GitRepoIndex:
    tracked = set(_git_z_list(repo_root, ["ls-files", "--cached"]))
    ignored = set(_git_z_list(repo_root, ["ls-files", "--others", "-i", "--exclude-standard"]))
    untracked = set(_git_z_list(repo_root, ["ls-files", "--others", "--exclude-standard"]))
    modified = set(_git_z_list(repo_root, ["diff", "--name-only"]))
    staged = set(_git_z_list(repo_root, ["diff", "--name-only", "--cached"]))
    return _GitRepoIndex(
        repo_root=repo_root,
        tracked=tracked,
        ignored=ignored,
        untracked=untracked,
        modified=modified,
        staged=staged,
    )


def _git_z_list(repo_root: Path, args: list[str]) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *args, "-z"],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        return []
    if completed.returncode != 0 or not completed.stdout:
        return []
    return [item.decode("utf-8", "replace") for item in completed.stdout.split(b"\0") if item]


def _git_snapshot_for_path(path: Path, kind: str, repo_indexes: tuple[_GitRepoIndex, ...]) -> GitSnapshot:
    absolute_path = Path(os.path.abspath(path))
    for repo_index in repo_indexes:
        try:
            relative_path = absolute_path.relative_to(repo_index.repo_root).as_posix()
        except ValueError:
            continue

        if kind == "dir":
            return GitSnapshot(
                repo_root=str(repo_index.repo_root),
                repo_relative_path=relative_path,
                tracked=False,
                ignored=False,
                untracked=False,
                modified=False,
                staged=False,
            )

        return GitSnapshot(
            repo_root=str(repo_index.repo_root),
            repo_relative_path=relative_path,
            tracked=relative_path in repo_index.tracked,
            ignored=relative_path in repo_index.ignored,
            untracked=relative_path in repo_index.untracked,
            modified=relative_path in repo_index.modified,
            staged=relative_path in repo_index.staged,
        )

    return GitSnapshot(
        repo_root=None,
        repo_relative_path=None,
        tracked=None,
        ignored=None,
        untracked=None,
        modified=None,
        staged=None,
    )


def _ordered_counts(counter: Counter[str], preferred_order: list[str] | None = None) -> list[tuple[str, int]]:
    items: list[tuple[str, int]] = []
    preferred = preferred_order or []
    seen: set[str] = set()
    for key in preferred:
        if key in counter:
            items.append((key, counter[key]))
            seen.add(key)
    items.extend(sorted(((key, value) for key, value in counter.items() if key not in seen), key=lambda item: (-item[1], item[0])))
    return items


def _is_hidden_path(relative_path: str, root_name: str | None) -> bool:
    if relative_path == ".":
        return bool(root_name and root_name.startswith("."))
    return any(part.startswith(".") for part in PurePosixPath(relative_path).parts)


def _rewrite_html_for_live_scan(report_html: str, snapshot: SnapshotDocument) -> str:
    replacements = {
        "Context Census Report": "Context Census Report",
        "OpenClaw File Analysis": "OpenClaw File Analysis",
        "Offline Analysis": "Local Filesystem Scan",
        "OpenClaw writes a large number of workspace, runtime, memory, skill, and support files, and it can be hard to understand which ones matter most. This standalone HTML report keeps the analysis local and read-only while helping you understand which files are likely important, which deserve review, and which appear lower-priority.": "OpenClaw writes a large number of workspace, runtime, memory, skill, and support files, and it can be hard to understand which ones matter most. This standalone HTML report keeps the live scan local and read-only while helping you understand which files are likely important, which deserve review, and which appear lower-priority.",
        "The snapshot already assigned a semantic role to the file, so this is closer to an explicit classification than a filename guess.": "The analyzer mapped this path to a semantic role from location and naming heuristics, so this is stronger than a generic filename guess.",
        "Snapshot role semantics are one of the strongest inputs, so these codes often drive the recommendation directly.": "Role semantics are one of the strongest inputs, so these codes often drive the recommendation directly.",
        "The snapshot captured Git state for this path, such as tracked, ignored, or untracked.": "The scan captured Git state for this path, such as tracked, ignored, or untracked.",
        "The file crossed a staleness threshold relative to the snapshot timestamp used for this run.": "The file crossed a staleness threshold relative to the scan timestamp used for this run.",
        "Not present in this snapshot": "Not present in this scan",
        "No concrete example in this snapshot.": "No concrete example in this scan.",
    }

    snapshot_hero = (
        "OpenClaw writes a large number of workspace, runtime, memory, skill, and support files, and it can be hard to understand which ones matter most. This standalone HTML report keeps the analysis local and read-only while helping you understand which files are likely important, which deserve review, and which appear lower-priority."
    )
    live_hero = (
        "OpenClaw writes a large number of workspace, runtime, memory, skill, and support files, and it can be hard to understand which ones matter most. This standalone HTML report keeps the live scan local and read-only while helping you understand which files are likely important, which deserve review, and which appear lower-priority."
    )
    report_html = report_html.replace(snapshot_hero, live_hero)

    for old, new in replacements.items():
        if "PLACEHOLDER" in old:
            continue
        report_html = report_html.replace(old, new)
    return report_html
# --- End inlined module: live_scan.py ---

if __name__ == "__main__":
    raise SystemExit(main())
