# --- Begin inlined module: models.py ---
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class Recommendation(StrEnum):
    KEEP_SYNCED = "keep_synced"
    CANDIDATE_TO_SYNC = "candidate_to_sync"
    REVIEW = "review"
    ARCHIVE_CANDIDATE = "archive_candidate"
    PURGE_CANDIDATE = "purge_candidate"
    IGNORE = "ignore"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class GitSnapshot:
    repo_root: str | None
    repo_relative_path: str | None
    tracked: bool | None
    ignored: bool | None
    untracked: bool | None
    modified: bool | None
    staged: bool | None


@dataclass(frozen=True)
class SnapshotHost:
    hostname: str
    platform: str
    python_version: str
    user_name: str | None = None
    openclaw_version: str | None = None


@dataclass(frozen=True)
class SnapshotScan:
    workspace: str
    openclaw_root: str
    include_hidden: bool
    hash_max_bytes: int
    preview_bytes: int
    excluded_dir_names: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotSummary:
    entry_count: int
    error_count: int
    root_counts: dict[str, int]
    kind_counts: dict[str, int]
    role_counts: dict[str, int]
    skipped_count: int = 0
    skipped_hidden_count: int = 0
    skipped_excluded_count: int = 0


@dataclass(frozen=True)
class SnapshotEntry:
    source_path: str
    snapshot_generated_at_utc: datetime
    root_type: str
    root_path: str
    absolute_path: str
    relative_path: str
    name: str
    role: str
    is_hidden: bool
    mode_octal: str
    size_bytes: int
    modified_time_utc: datetime
    metadata_change_time_utc: datetime
    kind: str
    extension: str | None
    sha256: str | None
    git: GitSnapshot
    line_count: int | None = None
    symlink_target: str | None = None
    text_preview: str | None = None

    @property
    def source_name(self) -> str:
        return Path(self.source_path).name


@dataclass(frozen=True)
class SnapshotDocument:
    source_path: str
    schema_version: str
    generated_at_utc: datetime
    host: SnapshotHost
    scan: SnapshotScan
    summary: SnapshotSummary
    errors: tuple[object, ...]
    entries: tuple[SnapshotEntry, ...]


@dataclass(frozen=True)
class DuplicateSnapshot:
    skipped_source_path: str
    kept_source_path: str
    reason: str
    skipped_preview_bytes: int
    kept_preview_bytes: int


@dataclass(frozen=True)
class AnalysisConfig:
    archive_days: int = 30
    stale_days: int = 180
    large_file_bytes: int = 25 * 1024 * 1024
    reference_time_utc: datetime | None = None


@dataclass(frozen=True)
class AnalyzedEntry:
    source_path: str
    source_name: str
    snapshot_generated_at_utc: datetime
    root_type: str
    root_path: str
    absolute_path: str
    relative_path: str
    logical_path: str
    name: str
    role: str
    kind: str
    extension: str | None
    semantic_category: str
    recommendation: Recommendation
    confidence: Confidence
    reason_codes: tuple[str, ...]
    explanation: str
    is_hidden: bool
    size_bytes: int
    modified_time_utc: datetime
    metadata_change_time_utc: datetime
    age_days: int
    mode_octal: str
    sha256: str | None
    git: GitSnapshot
    line_count: int | None
    symlink_target: str | None
    text_preview: str | None


@dataclass(frozen=True)
class AnalysisResult:
    report_version: str
    generated_at_utc: datetime
    reference_time_utc: datetime
    config: AnalysisConfig
    requested_input_count: int
    inputs: tuple[SnapshotDocument, ...]
    duplicate_inputs: tuple[DuplicateSnapshot, ...]
    entries: tuple[AnalyzedEntry, ...]
    bucket_counts: dict[str, int]
    role_counts: dict[str, int]
    semantic_category_counts: dict[str, int]
    kind_counts: dict[str, int]
    highlights: dict[str, object]
# --- End inlined module: models.py ---

