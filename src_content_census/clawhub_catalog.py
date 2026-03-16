# --- Begin inlined module: clawhub_catalog.py ---
from pathlib import PurePosixPath



def all_clawhub_skill_knowledge() -> dict[str, dict[str, object]]:
    return {slug: dict(entry) for slug, entry in CLAWHUB_SKILL_CATALOG.items()}


def clawhub_catalog_scope() -> dict[str, object]:
    return dict(CATALOG_SCOPE)


def all_clawhub_skill_slug_index() -> dict[str, tuple[str, str, str, str, str]]:
    return dict(CLAWHUB_SKILL_SLUG_INDEX)


def clawhub_slug_index_scope() -> dict[str, object]:
    return dict(INDEX_SCOPE)


def lookup_clawhub_skill_reference(logical_path: str, role: str, root_type: str) -> dict[str, object] | None:
    """Return third-party ClawHub metadata for files inside recognized published skill folders."""
    normalized = _normalize_reference_path(logical_path)
    parts = PurePosixPath(normalized or ".").parts
    if len(parts) < 2 or parts[0] != "skills":
        return None

    slug = parts[1]
    skill = CLAWHUB_SKILL_CATALOG.get(slug)
    if skill is None:
        return _build_index_reference(slug)

    relative_file = "/".join(parts[2:]) if len(parts) > 2 else ""
    published_files = set(skill.get("files") or [])
    matched_published_file = relative_file if relative_file and relative_file in published_files else None

    field_notes = [
        f"Published on ClawHub as `{skill['display_name']}` by `{skill['owner_handle']}`.",
        (
            f"Latest recorded registry version is `{skill['latest_version']}` with "
            f"{_format_count(skill['stats']['downloads'])} downloads, "
            f"{_format_count(skill['stats']['installs_all_time'])} installs, and "
            f"{_format_count(skill['stats']['stars'])} stars."
        ),
        f"The captured registry bundle lists {skill['file_count']} published files.",
    ]
    if matched_published_file:
        field_notes.append(f"The registry bundle explicitly includes `{matched_published_file}`.")
    elif relative_file:
        field_notes.append(
            f"`{relative_file}` is not present in the captured ClawHub bundle listing, which can mean local customization, installer metadata, or a different installed revision."
        )

    convention_note = _skill_subpath_convention(relative_file)
    if convention_note:
        field_notes.append(convention_note)

    cautions = [
        "ClawHub is a third-party registry source. Treat this as ecosystem metadata, not official OpenClaw documentation.",
    ]
    llm_analysis = skill.get("llm_analysis") or {}
    if llm_analysis.get("summary"):
        cautions.append(
            f"Registry review signal: {llm_analysis.get('status') or 'unknown'} / {llm_analysis.get('verdict') or 'unknown'} — {llm_analysis['summary']}"
        )
    if skill.get("pending_review"):
        cautions.append("This skill was still marked as pending review in the captured registry metadata.")

    return {
        "id": f"clawhub_skill::{slug}",
        "panel_title": "ClawHub Skill Reference",
        "title": str(skill["display_name"]),
        "category": "third_party_skill",
        "summary": str(skill["summary"] or f"Published ClawHub skill `{slug}`."),
        "purpose": (
            f"Explains files that live under `skills/{slug}/...` by anchoring them to the published ClawHub skill bundle for `{skill['display_name']}`."
        ),
        "openclaw_use": (
            "OpenClaw enters a skill through `SKILL.md`; sibling files are support assets from the installed skill bundle or local additions on top of that bundle."
        ),
        "location": f"Skill folder: skills/{slug}/...",
        "note": (
            f"Registry page: {skill['page_url']} | Owner: {skill['owner_handle']} | "
            f"Latest version: {skill['latest_version']}"
        ),
        "field_notes": field_notes,
        "cautions": cautions,
        "sources": [
            {
                "label": "ClawHub Skills",
                "url": str(CATALOG_SCOPE.get("registry_url") or "https://clawhub.ai/skills"),
                "kind": "third_party",
                "note": "Public third-party skill registry.",
            },
            {
                "label": f"ClawHub Skill: {skill['display_name']}",
                "url": str(skill["page_url"]),
                "kind": "third_party",
                "note": "Published skill page derived from public registry metadata.",
            },
        ],
    }


