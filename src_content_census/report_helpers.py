# --- Begin inlined module: report_helpers.py ---
def _folder_overview(result: AnalysisResult) -> dict[str, object]:
    root_paths: dict[str, str] = {}
    nodes: dict[tuple[str, str], dict[str, object]] = {}

    def ensure_node(root_type: str, relative_path: str) -> dict[str, object]:
        key = (root_type, relative_path)
        if key in nodes:
            return nodes[key]

        name = _root_label(root_type) if not relative_path else PurePosixPath(relative_path).name
        node = {
            "root_type": root_type,
            "relative_path": relative_path,
            "name": name,
            "depth": 0 if not relative_path else len(PurePosixPath(relative_path).parts),
            "total_size_bytes": 0,
            "file_count": 0,
            "symlink_count": 0,
            "direct_size_bytes": 0,
            "direct_file_count": 0,
            "direct_symlink_count": 0,
            "_child_keys": [],
        }
        nodes[key] = node

        if relative_path:
            parent = PurePosixPath(relative_path).parent.as_posix()
            parent_path = "" if parent == "." else parent
            parent_node = ensure_node(root_type, parent_path)
            if key not in parent_node["_child_keys"]:
                parent_node["_child_keys"].append(key)

        return node

    for entry in result.entries:
        root_paths.setdefault(entry.root_type, entry.root_path)
        if "WORKSPACE_MIRROR" in entry.reason_codes:
            continue

        if entry.kind == "dir":
            ensure_node(entry.root_type, "" if entry.relative_path == "." else entry.relative_path)
            continue

        ensure_node(entry.root_type, "")
        parent = PurePosixPath(entry.relative_path).parent.as_posix()
        parent_path = "" if parent == "." else parent
        direct_node = ensure_node(entry.root_type, parent_path)

        direct_node["direct_size_bytes"] += entry.size_bytes
        if entry.kind == "symlink":
            direct_node["direct_symlink_count"] += 1
        else:
            direct_node["direct_file_count"] += 1

        ancestor_paths = [""]
        if parent_path:
            current_parts: list[str] = []
            for part in PurePosixPath(parent_path).parts:
                current_parts.append(part)
                ancestor_paths.append("/".join(current_parts))

        for ancestor_path in ancestor_paths:
            ancestor = ensure_node(entry.root_type, ancestor_path)
            ancestor["total_size_bytes"] += entry.size_bytes
            if entry.kind == "symlink":
                ancestor["symlink_count"] += 1
            else:
                ancestor["file_count"] += 1

    def serialize(node: dict[str, object]) -> dict[str, object]:
        child_keys = node.pop("_child_keys")
        children = [serialize(nodes[key].copy()) for key in sorted(child_keys, key=lambda key: (-int(nodes[key]["total_size_bytes"]), str(nodes[key]["name"])))]
        return {
            "root_type": node["root_type"],
            "relative_path": node["relative_path"],
            "name": node["name"],
            "depth": node["depth"],
            "total_size_bytes": node["total_size_bytes"],
            "file_count": node["file_count"],
            "symlink_count": node["symlink_count"],
            "direct_size_bytes": node["direct_size_bytes"],
            "direct_file_count": node["direct_file_count"],
            "direct_symlink_count": node["direct_symlink_count"],
            "children": children,
        }

    root_order = [root for root in ("workspace", "openclaw") if root in root_paths] + sorted(root for root in root_paths if root not in {"workspace", "openclaw"})
    roots: list[dict[str, object]] = []
    for root_type in root_order:
        root_node = nodes.get((root_type, ""))
        if root_node is None:
            continue
        serialized_root = serialize(root_node.copy())
        roots.append(
            {
                "root_type": root_type,
                "label": _root_label(root_type),
                "root_path": root_paths.get(root_type, ""),
                "total_size_bytes": serialized_root["total_size_bytes"],
                "file_count": serialized_root["file_count"],
                "symlink_count": serialized_root["symlink_count"],
                "tree": serialized_root,
            }
        )

    total_size_bytes = sum(int(root["total_size_bytes"]) for root in roots)
    non_root_folders = [
        node
        for (root_type, relative_path), node in nodes.items()
        if relative_path and int(node["total_size_bytes"]) > 0
    ]
    largest_folder = None
    if non_root_folders:
        folder = max(non_root_folders, key=lambda item: (int(item["total_size_bytes"]), -int(item["depth"]), str(item["relative_path"])))
        largest_folder = {
            "label": f"{_root_label(str(folder['root_type']))} / {folder['relative_path']}",
            "size_bytes": int(folder["total_size_bytes"]),
            "file_count": int(folder["file_count"]),
        }

    segments: list[dict[str, object]] = []
    for root in roots:
        tree = root["tree"]
        for child in tree["children"]:
            segments.append(
                {
                    "label": f"{root['label']} / {child['relative_path']}",
                    "size_bytes": int(child["total_size_bytes"]),
                }
            )
        if int(tree["direct_size_bytes"]) > 0:
            segments.append(
                {
                    "label": f"{root['label']} /",
                    "size_bytes": int(tree["direct_size_bytes"]),
                }
            )

    chart_segments = _folder_chart_segments(segments, total_size_bytes)
    return {
        "total_size_bytes": total_size_bytes,
        "largest_folder": largest_folder,
        "roots": roots,
        "chart": {
            "segments": chart_segments,
            "gradient": _folder_chart_gradient(chart_segments, total_size_bytes),
        },
    }


