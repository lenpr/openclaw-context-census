# --- Begin inlined module: report_payloads.py ---
def _cleanup_review_order() -> tuple[str, ...]:
    return (
        Recommendation.REVIEW.value,
        Recommendation.ARCHIVE_CANDIDATE.value,
        Recommendation.PURGE_CANDIDATE.value,
        Recommendation.CANDIDATE_TO_SYNC.value,
        Recommendation.KEEP_SYNCED.value,
    )


def _cleanup_priority_rank(recommendation: Recommendation) -> int:
    order = {
        Recommendation.REVIEW: 0,
        Recommendation.ARCHIVE_CANDIDATE: 1,
        Recommendation.PURGE_CANDIDATE: 2,
        Recommendation.CANDIDATE_TO_SYNC: 3,
        Recommendation.KEEP_SYNCED: 4,
        Recommendation.IGNORE: 5,
    }
    return order[recommendation]


def _cleanup_manual_review_reasons(entry: AnalyzedEntry) -> list[str]:
    reasons: list[str] = []
    if entry.kind == "symlink":
        reasons.append("symlink")
    if entry.git.staged:
        reasons.append("git_staged")
    if entry.git.modified:
        reasons.append("git_modified")
    if entry.git.tracked:
        reasons.append("git_tracked")
    if "ROLE_CREDENTIALS" in entry.reason_codes or "SENSITIVE_PATH" in entry.reason_codes:
        reasons.append("sensitive_data")
    if entry.recommendation is Recommendation.PURGE_CANDIDATE:
        reasons.append("purge_requires_confirmation")
    return reasons


def _cleanup_suggested_next_step(recommendation: Recommendation) -> str:
    return {
        Recommendation.KEEP_SYNCED: "leave_in_place",
        Recommendation.CANDIDATE_TO_SYNC: "consider_sync_or_commit",
        Recommendation.REVIEW: "inspect_before_any_change",
        Recommendation.ARCHIVE_CANDIDATE: "review_for_archive",
        Recommendation.PURGE_CANDIDATE: "review_for_possible_purge",
        Recommendation.IGNORE: "ignore",
    }[recommendation]


def _stable_identifier(prefix: str, *parts: object) -> str:
    material = "\0".join("" if part is None else str(part) for part in parts)
    return f"{prefix}_{sha256(material.encode('utf-8')).hexdigest()[:16]}"


def _entry_identifier(source_name: str, absolute_path: str, root_type: str, kind: str) -> str:
    return _stable_identifier("entry", source_name, absolute_path, root_type, kind)


def _entry_identifier_for_entry(entry: AnalyzedEntry) -> str:
    return _entry_identifier(entry.source_name, entry.absolute_path, entry.root_type, entry.kind)


def _entry_identifier_from_item(item: dict[str, object]) -> str:
    return _entry_identifier(
        str(item.get("source") or item.get("source_name") or ""),
        str(item.get("absolute_path") or ""),
        str(item.get("root_type") or ""),
        str(item.get("kind") or "file"),
    )


def _duplicate_group_identifier(digest: str) -> str:
    return _stable_identifier("dupgrp", digest)


def _default_duplicate_context() -> dict[str, object]:
    return {
        "is_duplicate": False,
        "group_id": None,
        "group_size": 0,
        "group_total_bytes": 0,
        "reclaimable_bytes_if_deduplicated": 0,
        "sha256_prefix": None,
        "other_member_entry_ids": [],
        "other_member_paths": [],
    }


