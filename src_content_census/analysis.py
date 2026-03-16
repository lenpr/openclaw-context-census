# --- Begin inlined module: analysis.py ---
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import PurePosixPath


REPORT_VERSION = "0.1"

REASON_CATALOG: dict[str, str] = {
    "ROLE_BOOTSTRAP": "Workspace bootstrap file.",
    "ROLE_BROWSER_DATA": "Browser state or browser-export data.",
    "ROLE_CONFIG": "Configuration or policy file.",
    "ROLE_CREDENTIALS": "Credential or auth-related file.",
    "ROLE_CRON_LOG": "Cron run log or scheduler output.",
    "ROLE_MEMORY_DAILY": "Daily memory file.",
    "ROLE_MEMORY_INDEX": "Memory index or plugin data.",
    "ROLE_MEMORY_LONGTERM": "Long-term memory file.",
    "ROLE_MEDIA": "Media or blob-like file.",
    "ROLE_SESSION_ARTIFACT": "Session artifact such as reset/deleted output.",
    "ROLE_SESSION_STORE": "Session store/state file.",
    "ROLE_SESSION_TRANSCRIPT": "Session transcript file.",
    "ROLE_SKILL_FILE": "Skill source or support file.",
    "ROLE_SKILL_MANIFEST": "Skill manifest file.",
    "ROLE_TELEGRAM_DATA": "Telegram state or export data.",
    "ROOT_OPENCLAW": "Entry belongs to the OpenClaw root.",
    "ROOT_WORKSPACE": "Entry belongs to the workspace root.",
    "WORKSPACE_MIRROR": "OpenClaw workspace mirror duplicates a workspace entry.",
    "PATH_HIDDEN": "Hidden path.",
    "PATH_TEMP_LIKE": "Temp-like or cache-like path.",
    "PATH_BUILD_ARTIFACT": "Build output path.",
    "PATH_MEETING_NOTES": "Workspace notes/document path.",
    "PATH_TOOLS": "Tooling path.",
    "PATH_MODELS": "Model or model-cache path.",
    "PATH_LOGS": "Log-like path.",
    "PATH_BACKUP": "Backup-like filename or suffix.",
    "PATH_CREDENTIALS": "Credential directory path.",
    "KIND_DIRECTORY": "Directory entries are summarized only.",
    "KIND_SYMLINK": "Symlink requires explicit manual review.",
    "LARGE_FILE": "Large file by configured threshold.",
    "STALE_30D": "Older than the archive threshold.",
    "STALE_90D": "Older than 90 days.",
    "STALE_180D": "Older than the stale threshold.",
    "GIT_TRACKED": "Tracked by Git.",
    "GIT_MODIFIED": "Tracked file has local modifications.",
    "GIT_UNTRACKED": "Untracked in Git.",
    "GIT_IGNORED": "Ignored by Git.",
    "DUPLICATE_HASH": "Hash is shared with another file in the analyzed set.",
    "TEXT_LIKE": "Looks like a text file.",
    "BINARY_LIKE": "Looks like a binary or blob-like file.",
    "FILE_EMPTY": "Empty file.",
    "UNKNOWN_ROLE": "Role is generic or unknown.",
    "SENSITIVE_PATH": "Likely sensitive data.",
}