def _folder_chart_segments(segments: list[dict[str, object]], total_size_bytes: int, limit: int = 6) -> list[dict[str, object]]:
    palette = ["#4FC3F7", "#66BB6A", "#FFD54F", "#FF6B6B", "#5C6BC0", "#26A69A", "#FFB74D"]
    ordered = sorted((segment for segment in segments if int(segment["size_bytes"]) > 0), key=lambda item: (-int(item["size_bytes"]), str(item["label"])))
    visible = ordered[:limit]
    other_size = sum(int(segment["size_bytes"]) for segment in ordered[limit:])
    if other_size:
        visible.append({"label": "Other folders", "size_bytes": other_size})

    chart_segments: list[dict[str, object]] = []
    for index, segment in enumerate(visible):
        size_bytes = int(segment["size_bytes"])
        percentage = (size_bytes / total_size_bytes * 100) if total_size_bytes else 0
        chart_segments.append(
            {
                "label": str(segment["label"]),
                "size_bytes": size_bytes,
                "percentage": percentage,
                "color": palette[index % len(palette)],
            }
        )
    return chart_segments


def _folder_chart_gradient(segments: list[dict[str, object]], total_size_bytes: int) -> str:
    if not segments or not total_size_bytes:
        return "conic-gradient(#4FC3F7 0% 100%)"

    start = 0.0
    stops: list[str] = []
    for segment in segments:
        percentage = float(segment["percentage"])
        end = start + percentage
        stops.append(f"{segment['color']} {start:.2f}% {end:.2f}%")
        start = end
    return "conic-gradient(" + ", ".join(stops) + ")"


def _folder_summary_rows(folder_overview: dict[str, object]) -> list[tuple[str, str]]:
    roots = folder_overview.get("roots", [])
    root_sizes = {root["label"]: _format_bytes(int(root["total_size_bytes"])) for root in roots}
    rows = [("Tracked bytes", _format_bytes(int(folder_overview.get("total_size_bytes") or 0)))]
    for label, value in root_sizes.items():
        rows.append((label, value))

    largest_folder = folder_overview.get("largest_folder")
    if isinstance(largest_folder, dict):
        rows.append(("Largest folder", f"{largest_folder['label']} · {_format_bytes(int(largest_folder['size_bytes']))}"))
    return rows


def _render_folder_chart(folder_overview: dict[str, object]) -> str:
    chart = folder_overview.get("chart", {})
    segments = chart.get("segments", [])
    gradient = chart.get("gradient") or "conic-gradient(#4FC3F7 0% 100%)"
    legend_markup = "\n".join(
        f"""
        <div class="storage-legend-item">
          <span class="storage-swatch" style="background:{html.escape(str(segment['color']))};"></span>
          <div>
            <div class="storage-legend-label">{html.escape(str(segment['label']))}</div>
            <div class="storage-legend-meta">{segment['percentage']:.1f}% of tracked bytes</div>
          </div>
          <div class="storage-legend-size mono">{html.escape(_format_bytes(int(segment['size_bytes'])))}</div>
        </div>
        """.strip()
        for segment in segments
    )
    return f"""
      <div class="storage-chart-layout">
        <div class="storage-donut-wrap">
          <div class="storage-donut" style="--chart-gradient: {html.escape(str(gradient))};">
            <div class="storage-donut-center">
              <div class="storage-donut-label">Tracked bytes</div>
              <div class="storage-donut-value mono">{html.escape(_format_bytes(int(folder_overview.get('total_size_bytes') or 0)))}</div>
            </div>
          </div>
        </div>
        <div class="storage-legend">
          {legend_markup}
        </div>
      </div>
    """.strip()