def _full_duplicate_inventory_payload(result: AnalysisResult) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    groups = _exact_duplicate_file_groups(result.entries)
    summary = _duplicate_group_summary(groups)
    groups_payload: list[dict[str, object]] = []
    context_by_entry_id: dict[str, dict[str, object]] = {}

    for rank, group in enumerate(groups, start=1):
        group_id = _duplicate_group_identifier(str(group["sha256"]))
        members_payload: list[dict[str, object]] = []
        member_entry_ids: list[str] = []
        member_paths: list[str] = []
        for member in group.get("members", []):
            if not isinstance(member, dict):
                continue
            entry_id = _entry_identifier_from_item(member)
            member_entry_ids.append(entry_id)
            member_paths.append(str(member.get("path") or ""))
            members_payload.append(
                {
                    "entry_id": entry_id,
                    **member,
                }
            )

        groups_payload.append(
            {
                "group_id": group_id,
                "review_rank": rank,
                "member_entry_ids": member_entry_ids,
                **group,
                "members": members_payload,
            }
        )

        for index, entry_id in enumerate(member_entry_ids):
            context_by_entry_id[entry_id] = {
                "is_duplicate": True,
                "group_id": group_id,
                "group_size": int(group["duplicate_count"]),
                "group_total_bytes": int(group["group_total_bytes"]),
                "reclaimable_bytes_if_deduplicated": int(group["reclaimable_bytes"]),
                "sha256_prefix": group["sha256_prefix"],
                "other_member_entry_ids": [
                    other_entry_id
                    for other_index, other_entry_id in enumerate(member_entry_ids)
                    if other_index != index
                ],
                "other_member_paths": [
                    other_path
                    for other_index, other_path in enumerate(member_paths)
                    if other_index != index
                ],
            }

    return (
        {
            **summary,
            "groups": groups_payload,
        },
        context_by_entry_id,
    )


def _folder_context_by_entry_id(result: AnalysisResult) -> dict[str, dict[str, object]]:
    folder_stats: dict[tuple[str, str], dict[str, object]] = {}
    recommendation_order = [bucket.value for bucket in Recommendation if bucket is not Recommendation.IGNORE]

    for entry in result.entries:
        if entry.kind == "dir":
            continue
        parent = PurePosixPath(entry.logical_path).parent.as_posix()
        folder_path = "." if parent == "." else parent
        key = (entry.root_type, folder_path)
        stats = folder_stats.setdefault(
            key,
            {
                "root_type": entry.root_type,
                "folder_path": folder_path,
                "entry_count": 0,
                "file_count": 0,
                "symlink_count": 0,
                "duplicate_file_count": 0,
                "total_bytes": 0,
                "recommendation_counter": Counter(),
            },
        )
        stats["entry_count"] = int(stats["entry_count"]) + 1
        if entry.kind == "symlink":
            stats["symlink_count"] = int(stats["symlink_count"]) + 1
        else:
            stats["file_count"] = int(stats["file_count"]) + 1
        if "DUPLICATE_HASH" in entry.reason_codes:
            stats["duplicate_file_count"] = int(stats["duplicate_file_count"]) + 1
        stats["total_bytes"] = int(stats["total_bytes"]) + int(entry.size_bytes)
        recommendation_counter = stats["recommendation_counter"]
        if isinstance(recommendation_counter, Counter):
            recommendation_counter[entry.recommendation.value] += 1

    payload_by_entry_id: dict[str, dict[str, object]] = {}
    for entry in result.entries:
        if entry.kind == "dir":
            continue
        parent = PurePosixPath(entry.logical_path).parent.as_posix()
        folder_path = "." if parent == "." else parent
        stats = folder_stats[(entry.root_type, folder_path)]
        recommendation_counter = stats["recommendation_counter"]
        folder_context = {
            "root_type": entry.root_type,
            "folder_path": folder_path,
            "entry_count": int(stats["entry_count"]),
            "other_entry_count": max(int(stats["entry_count"]) - 1, 0),
            "file_count": int(stats["file_count"]),
            "symlink_count": int(stats["symlink_count"]),
            "duplicate_file_count": int(stats["duplicate_file_count"]),
            "total_bytes": int(stats["total_bytes"]),
            "recommendation_counts": _ordered_counter(recommendation_counter, recommendation_order)
            if isinstance(recommendation_counter, Counter)
            else {},
        }
        payload_by_entry_id[_entry_identifier_for_entry(entry)] = folder_context

    return payload_by_entry_id


def _cleanup_preservation_signals(entry: AnalyzedEntry, duplicate_context: dict[str, object]) -> list[str]:
    signals: list[str] = []
    for code in entry.reason_codes:
        if code.startswith("ROLE_") or code in {"SENSITIVE_PATH", "GIT_TRACKED", "GIT_MODIFIED"}:
            signals.append(code)
    if entry.git.staged:
        signals.append("git_staged")
    if duplicate_context.get("is_duplicate"):
        signals.append("duplicate_group_present")
    if entry.recommendation in {Recommendation.KEEP_SYNCED, Recommendation.CANDIDATE_TO_SYNC}:
        signals.append("recommendation_preserves_file")
    return signals