TEXT_EXTENSIONS = {
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

BINARY_EXTENSIONS = {
    ".avi",
    ".bin",
    ".bmp",
    ".db",
    ".dylib",
    ".exe",
    ".gguf",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".pdf",
    ".png",
    ".so",
    ".sqlite",
    ".tar",
    ".wav",
    ".webp",
    ".zip",
}

MEDIA_EXTENSIONS = {
    ".avi",
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".png",
    ".wav",
    ".webp",
}

MODEL_EXTENSIONS = {
    ".bin",
    ".gguf",
}

GENERIC_ROLES = {"openclaw_file", "workspace_file"}

FIXED_HARD_RULES: dict[str, tuple[str, Recommendation, Confidence]] = {
    "memory_daily": ("ROLE_MEMORY_DAILY", Recommendation.KEEP_SYNCED, Confidence.HIGH),
    "skill_manifest": ("ROLE_SKILL_MANIFEST", Recommendation.KEEP_SYNCED, Confidence.HIGH),
    "skill_file": ("ROLE_SKILL_FILE", Recommendation.KEEP_SYNCED, Confidence.HIGH),
    "memory_index_or_plugin_data": ("ROLE_MEMORY_INDEX", Recommendation.REVIEW, Confidence.MEDIUM),
    "browser_data": ("ROLE_BROWSER_DATA", Recommendation.REVIEW, Confidence.MEDIUM),
    "telegram_data": ("ROLE_TELEGRAM_DATA", Recommendation.REVIEW, Confidence.MEDIUM),
    "media": ("ROLE_MEDIA", Recommendation.ARCHIVE_CANDIDATE, Confidence.MEDIUM),
}


class _AnalysisContext:
    def __init__(self, snapshots: tuple[SnapshotDocument, ...], config: AnalysisConfig, reference_time_utc: datetime) -> None:
        self.snapshots = snapshots
        self.config = config
        self.reference_time_utc = reference_time_utc
        self.workspace_paths = {
            entry.relative_path
            for snapshot in snapshots
            for entry in snapshot.entries
            if entry.root_type == "workspace"
        }
        self.hash_counts = Counter(
            entry.sha256
            for snapshot in snapshots
            for entry in snapshot.entries
            if (
                entry.kind == "file"
                and entry.sha256
                and entry.size_bytes > 0
                and not _is_workspace_mirror(entry, self)
            )
        )


def analyze_snapshots(snapshots: list[SnapshotDocument], config: AnalysisConfig | None = None) -> AnalysisResult:
    """Normalize, classify, and summarize one or more snapshot documents."""
    requested_input_count = len(snapshots)
    deduplicated_snapshots, duplicate_inputs = _deduplicate_snapshots(snapshots)
    ordered_snapshots = tuple(sorted(deduplicated_snapshots, key=lambda snapshot: snapshot.source_path))
    effective_config = config or AnalysisConfig()
    reference_time_utc = effective_config.reference_time_utc or max(
        snapshot.generated_at_utc for snapshot in ordered_snapshots
    )
    reference_time_utc = reference_time_utc.astimezone(UTC)
    effective_config = replace(effective_config, reference_time_utc=reference_time_utc)

    context = _AnalysisContext(ordered_snapshots, effective_config, reference_time_utc)

    analyzed_entries = tuple(
        sorted(
            (
                _classify_entry(entry, context)
                for snapshot in ordered_snapshots
                for entry in snapshot.entries
            ),
            key=lambda item: (item.source_name, item.root_type, item.relative_path, item.kind),
        )
    )

    bucket_counts = _ordered_counter(
        Counter(entry.recommendation.value for entry in analyzed_entries),
        [
            Recommendation.KEEP_SYNCED.value,
            Recommendation.CANDIDATE_TO_SYNC.value,
            Recommendation.REVIEW.value,
            Recommendation.ARCHIVE_CANDIDATE.value,
            Recommendation.PURGE_CANDIDATE.value,
            Recommendation.IGNORE.value,
        ],
    )
    role_counts = _sort_counter_desc(Counter(entry.role for entry in analyzed_entries))
    semantic_category_counts = _sort_counter_desc(Counter(entry.semantic_category for entry in analyzed_entries))
    kind_counts = _ordered_counter(Counter(entry.kind for entry in analyzed_entries), ["file", "dir", "symlink"])

    duplicate_groups = _exact_duplicate_file_groups(analyzed_entries)
    highlights = {
        "largest_files": [_entry_to_highlight(entry) for entry in _top_largest(analyzed_entries, limit=10)],
        "stalest_files": [_entry_to_highlight(entry) for entry in _top_stalest(analyzed_entries, limit=10)],
        "duplicate_groups_summary": _duplicate_group_summary(duplicate_groups),
        "duplicate_groups": duplicate_groups[:10],
        "notable_unknown_files": [
            _entry_to_highlight(entry)
            for entry in _top_unknowns(analyzed_entries, limit=10)
        ],
        "symlinks": [_entry_to_highlight(entry) for entry in analyzed_entries if entry.kind == "symlink"],
        "top_recommendations_by_bucket": {
            bucket.value: [_entry_to_highlight(entry) for entry in _top_bucket_entries(analyzed_entries, bucket, limit=5)]
            for bucket in Recommendation
            if bucket is not Recommendation.IGNORE
        },
    }

    return AnalysisResult(
        report_version=REPORT_VERSION,
        generated_at_utc=reference_time_utc,
        reference_time_utc=reference_time_utc,
        config=effective_config,
        requested_input_count=requested_input_count,
        inputs=ordered_snapshots,
        duplicate_inputs=duplicate_inputs,
        entries=analyzed_entries,
        bucket_counts=bucket_counts,
        role_counts=role_counts,
        semantic_category_counts=semantic_category_counts,
        kind_counts=kind_counts,
        highlights=highlights,
    )


def _deduplicate_snapshots(
    snapshots: list[SnapshotDocument],
) -> tuple[tuple[SnapshotDocument, ...], tuple[DuplicateSnapshot, ...]]:
    groups: dict[str, list[SnapshotDocument]] = {}
    for snapshot in snapshots:
        groups.setdefault(_snapshot_content_signature(snapshot), []).append(snapshot)

    kept_snapshots: list[SnapshotDocument] = []
    duplicate_inputs: list[DuplicateSnapshot] = []

    for group in groups.values():
        preferred = max(
            group,
            key=lambda snapshot: (
                snapshot.scan.preview_bytes,
                snapshot.generated_at_utc,
                snapshot.source_path,
            ),
        )
        kept_snapshots.append(preferred)

        for snapshot in group:
            if snapshot is preferred:
                continue
            duplicate_inputs.append(
                DuplicateSnapshot(
                    skipped_source_path=snapshot.source_path,
                    kept_source_path=preferred.source_path,
                    reason="normalized entries matched another snapshot after ignoring preview-only fields and capture-time timestamp drift; kept the richer preview or newer capture",
                    skipped_preview_bytes=snapshot.scan.preview_bytes,
                    kept_preview_bytes=preferred.scan.preview_bytes,
                )
            )

    return tuple(kept_snapshots), tuple(
        sorted(
            duplicate_inputs,
            key=lambda duplicate: (duplicate.kept_source_path, duplicate.skipped_source_path),
        )
    )


def _snapshot_content_signature(snapshot: SnapshotDocument) -> str:
    digest = sha256()
    for entry in sorted(snapshot.entries, key=lambda item: (item.root_type, item.relative_path, item.kind, item.role, item.name)):
        entry_signature = (
            entry.root_type,
            entry.root_path,
            entry.absolute_path,
            entry.relative_path,
            entry.name,
            entry.role,
            entry.is_hidden,
            entry.mode_octal,
            entry.size_bytes,
            entry.kind,
            entry.extension,
            entry.sha256,
            entry.git.repo_root,
            entry.git.repo_relative_path,
            entry.git.tracked,
            entry.git.ignored,
            entry.git.untracked,
            entry.git.modified,
            entry.git.staged,
            entry.line_count,
            entry.symlink_target,
        )
        digest.update(repr(entry_signature).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _classify_entry(entry: SnapshotEntry, context: _AnalysisContext) -> AnalyzedEntry:
    logical_path = _logical_path(entry)
    age_days = max((context.reference_time_utc - entry.modified_time_utc).days, 0)
    semantic_category = _semantic_category(entry, logical_path)

    reasons: list[str] = []
    reasons.append("ROOT_WORKSPACE" if entry.root_type == "workspace" else "ROOT_OPENCLAW")

    if entry.kind == "dir":
        reasons.append("KIND_DIRECTORY")
        reasons.extend(_common_signal_reasons(entry, age_days, context, logical_path))
        return _build_result(
            entry=entry,
            logical_path=logical_path,
            semantic_category=semantic_category,
            recommendation=Recommendation.IGNORE,
            confidence=Confidence.HIGH,
            reasons=reasons,
            age_days=age_days,
        )

    if _is_workspace_mirror(entry, context):
        reasons.append("WORKSPACE_MIRROR")
        reasons.extend(_common_signal_reasons(entry, age_days, context, logical_path))
        return _build_result(
            entry=entry,
            logical_path=logical_path,
            semantic_category=semantic_category,
            recommendation=Recommendation.IGNORE,
            confidence=Confidence.HIGH,
            reasons=reasons,
            age_days=age_days,
        )

    if entry.kind == "symlink":
        reasons.append("KIND_SYMLINK")
        if _is_build_artifact_path(logical_path):
            reasons.append("PATH_BUILD_ARTIFACT")
        reasons.extend(_common_signal_reasons(entry, age_days, context, logical_path))
        return _build_result(
            entry=entry,
            logical_path=logical_path,
            semantic_category=semantic_category,
            recommendation=Recommendation.REVIEW,
            confidence=Confidence.MEDIUM,
            reasons=reasons,
            age_days=age_days,
        )

    hard_result = _classify_hard_rules(entry, logical_path, age_days, semantic_category, reasons, context)
    if hard_result is not None:
        return hard_result

    return _classify_soft_rules(entry, logical_path, age_days, semantic_category, reasons, context)


def _classify_hard_rules(
    entry: SnapshotEntry,
    logical_path: str,
    age_days: int,
    semantic_category: str,
    reasons: list[str],
    context: _AnalysisContext,
) -> AnalyzedEntry | None:
    basename = PurePosixPath(logical_path).name

    if basename.upper() == "MEMORY.MD":
        return _build_hard_rule_result(
            entry,
            logical_path,
            age_days,
            semantic_category,
            reasons,
            context,
            "ROLE_MEMORY_LONGTERM",
            Recommendation.KEEP_SYNCED,
            Confidence.HIGH,
        )

    fixed_role_rule = FIXED_HARD_RULES.get(entry.role)
    if fixed_role_rule is not None:
        reason_code, recommendation, confidence = fixed_role_rule
        return _build_hard_rule_result(
            entry,
            logical_path,
            age_days,
            semantic_category,
            reasons,
            context,
            reason_code,
            recommendation,
            confidence,
        )

    if entry.role.startswith("workspace_bootstrap_"):
        return _build_hard_rule_result(
            entry,
            logical_path,
            age_days,
            semantic_category,
            reasons,
            context,
            "ROLE_BOOTSTRAP",
            Recommendation.KEEP_SYNCED,
            Confidence.HIGH,
        )

    if entry.role == "openclaw_config" or _is_config_path(logical_path):
        return _classify_config_hard_rule(entry, logical_path, age_days, semantic_category, reasons, context)

    if entry.role == "credentials" or _is_sensitive_path(logical_path):
        return _classify_credentials_hard_rule(entry, logical_path, age_days, semantic_category, reasons, context)

    if entry.role == "session_store":
        return _classify_session_store_hard_rule(entry, logical_path, age_days, semantic_category, reasons, context)

    if entry.role == "session_transcript":
        return _classify_session_transcript_hard_rule(entry, logical_path, age_days, semantic_category, reasons, context)

    if entry.role == "session_artifact":
        return _classify_session_artifact_hard_rule(entry, logical_path, age_days, semantic_category, reasons, context)

    if entry.role == "cron_run_log":
        return _classify_cron_log_hard_rule(entry, logical_path, age_days, semantic_category, reasons, context)

    if _is_model_path(logical_path):
        return _build_hard_rule_result(
            entry,
            logical_path,
            age_days,
            semantic_category,
            reasons,
            context,
            "PATH_MODELS",
            Recommendation.ARCHIVE_CANDIDATE,
            Confidence.HIGH,
        )

    return None


def _build_hard_rule_result(
    entry: SnapshotEntry,
    logical_path: str,
    age_days: int,
    semantic_category: str,
    reasons: list[str],
    context: _AnalysisContext,
    reason_code: str,
    recommendation: Recommendation,
    confidence: Confidence,
    *,
    extra_reasons: tuple[str, ...] = (),
) -> AnalyzedEntry:
    reasons.append(reason_code)
    reasons.extend(extra_reasons)
    reasons.extend(_common_signal_reasons(entry, age_days, context, logical_path))
    return _build_result(entry, logical_path, semantic_category, recommendation, confidence, reasons, age_days)


def _classify_config_hard_rule(
    entry: SnapshotEntry,
    logical_path: str,
    age_days: int,
    semantic_category: str,
    reasons: list[str],
    context: _AnalysisContext,
) -> AnalyzedEntry:
    if _is_backup_like(entry, logical_path):
        return _build_hard_rule_result(
            entry,
            logical_path,
            age_days,
            semantic_category,
            reasons,
            context,
            "ROLE_CONFIG",
            Recommendation.ARCHIVE_CANDIDATE,
            Confidence.MEDIUM,
            extra_reasons=("PATH_BACKUP",),
        )
    return _build_hard_rule_result(
        entry,
        logical_path,
        age_days,
        semantic_category,
        reasons,
        context,
        "ROLE_CONFIG",
        Recommendation.REVIEW,
        Confidence.HIGH,
    )


def _classify_credentials_hard_rule(
    entry: SnapshotEntry,
    logical_path: str,
    age_days: int,
    semantic_category: str,
    reasons: list[str],
    context: _AnalysisContext,
) -> AnalyzedEntry:
    extra_reasons = ["SENSITIVE_PATH"]
    if _contains_segment(logical_path, {"credentials"}):
        extra_reasons.append("PATH_CREDENTIALS")
    return _build_hard_rule_result(
        entry,
        logical_path,
        age_days,
        semantic_category,
        reasons,
        context,
        "ROLE_CREDENTIALS",
        Recommendation.REVIEW,
        Confidence.HIGH,
        extra_reasons=tuple(extra_reasons),
    )


def _classify_session_store_hard_rule(
    entry: SnapshotEntry,
    logical_path: str,
    age_days: int,
    semantic_category: str,
    reasons: list[str],
    context: _AnalysisContext,
) -> AnalyzedEntry:
    if age_days >= context.config.archive_days:
        recommendation = Recommendation.ARCHIVE_CANDIDATE
        confidence = Confidence.MEDIUM
    else:
        recommendation = Recommendation.REVIEW
        confidence = Confidence.HIGH
    return _build_hard_rule_result(
        entry,
        logical_path,
        age_days,
        semantic_category,
        reasons,
        context,
        "ROLE_SESSION_STORE",
        recommendation,
        confidence,
    )


def _classify_session_transcript_hard_rule(
    entry: SnapshotEntry,
    logical_path: str,
    age_days: int,
    semantic_category: str,
    reasons: list[str],
    context: _AnalysisContext,
) -> AnalyzedEntry:
    if age_days >= context.config.archive_days or entry.size_bytes >= context.config.large_file_bytes:
        recommendation = Recommendation.ARCHIVE_CANDIDATE
    else:
        recommendation = Recommendation.REVIEW
    return _build_hard_rule_result(
        entry,
        logical_path,
        age_days,
        semantic_category,
        reasons,
        context,
        "ROLE_SESSION_TRANSCRIPT",
        recommendation,
        Confidence.MEDIUM,
    )


def _classify_session_artifact_hard_rule(
    entry: SnapshotEntry,
    logical_path: str,
    age_days: int,
    semantic_category: str,
    reasons: list[str],
    context: _AnalysisContext,
) -> AnalyzedEntry:
    if _should_consider_purge(entry, logical_path, age_days, context):
        recommendation = Recommendation.PURGE_CANDIDATE
        confidence = Confidence.MEDIUM
    else:
        recommendation = Recommendation.ARCHIVE_CANDIDATE
        confidence = Confidence.HIGH if _is_backup_like(entry, logical_path) else Confidence.MEDIUM
    return _build_hard_rule_result(
        entry,
        logical_path,
        age_days,
        semantic_category,
        reasons,
        context,
        "ROLE_SESSION_ARTIFACT",
        recommendation,
        confidence,
    )


def _classify_cron_log_hard_rule(
    entry: SnapshotEntry,
    logical_path: str,
    age_days: int,
    semantic_category: str,
    reasons: list[str],
    context: _AnalysisContext,
) -> AnalyzedEntry:
    if _should_consider_purge(entry, logical_path, age_days, context):
        recommendation = Recommendation.PURGE_CANDIDATE
    else:
        recommendation = Recommendation.ARCHIVE_CANDIDATE
    return _build_hard_rule_result(
        entry,
        logical_path,
        age_days,
        semantic_category,
        reasons,
        context,
        "ROLE_CRON_LOG",
        recommendation,
        Confidence.MEDIUM,
    )


def _classify_soft_rules(
    entry: SnapshotEntry,
    logical_path: str,
    age_days: int,
    semantic_category: str,
    reasons: list[str],
    context: _AnalysisContext,
) -> AnalyzedEntry:
    text_like = _is_text_like(entry)
    temp_like = _is_temp_like(logical_path)
    build_artifact = _is_build_artifact_path(logical_path)
    media_like = _is_media_like(entry, logical_path)
    binary_like = _is_binary_like(entry, logical_path)

    if entry.git.tracked:
        reasons.append("GIT_TRACKED")
        if entry.git.modified:
            reasons.append("GIT_MODIFIED")
        reasons.extend(_common_signal_reasons(entry, age_days, context, logical_path, include_git=False))
        return _build_result(
            entry,
            logical_path,
            semantic_category,
            Recommendation.CANDIDATE_TO_SYNC,
            Confidence.HIGH,
            reasons,
            age_days,
        )

    if entry.root_type == "workspace" and _is_workspace_user_content(entry, logical_path):
        if _contains_segment(logical_path, {"meeting notes"}):
            reasons.append("PATH_MEETING_NOTES")
        reasons.extend(_common_signal_reasons(entry, age_days, context, logical_path))
        return _build_result(
            entry,
            logical_path,
            semantic_category,
            Recommendation.CANDIDATE_TO_SYNC,
            Confidence.MEDIUM,
            reasons,
            age_days,
        )

    if _is_log_like(logical_path):
        reasons.append("PATH_LOGS")
        reasons.extend(_common_signal_reasons(entry, age_days, context, logical_path))
        recommendation = Recommendation.PURGE_CANDIDATE if _should_consider_purge(entry, logical_path, age_days, context) else Recommendation.ARCHIVE_CANDIDATE
        confidence = Confidence.LOW if recommendation is Recommendation.PURGE_CANDIDATE else Confidence.MEDIUM
        return _build_result(entry, logical_path, semantic_category, recommendation, confidence, reasons, age_days)

    if temp_like or build_artifact:
        if temp_like:
            reasons.append("PATH_TEMP_LIKE")
        if build_artifact:
            reasons.append("PATH_BUILD_ARTIFACT")
        reasons.extend(_common_signal_reasons(entry, age_days, context, logical_path))
        recommendation = Recommendation.PURGE_CANDIDATE if _should_consider_purge(entry, logical_path, age_days, context) else Recommendation.ARCHIVE_CANDIDATE
        confidence = Confidence.MEDIUM if recommendation is Recommendation.ARCHIVE_CANDIDATE else Confidence.LOW
        return _build_result(entry, logical_path, semantic_category, recommendation, confidence, reasons, age_days)

    if media_like or binary_like:
        if _contains_segment(logical_path, {"tools"}):
            reasons.append("PATH_TOOLS")
        reasons.extend(_common_signal_reasons(entry, age_days, context, logical_path))
        return _build_result(
            entry,
            logical_path,
            semantic_category,
            Recommendation.ARCHIVE_CANDIDATE,
            Confidence.MEDIUM,
            reasons,
            age_days,
        )

    reasons.append("UNKNOWN_ROLE" if entry.role in GENERIC_ROLES else entry.role.upper())
    reasons.extend(_common_signal_reasons(entry, age_days, context, logical_path))
    recommendation = Recommendation.REVIEW
    confidence = Confidence.LOW if entry.role in GENERIC_ROLES and not text_like else Confidence.MEDIUM
    return _build_result(entry, logical_path, semantic_category, recommendation, confidence, reasons, age_days)


def _build_result(
    entry: SnapshotEntry,
    logical_path: str,
    semantic_category: str,
    recommendation: Recommendation,
    confidence: Confidence,
    reasons: list[str],
    age_days: int,
) -> AnalyzedEntry:
    unique_reasons = tuple(_dedupe_reasons(reasons))
    explanation = _build_explanation(recommendation, confidence, unique_reasons)
    return AnalyzedEntry(
        source_path=entry.source_path,
        source_name=entry.source_name,
        snapshot_generated_at_utc=entry.snapshot_generated_at_utc,
        root_type=entry.root_type,
        root_path=entry.root_path,
        absolute_path=entry.absolute_path,
        relative_path=entry.relative_path,
        logical_path=logical_path,
        name=entry.name,
        role=entry.role,
        kind=entry.kind,
        extension=entry.extension,
        semantic_category=semantic_category,
        recommendation=recommendation,
        confidence=confidence,
        reason_codes=unique_reasons,
        explanation=explanation,
        is_hidden=entry.is_hidden,
        size_bytes=entry.size_bytes,
        modified_time_utc=entry.modified_time_utc,
        metadata_change_time_utc=entry.metadata_change_time_utc,
        age_days=age_days,
        mode_octal=entry.mode_octal,
        sha256=entry.sha256,
        git=entry.git,
        line_count=entry.line_count,
        symlink_target=entry.symlink_target,
        text_preview=entry.text_preview,
    )


def _common_signal_reasons(
    entry: SnapshotEntry,
    age_days: int,
    context: _AnalysisContext,
    logical_path: str,
    *,
    include_git: bool = True,
) -> list[str]:
    reasons: list[str] = []
    if entry.is_hidden:
        reasons.append("PATH_HIDDEN")

    if include_git:
        if entry.git.tracked:
            reasons.append("GIT_TRACKED")
        if entry.git.modified:
            reasons.append("GIT_MODIFIED")
        if entry.git.untracked:
            reasons.append("GIT_UNTRACKED")
        if entry.git.ignored:
            reasons.append("GIT_IGNORED")

    if age_days >= context.config.stale_days:
        reasons.append("STALE_180D")
    elif age_days >= 90:
        reasons.append("STALE_90D")
    elif age_days >= context.config.archive_days:
        reasons.append("STALE_30D")

    if entry.size_bytes == 0:
        reasons.append("FILE_EMPTY")
    if entry.size_bytes >= context.config.large_file_bytes:
        reasons.append("LARGE_FILE")

    if _is_text_like(entry):
        reasons.append("TEXT_LIKE")
    elif _is_binary_like(entry, logical_path):
        reasons.append("BINARY_LIKE")

    if _contains_segment(logical_path, {"tools"}):
        reasons.append("PATH_TOOLS")
    if _contains_segment(logical_path, {"logs"}) or logical_path.lower().endswith(".log"):
        reasons.append("PATH_LOGS")
    if _is_backup_like(entry, logical_path):
        reasons.append("PATH_BACKUP")
    if entry.sha256 and context.hash_counts.get(entry.sha256, 0) > 1:
        reasons.append("DUPLICATE_HASH")

    return reasons


def _build_explanation(recommendation: Recommendation, confidence: Confidence, reason_codes: tuple[str, ...]) -> str:
    intro = {
        Recommendation.KEEP_SYNCED: "Recommended to keep synced",
        Recommendation.CANDIDATE_TO_SYNC: "Looks like a reasonable sync candidate",
        Recommendation.REVIEW: "Needs manual review",
        Recommendation.ARCHIVE_CANDIDATE: "Looks better suited for archive than active sync",
        Recommendation.PURGE_CANDIDATE: "Looks like a cautious purge candidate after manual review",
        Recommendation.IGNORE: "Ignored in the actionable recommendations",
    }[recommendation]

    details = [REASON_CATALOG.get(code, code).rstrip(".") for code in reason_codes[:3]]
    if not details:
        return f"{intro} with {confidence.value} confidence."
    joined = details[0] if len(details) == 1 else ", ".join(details[:-1]) + f", and {details[-1]}"
    return f"{intro} with {confidence.value} confidence because it matches these signals: {joined}."


def _dedupe_reasons(reasons: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for reason in reasons:
        if reason not in REASON_CATALOG and not reason.startswith("ROLE_"):
            continue
        if reason not in seen:
            seen.add(reason)
            unique.append(reason)
    return unique


def _logical_path(entry: SnapshotEntry) -> str:
    if entry.root_type == "openclaw" and entry.relative_path == "workspace":
        return "."
    if entry.root_type == "openclaw" and entry.relative_path.startswith("workspace/"):
        return entry.relative_path.removeprefix("workspace/")
    return entry.relative_path


def _is_workspace_mirror(entry: SnapshotEntry, context: _AnalysisContext) -> bool:
    if entry.root_type != "openclaw":
        return False
    logical_path = _logical_path(entry)
    return logical_path in context.workspace_paths


def _is_text_like(entry: SnapshotEntry) -> bool:
    if entry.line_count is not None:
        return True
    if entry.text_preview:
        return True
    return (entry.extension or "").lower() in TEXT_EXTENSIONS


def _is_binary_like(entry: SnapshotEntry, logical_path: str) -> bool:
    extension = (entry.extension or "").lower()
    if extension in BINARY_EXTENSIONS:
        return True
    if _is_model_path(logical_path):
        return True
    return False


def _is_media_like(entry: SnapshotEntry, logical_path: str) -> bool:
    extension = (entry.extension or "").lower()
    if entry.role == "media":
        return True
    if extension in MEDIA_EXTENSIONS:
        return True
    return _contains_segment(logical_path, {"media"})


def _is_model_path(logical_path: str) -> bool:
    lower_path = logical_path.lower()
    if lower_path.startswith("models/"):
        return True
    path = PurePosixPath(lower_path)
    return path.suffix in MODEL_EXTENSIONS and any(segment == "models" for segment in path.parts)


def _is_temp_like(logical_path: str) -> bool:
    path = PurePosixPath(logical_path.lower())
    temp_segments = {"cache", "caches", "temp", "tmp", ".pytest_cache", "__pycache__"}
    if any(segment in temp_segments for segment in path.parts):
        return True
    basename = path.name
    return basename.startswith("tmp") or ".tmp" in basename


def _is_build_artifact_path(logical_path: str) -> bool:
    path = PurePosixPath(logical_path.lower())
    build_segments = {"build", "dist", "cmakefiles", "target"}
    return any(segment in build_segments for segment in path.parts)


def _is_backup_like(entry: SnapshotEntry, logical_path: str) -> bool:
    name = PurePosixPath(logical_path.lower()).name
    return any(marker in name for marker in (".bak", ".backup", ".old", ".orig", ".deleted.", ".reset."))


def _is_config_path(logical_path: str) -> bool:
    lower_path = logical_path.lower()
    basename = PurePosixPath(lower_path).name
    if basename in {"openclaw.json", "jobs.json", "exec-approvals.json"}:
        return True
    if basename in {"agents.md", "heartbeat.md", "identity.md", "soul.md", "tools.md", "user.md"}:
        return True
    return lower_path.startswith("identity/") or lower_path.startswith("devices/")


def _is_sensitive_path(logical_path: str) -> bool:
    lower_path = logical_path.lower()
    if lower_path.startswith("credentials/"):
        return True
    basename = PurePosixPath(lower_path).name
    return basename.endswith(".key") or basename.endswith(".env")


def _is_workspace_user_content(entry: SnapshotEntry, logical_path: str) -> bool:
    if entry.root_type != "workspace":
        return False
    if _is_temp_like(logical_path) or _is_build_artifact_path(logical_path):
        return False
    if _is_log_like(logical_path):
        return False
    if _is_backup_like(entry, logical_path) or _is_model_path(logical_path) or _is_media_like(entry, logical_path):
        return False
    if _contains_segment(logical_path, {"meeting notes", "memory", "templates", "transfer"}):
        return True
    return _is_text_like(entry) and not _contains_segment(logical_path, {"tools"}) and not _is_binary_like(entry, logical_path)


def _is_log_like(logical_path: str) -> bool:
    lower_path = logical_path.lower()
    basename = PurePosixPath(lower_path).name
    if _contains_segment(logical_path, {"logs"}):
        return True
    return basename.endswith(".log") or basename.endswith(".jsonl")


def _should_consider_purge(
    entry: SnapshotEntry,
    logical_path: str,
    age_days: int,
    context: _AnalysisContext,
) -> bool:
    signals = 0
    if _is_temp_like(logical_path):
        signals += 1
    if _is_build_artifact_path(logical_path):
        signals += 1
    if _is_backup_like(entry, logical_path):
        signals += 1
    if age_days >= context.config.stale_days:
        signals += 1
    if entry.size_bytes == 0:
        signals += 1
    if entry.size_bytes >= context.config.large_file_bytes:
        signals += 1
    return signals >= 2


def _semantic_category(entry: SnapshotEntry, logical_path: str) -> str:
    if entry.role in {"memory_daily", "memory_index_or_plugin_data"} or logical_path.lower().startswith("memory/"):
        return "memory"
    if entry.role in {"skill_manifest", "skill_file"} or logical_path.lower().startswith("skills/"):
        return "skill"
    if entry.role in {"session_artifact", "session_store", "session_transcript"} or "/sessions/" in logical_path:
        return "session"
    if entry.role == "openclaw_config" or _is_config_path(logical_path):
        return "config"
    if entry.role == "credentials" or _is_sensitive_path(logical_path):
        return "credentials"
    if entry.role == "media" or _is_media_like(entry, logical_path):
        return "media"
    if entry.role == "browser_data":
        return "browser_state"
    if entry.role == "telegram_data":
        return "telegram_state"
    if entry.role == "cron_run_log" or _is_temp_like(logical_path) or _is_build_artifact_path(logical_path):
        return "cache_or_temp"
    if _is_model_path(logical_path):
        return "model"
    if entry.root_type == "workspace" and _is_text_like(entry):
        return "workspace_content"
    return "unknown"


def _contains_segment(logical_path: str, segment_names: set[str]) -> bool:
    parts = [part.lower() for part in PurePosixPath(logical_path).parts]
    return any(part in segment_names for part in parts)


def _top_largest(entries: tuple[AnalyzedEntry, ...], limit: int) -> list[AnalyzedEntry]:
    files = [entry for entry in entries if entry.kind == "file"]
    return sorted(files, key=lambda entry: (-entry.size_bytes, entry.logical_path, entry.source_name))[:limit]


def _top_stalest(entries: tuple[AnalyzedEntry, ...], limit: int) -> list[AnalyzedEntry]:
    files = [entry for entry in entries if entry.kind == "file"]
    return sorted(files, key=lambda entry: (-entry.age_days, entry.logical_path, entry.source_name))[:limit]


def _top_unknowns(entries: tuple[AnalyzedEntry, ...], limit: int) -> list[AnalyzedEntry]:
    unknowns = [
        entry
        for entry in entries
        if entry.kind == "file" and entry.semantic_category == "unknown" and entry.recommendation is not Recommendation.IGNORE
    ]
    return sorted(
        unknowns,
        key=lambda entry: (-_bucket_rank(entry.recommendation), _confidence_rank(entry.confidence), -entry.size_bytes, entry.logical_path),
    )[:limit]


def _top_bucket_entries(
    entries: tuple[AnalyzedEntry, ...],
    bucket: Recommendation,
    limit: int,
) -> list[AnalyzedEntry]:
    candidates = [entry for entry in entries if entry.kind != "dir" and entry.recommendation is bucket]
    return sorted(
        candidates,
        key=lambda entry: (
            _role_priority(entry),
            _confidence_rank(entry.confidence),
            -entry.size_bytes,
            -entry.age_days,
            entry.logical_path,
        ),
    )[:limit]


def _bucket_rank(recommendation: Recommendation) -> int:
    order = {
        Recommendation.KEEP_SYNCED: 5,
        Recommendation.CANDIDATE_TO_SYNC: 4,
        Recommendation.REVIEW: 3,
        Recommendation.ARCHIVE_CANDIDATE: 2,
        Recommendation.PURGE_CANDIDATE: 1,
        Recommendation.IGNORE: 0,
    }
    return order[recommendation]


def _role_priority(entry: AnalyzedEntry) -> int:
    if entry.role == "memory_daily":
        return 0
    if entry.role.startswith("workspace_bootstrap_"):
        return 1
    if entry.role == "skill_manifest":
        return 2
    if entry.role == "skill_file":
        return 3
    if entry.role == "openclaw_config":
        return 4
    if entry.role == "session_store":
        return 5
    if entry.role == "session_transcript":
        return 6
    if entry.role == "session_artifact":
        return 7
    if entry.role == "cron_run_log":
        return 8
    if entry.role == "media":
        return 9
    return 10


def _confidence_rank(confidence: Confidence) -> int:
    order = {
        Confidence.HIGH: 0,
        Confidence.MEDIUM: 1,
        Confidence.LOW: 2,
    }
    return order[confidence]


def _entry_to_highlight(entry: AnalyzedEntry) -> dict[str, object]:
    return {
        "source": entry.source_name,
        "path": entry.logical_path,
        "absolute_path": entry.absolute_path,
        "root_type": entry.root_type,
        "role": entry.role,
        "semantic_category": entry.semantic_category,
        "recommendation": entry.recommendation.value,
        "confidence": entry.confidence.value,
        "reason_codes": list(entry.reason_codes),
        "size_bytes": entry.size_bytes,
        "modified_time_utc": entry.modified_time_utc.isoformat(),
        "age_days": entry.age_days,
        "kind": entry.kind,
        "symlink_target": entry.symlink_target,
        "text_preview": entry.text_preview,
    }


def _duplicate_group_member_sort_key(entry: AnalyzedEntry) -> tuple[str, str, str, str]:
    return (entry.root_type, entry.logical_path, entry.source_name, entry.absolute_path)


def _exact_duplicate_file_groups(entries: tuple[AnalyzedEntry, ...]) -> list[dict[str, object]]:
    groups_by_hash: dict[str, list[AnalyzedEntry]] = {}
    for entry in entries:
        if (
            entry.kind != "file"
            or not entry.sha256
            or entry.size_bytes <= 0
            or entry.recommendation is Recommendation.IGNORE
        ):
            continue
        groups_by_hash.setdefault(entry.sha256, []).append(entry)

    groups: list[dict[str, object]] = []
    recommendation_order = [bucket.value for bucket in Recommendation if bucket is not Recommendation.IGNORE]
    for digest, members in groups_by_hash.items():
        if len(members) < 2:
            continue
        ordered_members = sorted(members, key=_duplicate_group_member_sort_key)
        representative = ordered_members[0]
        recommendation_counts = _ordered_counter(
            Counter(member.recommendation.value for member in ordered_members),
            recommendation_order,
        )
        root_counts = _ordered_counter(Counter(member.root_type for member in ordered_members), ["workspace", "openclaw"])
        groups.append(
            {
                **_entry_to_highlight(representative),
                "sha256": digest,
                "sha256_prefix": digest[:12],
                "duplicate_count": len(ordered_members),
                "group_total_bytes": representative.size_bytes * len(ordered_members),
                "reclaimable_bytes": representative.size_bytes * (len(ordered_members) - 1),
                "has_mixed_recommendations": len(recommendation_counts) > 1,
                "recommendation_counts": recommendation_counts,
                "root_counts": root_counts,
                "members": [_entry_to_highlight(member) for member in ordered_members],
            }
        )

    groups.sort(
        key=lambda group: (
            -int(group["reclaimable_bytes"]),
            -int(group["duplicate_count"]),
            -int(group["size_bytes"]),
            str(group["path"]),
            str(group["source"]),
        )
    )
    return groups


def _duplicate_group_summary(groups: list[dict[str, object]]) -> dict[str, object]:
    duplicate_file_count = sum(int(group["duplicate_count"]) for group in groups)
    redundant_copy_count = sum(max(int(group["duplicate_count"]) - 1, 0) for group in groups)
    reclaimable_bytes = sum(int(group["reclaimable_bytes"]) for group in groups)
    return {
        "group_count": len(groups),
        "duplicate_file_count": duplicate_file_count,
        "redundant_copy_count": redundant_copy_count,
        "reclaimable_bytes": reclaimable_bytes,
        "basis": "sha256_exact_match_non_ignored_files",
        "workspace_mirrors_excluded": True,
        "guidance": "Exact duplicate groups are based on matching file hashes for non-ignored files. OpenClaw workspace mirror entries are excluded.",
    }


def _ordered_counter(counter: Counter[str], preferred_order: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for key in preferred_order:
        if key in counter:
            result[key] = counter[key]
    for key in sorted(counter):
        if key not in result:
            result[key] = counter[key]
    return result


def _sort_counter_desc(counter: Counter[str]) -> dict[str, int]:
    return {key: count for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))}


def reason_catalog() -> dict[str, str]:
    return dict(sorted(REASON_CATALOG.items()))
# --- End inlined module: analysis.py ---