def _render_folder_tree_panel(root: dict[str, object]) -> str:
    tree = root.get("tree", {})
    child_markup = "\n".join(_render_folder_tree_node(child) for child in tree.get("children", []))
    root_files_text = f"{int(tree.get('file_count') or 0):,} files"
    if int(tree.get("symlink_count") or 0):
        root_files_text += f", {int(tree['symlink_count']):,} links"
    return f"""
      <section class="tree-panel">
        <h3 class="tree-panel-title">{html.escape(str(root['label']))}</h3>
        <div class="tree-panel-subtitle mono">{html.escape(str(root.get('root_path') or ''))}</div>
        <div class="tree-root-summary">
          <div class="tree-name">{html.escape(str(root['label']))}</div>
          <div class="tree-meta mono">{html.escape(_format_bytes(int(root['total_size_bytes'])))} · {html.escape(root_files_text)}</div>
        </div>
        <div class="tree-children">
          {child_markup}
        </div>
      </section>
    """.strip()


def _render_folder_tree_node(node: dict[str, object]) -> str:
    children = node.get("children", [])
    files_text = f"{int(node.get('file_count') or 0):,} files"
    if int(node.get("symlink_count") or 0):
        files_text += f", {int(node['symlink_count']):,} links"
    child_markup = "\n".join(_render_folder_tree_node(child) for child in children)
    path_markup = (
        f'<div class="tree-path mono">{html.escape(str(node["relative_path"]))}</div>'
        if int(node.get("depth") or 0) > 1
        else ""
    )
    return f"""
      <details class="tree-node">
        <summary class="tree-summary">
          <div>
            <div class="tree-name">{html.escape(str(node['name']))}/</div>
            {path_markup}
          </div>
          <div class="tree-meta mono">{html.escape(_format_bytes(int(node['total_size_bytes'])))} · {html.escape(files_text)}</div>
        </summary>
        <div class="tree-children">
          {child_markup}
        </div>
      </details>
    """.strip()