def _cleanup_verify_before_change(
    entry: AnalyzedEntry,
    duplicate_context: dict[str, object],
    folder_context: dict[str, object],
) -> list[str]:
    steps: list[str] = []
    if duplicate_context.get("is_duplicate"):
        steps.append("Compare the duplicate group and confirm one retained copy is sufficient before archiving extras.")
    if entry.git.tracked or entry.git.modified or entry.git.staged:
        steps.append("Check Git history and uncommitted changes before moving, archiving, or deleting this path.")
    if "ROLE_CREDENTIALS" in entry.reason_codes or "SENSITIVE_PATH" in entry.reason_codes:
        steps.append("Confirm secret retention, backup, and rotation requirements before any filesystem change.")
    if entry.kind == "symlink":
        steps.append("Inspect the symlink target and the workflow that expects it.")
    if any(code.startswith("ROLE_") for code in entry.reason_codes):
        steps.append("Verify whether this path is part of a documented OpenClaw convention or active workflow.")
    if not steps:
        steps.append("Inspect the file contents and neighboring files before deciding.")
    if int(folder_context.get("other_entry_count") or 0) > 0:
        steps.append("Review nearby files in the same folder for related artifacts that should be handled together.")
    return steps


def _cleanup_safe_alternatives(entry: AnalyzedEntry, duplicate_context: dict[str, object]) -> list[str]:
    alternatives: list[str] = []
    if duplicate_context.get("is_duplicate"):
        alternatives.append("retain_one_copy_and_archive_the_rest_after_manual_review")
    if entry.git.tracked or entry.git.modified or entry.git.staged:
        alternatives.append("commit_or_tag_before_cleanup")
    if "ROLE_CREDENTIALS" in entry.reason_codes or "SENSITIVE_PATH" in entry.reason_codes:
        alternatives.append("leave_in_place_until_secret_handling_is_confirmed")
    if entry.recommendation is Recommendation.ARCHIVE_CANDIDATE:
        alternatives.append("archive_instead_of_delete")
    if entry.recommendation is Recommendation.PURGE_CANDIDATE:
        alternatives.append("backup_or_quarantine_before_any_deletion")
    if not alternatives:
        alternatives.append("leave_in_place")
    return alternatives


def _cleanup_related_paths(
    entry: AnalyzedEntry,
    duplicate_context: dict[str, object],
    folder_context: dict[str, object],
) -> list[dict[str, str]]:
    related: list[dict[str, str]] = []
    folder_path = str(folder_context.get("folder_path") or ".")
    related.append({"relationship": "folder", "path": folder_path})
    if entry.git.repo_relative_path:
        related.append({"relationship": "git_repo_path", "path": entry.git.repo_relative_path})
    for path in list(duplicate_context.get("other_member_paths") or [])[:10]:
        related.append({"relationship": "duplicate_copy", "path": str(path)})
    return related


def _cleanup_review_packet(
    entry: AnalyzedEntry,
    duplicate_context: dict[str, object],
    folder_context: dict[str, object],
) -> dict[str, object]:
    return {
        "why_candidate": entry.explanation,
        "risk_flags": _cleanup_manual_review_reasons(entry),
        "preservation_signals": _cleanup_preservation_signals(entry, duplicate_context),
        "verify_before_change": _cleanup_verify_before_change(entry, duplicate_context, folder_context),
        "safe_alternatives": _cleanup_safe_alternatives(entry, duplicate_context),
        "related_paths": _cleanup_related_paths(entry, duplicate_context, folder_context),
    }


