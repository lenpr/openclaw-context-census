# --- Begin inlined module: reference_utils.py ---
def _normalize_reference_path(logical_path: str) -> str:
    normalized = logical_path.strip("/")
    if normalized.startswith("workspace/"):
        normalized = normalized[len("workspace/"):]
    return normalized


def _reference_source(label: str, url: str, kind: str, note: str | None = None) -> dict[str, str]:
    payload = {
        "label": label,
        "url": url,
        "kind": kind,
    }
    if note:
        payload["note"] = note
    return payload


def _reference_entry(
    *,
    identifier: str,
    title: str,
    category: str,
    summary: str,
    purpose: str,
    openclaw_use: str,
    location: str,
    note: str,
    field_notes: list[str],
    cautions: list[str],
    panel_title: str | None = None,
    sources: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    payload = {
        "id": identifier,
        "title": title,
        "category": category,
        "summary": summary,
        "purpose": purpose,
        "openclaw_use": openclaw_use,
        "location": location,
        "note": note,
        "field_notes": field_notes,
        "cautions": cautions,
        "sources": list(sources) if sources is not None else [],
    }
    if panel_title is not None:
        payload["panel_title"] = panel_title
    return payload
# --- End inlined module: reference_utils.py ---