def render_markdown_report(result: AnalysisResult) -> str:
    duplicate_group_summary = _duplicate_group_summary_from_highlights(result.highlights)
    duplicate_groups = [
        group
        for group in result.highlights.get("duplicate_groups", [])
        if isinstance(group, dict)
    ]
    lines: list[str] = []
    lines.append("# OpenClaw Snapshot Analysis Report")
    lines.append("")
    lines.append(f"- Generated at: `{result.generated_at_utc.isoformat()}`")
    lines.append(f"- Reference time for staleness: `{result.reference_time_utc.isoformat()}`")
    lines.append(f"- Input files analyzed: `{len(result.inputs)}`")
    lines.append(f"- Requested input files: `{result.requested_input_count}`")
    lines.append(f"- Collapsed duplicate snapshots: `{len(result.duplicate_inputs)}`")
    lines.append(f"- Total entries analyzed: `{len(result.entries)}`")
    lines.append("")
    lines.append("## Assumptions")
    lines.append("")
    lines.append("- Age and staleness are computed from the latest snapshot timestamp for deterministic results.")
    lines.append("- OpenClaw `workspace/` mirror entries are treated as duplicates of workspace entries when a matching workspace path exists.")
    lines.append("- Directory entries are summarized, but not treated as primary action targets.")
    lines.append("- Duplicate snapshot captures with matching normalized entries are collapsed to one analyzed input, preferring the richer preview or newer capture.")
    lines.append("")
    lines.append("## Inputs")
    lines.append("")
    lines.append(_render_table(
        ["Snapshot", "Schema", "Generated", "Entries", "Preview Bytes"],
        [
            [
                _sanitize_cell(Path(snapshot.source_path).name),
                snapshot.schema_version,
                snapshot.generated_at_utc.date().isoformat(),
                str(snapshot.summary.entry_count),
                str(snapshot.scan.preview_bytes),
            ]
            for snapshot in result.inputs
        ],
    ))
    if result.duplicate_inputs:
        lines.append("")
        lines.append("### Collapsed Duplicates")
        lines.append("")
        lines.append(_render_table(
            ["Skipped Snapshot", "Kept Snapshot", "Reason", "Skipped Preview Bytes", "Kept Preview Bytes"],
            [
                [
                    _sanitize_cell(Path(duplicate.skipped_source_path).name),
                    _sanitize_cell(Path(duplicate.kept_source_path).name),
                    _sanitize_cell(duplicate.reason),
                    str(duplicate.skipped_preview_bytes),
                    str(duplicate.kept_preview_bytes),
                ]
                for duplicate in result.duplicate_inputs
            ],
        ))
    lines.append("")
    lines.append("## Recommendation Counts")
    lines.append("")
    lines.append(_render_table(
        ["Bucket", "Count"],
        [[bucket, str(count)] for bucket, count in result.bucket_counts.items()],
    ))
    lines.append("")
    lines.append("## Role Counts")
    lines.append("")
    lines.append(_render_table(
        ["Role", "Count"],
        [[role, str(count)] for role, count in list(result.role_counts.items())[:20]],
    ))
    lines.append("")
    lines.append("## Duplicates")
    lines.append("")
    lines.append(f"- Exact duplicate groups: `{int(duplicate_group_summary['group_count'])}`")
    lines.append(f"- Files in duplicate groups: `{int(duplicate_group_summary['duplicate_file_count'])}`")
    lines.append(
        f"- Potentially reclaimable after manual review: `{_format_bytes(int(duplicate_group_summary['reclaimable_bytes']))}`"
    )
    lines.append("- Exact duplicate groups are based on matching file hashes for non-ignored files.")
    lines.append("- OpenClaw `workspace/` mirror entries are excluded from this duplicate view.")
    lines.append("")
    if duplicate_groups:
        lines.append(_render_table(
            ["Representative Path", "Copies", "Each Size", "Potentially Reclaimable", "Recommendations"],
            [
                [
                    _sanitize_cell(str(group["path"])),
                    str(group["duplicate_count"]),
                    _format_bytes(int(group["size_bytes"])),
                    _format_bytes(int(group["reclaimable_bytes"])),
                    _sanitize_cell(
                        ", ".join(
                            f"{bucket}:{count}"
                            for bucket, count in dict(group.get("recommendation_counts", {})).items()
                        )
                    ),
                ]
                for group in duplicate_groups
            ],
        ))
        lines.append("")
        for group in duplicate_groups:
            lines.append(f"### `{_sanitize_cell(str(group['path']))}`")
            lines.append("")
            lines.append(
                f"`{group['duplicate_count']}` exact copies, hash prefix `{group['sha256_prefix']}`, "
                f"`{_format_bytes(int(group['reclaimable_bytes']))}` potentially reclaimable after manual review."
            )
            lines.append("")
            lines.append(_render_highlight_table(list(group.get("members", []))))
            lines.append("")
    else:
        lines.append("No exact duplicate file groups were identified.")
        lines.append("")
    lines.append("## Largest Files")
    lines.append("")
    lines.append(_render_highlight_table(result.highlights["largest_files"]))
    lines.append("")
    lines.append("## Stalest Files")
    lines.append("")
    lines.append(_render_highlight_table(result.highlights["stalest_files"]))
    lines.append("")
    lines.append("## Notable Unknown Files")
    lines.append("")
    unknown_rows = result.highlights["notable_unknown_files"]
    if unknown_rows:
        lines.append(_render_highlight_table(unknown_rows))
    else:
        lines.append("No notable unknown files were identified.")
    lines.append("")
    lines.append("## Symlinks")
    lines.append("")
    symlink_rows = result.highlights["symlinks"]
    if symlink_rows:
        lines.append(_render_table(
            ["Snapshot", "Path", "Role", "Recommendation", "Confidence", "Target"],
            [
                [
                    _sanitize_cell(item["source"]),
                    _sanitize_cell(item["path"]),
                    _sanitize_cell(item["role"]),
                    item["recommendation"],
                    item["confidence"],
                    _sanitize_cell(str(item.get("symlink_target") or "")),
                ]
                for item in symlink_rows
            ],
        ))
    else:
        lines.append("No symlinks were found.")
    lines.append("")
    lines.append("## Top Recommendations")
    lines.append("")
    for bucket_name, items in result.highlights["top_recommendations_by_bucket"].items():
        lines.append(f"### `{bucket_name}`")
        lines.append("")
        if items:
            lines.append(_render_highlight_table(items))
        else:
            lines.append("No entries in this bucket.")
        lines.append("")
    lines.append("## Detailed Recommendations")
    lines.append("")
    detailed_entries = [entry for entry in result.entries if entry.kind != "dir" and entry.recommendation is not Recommendation.IGNORE]
    for bucket in Recommendation:
        if bucket is Recommendation.IGNORE:
            continue
        bucket_entries = [entry for entry in detailed_entries if entry.recommendation is bucket]
        if not bucket_entries:
            continue
        lines.append(f"### `{bucket.value}`")
        lines.append("")
        lines.append(_render_entry_table(bucket_entries, include_snapshot=len(result.inputs) > 1))
        lines.append("")
    ignored_files = [entry for entry in result.entries if entry.kind != "dir" and entry.recommendation is Recommendation.IGNORE]
    if ignored_files:
        lines.append("## Ignored File Samples")
        lines.append("")
        lines.append(
            f"`{len(ignored_files)}` file or symlink entries were ignored. The first 20 are shown below so mirror and duplicate handling remains transparent."
        )
        lines.append("")
        lines.append(_render_entry_table(ignored_files[:20], include_snapshot=len(result.inputs) > 1))
        lines.append("")
    lines.append("## Directory Summary")
    lines.append("")
    directory_count = sum(1 for entry in result.entries if entry.kind == "dir")
    lines.append(f"`{directory_count}` directories were summarized and bucketed as `ignore`.")
    return "\n".join(lines).rstrip() + "\n"