def _cleanup_candidate_dict(
    entry: AnalyzedEntry,
    *,
    review_rank: int,
    duplicate_context: dict[str, object],
    folder_context: dict[str, object],
) -> dict[str, object]:
    references = _entry_reference_payload(entry.logical_path, entry.role, entry.root_type, entry.extension, entry.kind)
    return {
        "entry_id": _entry_identifier_for_entry(entry),
        "review_rank": review_rank,
        "absolute_path": entry.absolute_path,
        "relative_path": entry.relative_path,
        "logical_path": entry.logical_path,
        "root_type": entry.root_type,
        "kind": entry.kind,
        "role": entry.role,
        "semantic_category": entry.semantic_category,
        "recommendation": entry.recommendation.value,
        "confidence": entry.confidence.value,
        "suggested_next_step": _cleanup_suggested_next_step(entry.recommendation),
        "requires_human_review": True,
        "manual_review_reasons": _cleanup_manual_review_reasons(entry),
        "reason_codes": list(entry.reason_codes),
        "explanation": entry.explanation,
        "size_bytes": entry.size_bytes,
        "age_days": entry.age_days,
        "modified_time_utc": entry.modified_time_utc.isoformat(),
        "git": {
            "repo_root": entry.git.repo_root,
            "repo_relative_path": entry.git.repo_relative_path,
            "tracked": entry.git.tracked,
            "ignored": entry.git.ignored,
            "untracked": entry.git.untracked,
            "modified": entry.git.modified,
            "staged": entry.git.staged,
        },
        "duplicate_context": duplicate_context,
        "folder_context": folder_context,
        "review_packet": _cleanup_review_packet(entry, duplicate_context, folder_context),
        **references,
    }


def _cleanup_review_batches(candidates: list[dict[str, object]], *, batch_size: int = 20) -> list[dict[str, object]]:
    batches: list[dict[str, object]] = []
    recommendation_order = list(_cleanup_review_order())
    for batch_number, start in enumerate(range(0, len(candidates), batch_size), start=1):
        chunk = candidates[start:start + batch_size]
        if not chunk:
            continue
        recommendation_counts = _ordered_counter(
            Counter(str(candidate["recommendation"]) for candidate in chunk),
            recommendation_order,
        )
        batches.append(
            {
                "batch_id": f"batch_{batch_number:02d}",
                "batch_number": batch_number,
                "candidate_count": len(chunk),
                "start_review_rank": int(chunk[0]["review_rank"]),
                "end_review_rank": int(chunk[-1]["review_rank"]),
                "recommendation_counts": recommendation_counts,
                "candidate_entry_ids": [str(candidate["entry_id"]) for candidate in chunk],
                "candidate_paths": [str(candidate["logical_path"]) for candidate in chunk],
            }
        )
    return batches


def _cleanup_plan_payload(
    result: AnalysisResult,
    *,
    duplicate_context_by_entry_id: dict[str, dict[str, object]],
    folder_context_by_entry_id: dict[str, dict[str, object]],
) -> dict[str, object]:
    actionable_entries = [entry for entry in result.entries if entry.kind != "dir" and entry.recommendation is not Recommendation.IGNORE]
    ordered_entries = sorted(
        actionable_entries,
        key=lambda entry: (
            _cleanup_priority_rank(entry.recommendation),
            _confidence_rank(entry.confidence),
            -entry.size_bytes,
            -entry.age_days,
            entry.logical_path,
        ),
    )
    bucket_counts = _ordered_counter(
        Counter(entry.recommendation.value for entry in ordered_entries),
        list(_cleanup_review_order()),
    )
    candidates = [
        _cleanup_candidate_dict(
            entry,
            review_rank=index + 1,
            duplicate_context=duplicate_context_by_entry_id.get(_entry_identifier_for_entry(entry), _default_duplicate_context()),
            folder_context=folder_context_by_entry_id.get(_entry_identifier_for_entry(entry), {}),
        )
        for index, entry in enumerate(ordered_entries)
    ]
    return {
        "mode": "recommendations_only",
        "destructive_actions_included": False,
        "requires_human_review": True,
        "recommended_review_order": list(_cleanup_review_order()),
        "candidate_count": len(candidates),
        "bucket_counts": bucket_counts,
        "guidance": [
            "Use this section as a triage queue, not as permission to delete files automatically.",
            "Review archive and purge candidates manually before changing the filesystem.",
            "Treat Git-tracked, Git-modified, staged, symlink, and sensitive files as explicit review items.",
        ],
        "review_batches": _cleanup_review_batches(candidates),
        "candidates": candidates,
    }