def _build_index_reference(slug: str) -> dict[str, object] | None:
    index_entry = CLAWHUB_SKILL_SLUG_INDEX.get(slug)
    if index_entry is None:
        return None

    display_name, owner_handle, owner_user_id, latest_version, summary = index_entry
    page_url = f"https://clawhub.ai/{owner_user_id}/{slug}" if owner_user_id else str(INDEX_SCOPE["registry_url"])

    return {
        "id": f"clawhub_skill_index::{slug}",
        "panel_title": "ClawHub Skill Reference",
        "title": display_name,
        "category": "third_party_skill_index",
        "summary": summary or f"Published ClawHub skill `{slug}`.",
        "purpose": f"Identifies `skills/{slug}/...` as a published ClawHub skill based on the cached public slug index.",
        "openclaw_use": (
            "This is a lightweight registry-level match only. The analyzer knows the slug exists publicly on ClawHub, but it does not have a cached full bundle manifest for this skill."
        ),
        "location": f"Skill folder: skills/{slug}/...",
        "note": f"Registry page: {page_url} | Owner: {owner_handle} | Latest version: {latest_version}",
        "field_notes": [
            (
                f"Matched via the cached ClawHub public slug index captured on {INDEX_SCOPE['generated_at_utc']} "
                f"covering {int(INDEX_SCOPE['indexed_skill_count']):,} published skill slugs."
            ),
            f"Published as `{display_name}` by `{owner_handle}`.",
        ],
        "cautions": [
            "This is a lightweight registry match, not a cached full bundle manifest. File-by-file claims for this skill are therefore weaker than for fixture slugs with detailed catalog records.",
            "ClawHub is a third-party registry source. Treat it as ecosystem metadata, not official OpenClaw documentation.",
        ],
        "sources": [
            {
                "label": "ClawHub Skills",
                "url": str(INDEX_SCOPE.get("registry_url") or "https://clawhub.ai/skills"),
                "kind": "third_party",
                "note": "Public third-party skill registry.",
            },
            {
                "label": f"ClawHub Skill: {display_name}",
                "url": page_url,
                "kind": "third_party",
                "note": "Published skill page derived from cached slug-index metadata.",
            },
        ],
    }


def _format_count(value: object) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def _skill_subpath_convention(relative_file: str) -> str | None:
    if not relative_file:
        return "The skill root itself usually contains `SKILL.md` plus support code, docs, and package metadata."
    if relative_file == "SKILL.md":
        return "`SKILL.md` is the skill entrypoint that OpenClaw reads when the skill is invoked."
    if relative_file == "_meta.json":
        return "`_meta.json` commonly appears as installer or local package metadata rather than as the agent-facing entrypoint."

    parts = PurePosixPath(relative_file).parts
    if "examples" in parts:
        return "Files under `examples/` are usually usage examples or smoke-test snippets for the skill."
    if "tests" in parts:
        return "Files under `tests/` are usually validation code and are not part of the main agent-facing entrypoint."
    if "hooks" in parts:
        return "Files under `hooks/` usually support automation or platform integrations that the skill can wire into OpenClaw."
    if "scripts" in parts:
        return "Files under `scripts/` usually provide helper executables or setup utilities used by the skill."
    if "assets" in parts or "references" in parts or relative_file.endswith(".md"):
        return "This path looks like bundled documentation, templates, or supporting reference material shipped with the skill."
    if "lib" in parts or relative_file.endswith((".js", ".ts", ".py", ".sh")):
        return "This path looks like implementation code or a helper script that backs the skill's behavior."
    if relative_file.endswith((".json", ".db", ".sqlite", ".lock")):
        return "This path looks like bundled data, metadata, or dependency state that supports the skill locally."
    return None
# --- End inlined module: clawhub_catalog.py ---