def _entry_to_dict(
    entry: AnalyzedEntry,
    *,
    duplicate_context: dict[str, object],
    folder_context: dict[str, object],
) -> dict[str, object]:
    references = _entry_reference_payload(entry.logical_path, entry.role, entry.root_type, entry.extension, entry.kind)
    return {
        "entry_id": _entry_identifier_for_entry(entry),
        "source_path": entry.source_path,
        "source_name": entry.source_name,
        "snapshot_generated_at_utc": entry.snapshot_generated_at_utc.isoformat(),
        "root_type": entry.root_type,
        "root_path": entry.root_path,
        "absolute_path": entry.absolute_path,
        "relative_path": entry.relative_path,
        "logical_path": entry.logical_path,
        "name": entry.name,
        "role": entry.role,
        "kind": entry.kind,
        "extension": entry.extension,
        "semantic_category": entry.semantic_category,
        "recommendation": entry.recommendation.value,
        "confidence": entry.confidence.value,
        "reason_codes": list(entry.reason_codes),
        "explanation": entry.explanation,
        "is_hidden": entry.is_hidden,
        "size_bytes": entry.size_bytes,
        "modified_time_utc": entry.modified_time_utc.isoformat(),
        "metadata_change_time_utc": entry.metadata_change_time_utc.isoformat(),
        "age_days": entry.age_days,
        "mode_octal": entry.mode_octal,
        "sha256": entry.sha256,
        "git": {
            "repo_root": entry.git.repo_root,
            "repo_relative_path": entry.git.repo_relative_path,
            "tracked": entry.git.tracked,
            "ignored": entry.git.ignored,
            "untracked": entry.git.untracked,
            "modified": entry.git.modified,
            "staged": entry.git.staged,
        },
        "line_count": entry.line_count,
        "symlink_target": entry.symlink_target,
        "text_preview": entry.text_preview,
        "duplicate_context": duplicate_context,
        "folder_context": folder_context,
        **references,
    }


def _html_entry_dict(entry: AnalyzedEntry) -> dict[str, object]:
    references = _entry_reference_payload(entry.logical_path, entry.role, entry.root_type, entry.extension, entry.kind)
    return {
        "source_name": entry.source_name,
        "snapshot_generated_at_utc": entry.snapshot_generated_at_utc.isoformat(),
        "root_type": entry.root_type,
        "absolute_path": entry.absolute_path,
        "relative_path": entry.relative_path,
        "logical_path": entry.logical_path,
        "role": entry.role,
        "kind": entry.kind,
        "semantic_category": entry.semantic_category,
        "recommendation": entry.recommendation.value,
        "confidence": entry.confidence.value,
        "reason_codes": list(entry.reason_codes),
        "is_hidden": entry.is_hidden,
        "size_bytes": entry.size_bytes,
        "modified_time_utc": entry.modified_time_utc.isoformat(),
        "age_days": entry.age_days,
        "has_duplicate_hash": "DUPLICATE_HASH" in entry.reason_codes,
        "git": {
            "tracked": entry.git.tracked,
            "ignored": entry.git.ignored,
            "untracked": entry.git.untracked,
            "modified": entry.git.modified,
            "staged": entry.git.staged,
        },
        "line_count": entry.line_count,
        "symlink_target": entry.symlink_target,
        "text_preview": entry.text_preview,
        **references,
    }


def _render_highlight_table(items: list[dict[str, object]]) -> str:
    if not items:
        return "No rows."
    return _render_table(
        ["Snapshot", "Path", "Role", "Recommendation", "Confidence", "Size", "Age (days)", "Reasons"],
        [
            [
                _sanitize_cell(str(item["source"])),
                _sanitize_cell(str(item["path"])),
                _sanitize_cell(str(item["role"])),
                str(item["recommendation"]),
                str(item["confidence"]),
                _format_bytes(int(item["size_bytes"])),
                str(item["age_days"]),
                _sanitize_cell(", ".join(item["reason_codes"])),
            ]
            for item in items
        ],
    )