def _duplicate_group_summary_from_highlights(highlights: dict[str, object]) -> dict[str, object]:
    summary = highlights.get("duplicate_groups_summary")
    if isinstance(summary, dict):
        return summary
    return _duplicate_group_summary([])


def _agent_support_payload(cleanup_plan: dict[str, object]) -> dict[str, object]:
    return {
        "format_version": 1,
        "entry_id_scheme": "entry_<sha256(source_name\\0absolute_path\\0root_type\\0kind)[:16]>",
        "duplicate_group_id_scheme": "dupgrp_<sha256(content_sha256)[:16]>",
        "conversation_guide": [
            "Treat every recommendation as advisory only and ask for human confirmation before destructive changes.",
            "Review duplicate groups and Git-tracked paths before archive or purge decisions.",
            "Use cleanup_plan.review_batches to discuss the queue in small chunks instead of traversing the full report at once.",
            "Prefer archive or quarantine-style actions over deletion when the file has workflow, secret, or repository signals.",
        ],
        "suggested_agent_sequence": [
            "Inspect duplicates.groups for high-payoff duplicate clusters.",
            "Walk cleanup_plan.review_batches in order.",
            "Use entries plus duplicate and folder context when discussing a specific path.",
        ],
    }


def _report_thresholds_payload(result: AnalysisResult) -> dict[str, object]:
    return {
        "archive_days": result.config.archive_days,
        "stale_days": result.config.stale_days,
        "large_file_bytes": result.config.large_file_bytes,
    }


def _snapshot_host_payload(snapshot: SnapshotDocument) -> dict[str, object]:
    return {
        "hostname": snapshot.host.hostname,
        "platform": snapshot.host.platform,
        "python_version": snapshot.host.python_version,
        "user_name": snapshot.host.user_name,
        "openclaw_version": snapshot.host.openclaw_version,
    }


def _snapshot_scan_payload(snapshot: SnapshotDocument, *, include_hash_settings: bool) -> dict[str, object]:
    payload = {
        "workspace": snapshot.scan.workspace,
        "openclaw_root": snapshot.scan.openclaw_root,
        "include_hidden": snapshot.scan.include_hidden,
    }
    if include_hash_settings:
        payload["hash_max_bytes"] = snapshot.scan.hash_max_bytes
    payload["preview_bytes"] = snapshot.scan.preview_bytes
    if include_hash_settings:
        payload["excluded_dir_names"] = list(snapshot.scan.excluded_dir_names)
    return payload


def _snapshot_summary_payload(snapshot: SnapshotDocument, *, include_role_breakdown: bool) -> dict[str, object]:
    payload = {
        "entry_count": snapshot.summary.entry_count,
        "error_count": snapshot.summary.error_count,
    }
    if include_role_breakdown:
        payload["root_counts"] = dict(snapshot.summary.root_counts)
        payload["kind_counts"] = dict(snapshot.summary.kind_counts)
        payload["role_counts"] = dict(snapshot.summary.role_counts)
    payload["skipped_count"] = snapshot.summary.skipped_count
    payload["skipped_hidden_count"] = snapshot.summary.skipped_hidden_count
    payload["skipped_excluded_count"] = snapshot.summary.skipped_excluded_count
    return payload


def _inputs_payload(
    result: AnalysisResult,
    *,
    include_hash_settings: bool,
    include_role_breakdown: bool,
) -> list[dict[str, object]]:
    return [
        {
            "path": snapshot.source_path,
            "name": Path(snapshot.source_path).name,
            "schema_version": snapshot.schema_version,
            "generated_at_utc": snapshot.generated_at_utc.isoformat(),
            "host": _snapshot_host_payload(snapshot),
            "scan": _snapshot_scan_payload(snapshot, include_hash_settings=include_hash_settings),
            "summary": _snapshot_summary_payload(snapshot, include_role_breakdown=include_role_breakdown),
        }
        for snapshot in result.inputs
    ]