def _render_entry_table(entries: list[AnalyzedEntry], include_snapshot: bool) -> str:
    headers = ["Path", "Role", "Recommendation", "Confidence", "Reasons", "Size", "Modified", "Why"]
    rows: list[list[str]] = []
    for entry in entries:
        row = [
            _sanitize_cell(entry.logical_path),
            _sanitize_cell(entry.role),
            entry.recommendation.value,
            entry.confidence.value,
            _sanitize_cell(", ".join(entry.reason_codes)),
            _format_bytes(entry.size_bytes),
            entry.modified_time_utc.date().isoformat(),
            _sanitize_cell(entry.explanation),
        ]
        if include_snapshot:
            row.insert(0, _sanitize_cell(entry.source_name))
        rows.append(row)
    if include_snapshot:
        headers = ["Snapshot", *headers]
    return _render_table(headers, rows)


def _render_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "No rows."
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def _sanitize_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "\\n")


_BRAND_REDACTION_PATTERN = re.compile("context" + "mate", flags=re.IGNORECASE)


def _sanitize_brand_mentions(value: object) -> object:
    if not isinstance(value, str):
        return value
    return _BRAND_REDACTION_PATTERN.sub("another tool", value)


def _sanitize_report_payload(value: object) -> object:
    if isinstance(value, dict):
        return {key: _sanitize_report_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_report_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_report_payload(item) for item in value)
    return _sanitize_brand_mentions(value)


def _build_html_report_context(
    result: AnalysisResult,
    payload: dict[str, object],
    folder_overview: dict[str, object],
) -> _HtmlReportContext:
    return _HtmlReportContext(
        title="Context Census Report",
        generated_at=html.escape(_format_display_datetime(result.generated_at_utc)),
        data_json=json.dumps(payload, separators=(",", ":"), ensure_ascii=True).replace("</", "<\\/"),
        run_summary_markup=_render_run_summary_markup(result),
        bucket_strip_markup=_render_bucket_strip(result.bucket_counts),
        folder_summary_cards_markup="\n".join(
            _render_summary_card_markup(label, value) for label, value in _folder_summary_rows(folder_overview)
        ),
        folder_chart_markup=_render_folder_chart(folder_overview),
        folder_tree_markup="\n".join(_render_folder_tree_panel(root) for root in folder_overview.get("roots", [])),
        catalog_assumptions_markup=_render_catalog_assumptions_markup(),
        reason_catalog_count=len(payload.get("reason_catalog", {})),
    )


def _render_run_summary_markup(result: AnalysisResult) -> str:
    summary_facts_markup = "\n".join(
        _render_summary_fact_markup(label, value)
        for label, value in _run_summary_items(result)
    )
    summary_meta_markup = "\n".join(
        f"""
        <div class="summary-meta-item">
          <span class="summary-meta-label">{html.escape(label)}</span>
          <span class="summary-meta-value mono">{html.escape(value)}</span>
        </div>
        """.strip()
        for label, value in _run_summary_meta_items(result)
    )
    return f"""
      <div class="summary-shell surface-card">
        <div class="summary-shell-header">
          <div class="hero-panel-title">Run summary facts &amp; metadata.</div>
          <span class="pill">deterministic</span>
        </div>
        <div class="summary-fact-bar">
          {summary_facts_markup}
        </div>
        <div class="summary-meta-bar">
          {summary_meta_markup}
        </div>
      </div>
    """.strip()


def _run_summary_items(result: AnalysisResult) -> list[tuple[str, str]]:
    first_input = result.inputs[0] if result.inputs else None
    duplicate_group_summary = _duplicate_group_summary_from_highlights(result.highlights)
    items = [
        ("Files scanned", f"{sum(1 for entry in result.entries if entry.kind == 'file'):,}"),
        ("Skipped", f"{sum(snapshot.summary.skipped_count for snapshot in result.inputs):,}"),
        ("Dup snaps", f"{len(result.duplicate_inputs):,}"),
        ("Dup groups", f"{int(duplicate_group_summary['group_count']):,}"),
        ("Generated", _format_display_datetime(result.generated_at_utc)),
    ]
    is_live_scan = any(snapshot.schema_version.startswith("live-scan") for snapshot in result.inputs)
    if first_input:
        if is_live_scan or first_input.host.user_name:
            items.append(("Whoami", first_input.host.user_name or "unknown"))
        if is_live_scan or first_input.host.openclaw_version:
            items.append(("OpenClaw", first_input.host.openclaw_version or "unknown"))

    inquiry_summary = _highlight_inquiry_summary(result.highlights)
    if inquiry_summary is not None:
        requested = int(inquiry_summary.get("requested") or 0)
        completed = int(inquiry_summary.get("completed") or 0) + int(inquiry_summary.get("cached") or 0)
        failed = int(inquiry_summary.get("failed") or 0)
        if requested:
            items.append(("Inquiry files", f"{completed:,}/{requested:,}"))
        if failed:
            items.append(("Inquiry failed", f"{failed:,}"))
    return items


def _run_summary_meta_items(result: AnalysisResult) -> list[tuple[str, str]]:
    first_input = result.inputs[0] if result.inputs else None
    if first_input is None:
        return []

    items = [
        ("Snapshot", Path(first_input.source_path).name),
        ("Preview bytes", f"{first_input.scan.preview_bytes:,}"),
        ("Workspace", first_input.scan.workspace),
        ("Host", first_input.host.hostname),
    ]
    if len(result.inputs) > 1:
        items.insert(1, ("Inputs analyzed", f"{len(result.inputs):,}"))
    return items


def _render_summary_card_markup(label: str, value: str) -> str:
    return f"""
        <div class="summary-card">
          <div class="summary-card-label">{html.escape(label)}</div>
          <div class="summary-card-value mono">{html.escape(value)}</div>
        </div>
        """.strip()


def _render_summary_fact_markup(label: str, value: str) -> str:
    return f"""
        <div class="summary-fact-item">
          <span class="summary-fact-label">{html.escape(label)}</span>
          <span class="summary-fact-value mono">{html.escape(value)}</span>
        </div>
        """.strip()


def _highlight_inquiry_summary(highlights: dict[str, object]) -> dict[str, object] | None:
    if not isinstance(highlights, dict):
        return None
    summary = highlights.get("inquiry_summary")
    if isinstance(summary, dict):
        return summary
    legacy_summary = highlights.get("sleuth_summary")
    return legacy_summary if isinstance(legacy_summary, dict) else None


def _render_bucket_strip(bucket_counts: dict[str, int]) -> str:
    return "\n".join(
        f"""
        <div class="bucket-chip">
          <span class="bucket-chip-name">{html.escape(_bucket_label(bucket))}</span>
          <span class="bucket-chip-count mono">{count:,}</span>
        </div>
        """.strip()
        for bucket, count in bucket_counts.items()
    )


def _render_catalog_assumptions_markup() -> str:
    assumption_items = "\n".join(
        f"<li>{html.escape(item)}</li>"
        for item in [
            "Age and staleness are computed from the latest snapshot timestamp for deterministic results.",
            "OpenClaw workspace mirror entries are treated as duplicates of workspace entries when a matching workspace path exists.",
            "Directory entries are summarized and shown separately from primary file actions.",
            "Recommendations are advisory only. The report never deletes, syncs, or mutates anything.",
        ]
    )
    return f"""
      <div class="catalog-evidence">
        <div class="catalog-evidence-card">
          <h3>Evidence Model</h3>
          <p class="section-copy">
            Recommendations are based on hard rules first, then soft heuristics, then confidence. Unknowns stay conservative.
          </p>
          <ul>{assumption_items}</ul>
        </div>
        <div class="catalog-evidence-card">
          <h3>External Links</h3>
          <p class="section-copy">
            Use these sources when you want the underlying OpenClaw docs, template pages, skill registry records, or configuration details behind the labels in this report.
          </p>
          {_render_catalog_external_links_markup()}
        </div>
      </div>
    """.strip()


def _render_catalog_external_links_markup() -> str:
    links = [
        (
            "OpenClaw Docs",
            "https://docs.openclaw.ai/",
            "Official",
            "Main documentation hub for runtime concepts, workspace layout, skills, memory, configuration, and reference pages.",
            "Start here if you want the broad product-level explanation before drilling into individual file types.",
        ),
        (
            "Agent Workspace",
            "https://docs.openclaw.ai/concepts/agent-workspace",
            "Official",
            "Best file-map page for standard workspace files like AGENTS.md, SOUL.md, USER.md, MEMORY.md, daily memory files, and what should stay outside the workspace.",
            "This is the most useful page when you want to understand what a known OpenClaw file is for.",
        ),
        (
            "Agent Runtime",
            "https://docs.openclaw.ai/concepts/agent",
            "Official",
            "Explains bootstrap file injection, built-in tools, skill loading locations, and where OpenClaw stores sessions.",
            "Useful for why a file shows up in context at all, not just what it contains.",
        ),
        (
            "Skills Guide",
            "https://docs.openclaw.ai/tools/skills",
            "Official",
            "Explains SKILL.md folders, precedence between bundled, managed, and workspace skills, and how OpenClaw loads them.",
            "Use this when a file lives under skills/ or when a skill manifest drives the recommendation.",
        ),
        (
            "Configuration Reference",
            "https://docs.openclaw.ai/gateway/configuration-reference",
            "Official",
            "Reference for ~/.openclaw/openclaw.json, gateway options, hook settings, sandbox paths, and runtime toggles.",
            "This is the best place to verify config keys or understand control-plane files outside the workspace.",
        ),
        (
            "ClawHub Docs",
            "https://docs.openclaw.ai/tools/clawhub",
            "Official",
            "Explains how OpenClaw installs and syncs skills through ClawHub and how published skills relate to local skill folders.",
            "Use this when a skill slug appears in the report and you want the official packaging context.",
        ),
        (
            "ClawHub Skills",
            "https://clawhub.com/skills",
            "Third Party",
            "Public skill registry where you can look up skill slugs, owners, versions, and package pages for published skills.",
            "This is the fastest external lookup when a file path includes a recognizable skill slug.",
        ),
    ]
    items = "\n".join(
        f"""
        <li class="catalog-link-item">
          <div class="catalog-link-header">
            <a class="catalog-link" href="{html.escape(url)}" target="_blank" rel="noreferrer noopener">{html.escape(label)}</a>
            <span class="reference-source-kind">{html.escape(kind)}</span>
          </div>
          <div class="catalog-link-description">{html.escape(description)}</div>
          <div class="catalog-link-note">{html.escape(note)}</div>
        </li>
        """.strip()
        for label, url, kind, description, note in links
    )
    return f'<ul class="catalog-link-list">{items}</ul>'