def _summary_payload(result: AnalysisResult, duplicate_group_summary: dict[str, object]) -> dict[str, object]:
    return {
        "requested_input_count": result.requested_input_count,
        "input_count": len(result.inputs),
        "duplicate_input_count": len(result.duplicate_inputs),
        "duplicate_file_group_count": int(duplicate_group_summary["group_count"]),
        "duplicate_file_count": int(duplicate_group_summary["duplicate_file_count"]),
        "duplicate_reclaimable_bytes": int(duplicate_group_summary["reclaimable_bytes"]),
        "entry_count": len(result.entries),
        "bucket_counts": dict(result.bucket_counts),
        "role_counts": dict(result.role_counts),
        "semantic_category_counts": dict(result.semantic_category_counts),
        "kind_counts": dict(result.kind_counts),
        "file_count": sum(1 for entry in result.entries if entry.kind == "file"),
        "directory_count": sum(1 for entry in result.entries if entry.kind == "dir"),
        "symlink_count": sum(1 for entry in result.entries if entry.kind == "symlink"),
        "skipped_count": sum(snapshot.summary.skipped_count for snapshot in result.inputs),
    }


def _duplicate_inputs_payload(result: AnalysisResult) -> list[dict[str, object]]:
    return [
        {
            "skipped_source_path": duplicate.skipped_source_path,
            "kept_source_path": duplicate.kept_source_path,
            "reason": duplicate.reason,
            "skipped_preview_bytes": duplicate.skipped_preview_bytes,
            "kept_preview_bytes": duplicate.kept_preview_bytes,
        }
        for duplicate in result.duplicate_inputs
    ]


def _shared_report_payload(
    result: AnalysisResult,
    *,
    folder_overview: dict[str, object],
    duplicate_group_summary: dict[str, object],
    include_hash_settings: bool,
    include_role_breakdown: bool,
) -> dict[str, object]:
    return {
        "report_version": result.report_version,
        "generated_at_utc": result.generated_at_utc.isoformat(),
        "reference_time_utc": result.reference_time_utc.isoformat(),
        "thresholds": _report_thresholds_payload(result),
        "inputs": _inputs_payload(
            result,
            include_hash_settings=include_hash_settings,
            include_role_breakdown=include_role_breakdown,
        ),
        "summary": _summary_payload(result, duplicate_group_summary),
        "duplicate_inputs": _duplicate_inputs_payload(result),
        "folder_overview": folder_overview,
        "highlights": _highlight_payload_with_known_references(result.highlights),
        "reason_catalog": reason_catalog(),
    }


def _json_report_payload(result: AnalysisResult, folder_overview: dict[str, object] | None = None) -> dict[str, object]:
    effective_folder_overview = folder_overview or _folder_overview(result)
    duplicate_group_summary = _duplicate_group_summary_from_highlights(result.highlights)
    duplicate_inventory, duplicate_context_by_entry_id = _full_duplicate_inventory_payload(result)
    folder_context_by_entry_id = _folder_context_by_entry_id(result)
    cleanup_plan = _cleanup_plan_payload(
        result,
        duplicate_context_by_entry_id=duplicate_context_by_entry_id,
        folder_context_by_entry_id=folder_context_by_entry_id,
    )
    payload = _shared_report_payload(
        result,
        folder_overview=effective_folder_overview,
        duplicate_group_summary=duplicate_group_summary,
        include_hash_settings=True,
        include_role_breakdown=True,
    )
    payload["duplicates"] = duplicate_inventory
    payload["cleanup_plan"] = cleanup_plan
    payload["agent_support"] = _agent_support_payload(cleanup_plan)
    payload["entries"] = [
        _entry_to_dict(
            entry,
            duplicate_context=duplicate_context_by_entry_id.get(_entry_identifier_for_entry(entry), _default_duplicate_context()),
            folder_context=folder_context_by_entry_id.get(_entry_identifier_for_entry(entry), {}),
        )
        for entry in result.entries
    ]
    return payload


def _html_report_payload(result: AnalysisResult, folder_overview: dict[str, object] | None = None) -> dict[str, object]:
    effective_folder_overview = folder_overview or _folder_overview(result)
    duplicate_group_summary = _duplicate_group_summary_from_highlights(result.highlights)
    payload = _shared_report_payload(
        result,
        folder_overview=effective_folder_overview,
        duplicate_group_summary=duplicate_group_summary,
        include_hash_settings=False,
        include_role_breakdown=False,
    )
    payload["entries"] = [_html_entry_dict(entry) for entry in result.entries]
    return _sanitize_report_payload(payload)
# --- End inlined module: report_payloads.py ---