def _format_bytes(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    units = ["KiB", "MiB", "GiB", "TiB"]
    size = float(size_bytes)
    for unit in units:
        size /= 1024.0
        if size < 1024.0:
            return f"{size:.1f} {unit}"
    return f"{size:.1f} PiB"


def _format_display_datetime(value) -> str:
    month = value.strftime("%B")
    day = value.day
    year = value.year
    clock = value.strftime("%I:%M %p").lstrip("0")
    zone = value.strftime("%Z") or "UTC"
    return f"{month} {day}, {year} at {clock} {zone}"


def _highlight_payload_with_known_references(highlights: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in highlights.items():
        if key == "top_recommendations_by_bucket" and isinstance(value, dict):
            payload[key] = {
                bucket: [_highlight_item_with_reference(item) for item in items]
                for bucket, items in value.items()
            }
            continue
        if key == "duplicate_groups" and isinstance(value, list):
            payload[key] = [_duplicate_group_item_with_references(item) for item in value]
            continue
        if isinstance(value, list):
            payload[key] = [_highlight_item_with_reference(item) for item in value]
            continue
        payload[key] = value
    return payload


def _duplicate_group_item_with_references(item: dict[str, object]) -> dict[str, object]:
    enriched = _highlight_item_with_reference(item)
    members = item.get("members")
    if isinstance(members, list):
        enriched["members"] = [
            _highlight_item_with_reference(member)
            for member in members
            if isinstance(member, dict)
        ]
    return enriched


def _highlight_item_with_reference(item: dict[str, object]) -> dict[str, object]:
    enriched = dict(item)
    enriched.update(
        _entry_reference_payload(
            str(item.get("path") or ""),
            str(item.get("role") or ""),
            str(item.get("root_type") or ""),
            None,
            str(item.get("kind") or "file"),
        )
    )
    return enriched


def _entry_reference_payload(
    logical_path: str,
    role: str,
    root_type: str,
    extension: str | None = None,
    kind: str = "file",
) -> dict[str, object]:
    payload: dict[str, object] = {}
    known_reference = lookup_known_file_reference(logical_path, role, root_type)
    if known_reference is not None:
        payload["known_reference"] = known_reference
    skill_registry_reference = lookup_clawhub_skill_reference(logical_path, role, root_type)
    if skill_registry_reference is not None:
        payload["skill_registry_reference"] = skill_registry_reference
    if known_reference is None and skill_registry_reference is None:
        file_type_reference = lookup_file_type_reference(logical_path, extension, kind)
        if file_type_reference is not None:
            payload["file_type_reference"] = file_type_reference
    return payload


def _root_label(root_type: str) -> str:
    labels = {
        "workspace": "Workspace",
        "openclaw": "OpenClaw",
    }
    return labels.get(root_type, root_type.replace("_", " ").title())


def _bucket_label(bucket: str) -> str:
    labels = {
        "keep_synced": "Keep Synced",
        "candidate_to_sync": "Candidates to Sync",
        "review": "Review",
        "archive_candidate": "Archive Candidates",
        "purge_candidate": "Purge Candidates",
        "ignore": "Ignore",
    }
    return labels.get(bucket, bucket.replace("_", " ").title())
# --- End inlined module: report_helpers.py ---
