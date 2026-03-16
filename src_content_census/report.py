# --- Begin inlined module: report.py ---
import html
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath



@dataclass(frozen=True)
class _HtmlReportContext:
    title: str
    generated_at: str
    data_json: str
    run_summary_markup: str
    bucket_strip_markup: str
    folder_summary_cards_markup: str
    folder_chart_markup: str
    folder_tree_markup: str
    catalog_assumptions_markup: str
    reason_catalog_count: int


def render_json_report(result: AnalysisResult) -> str:
    """Render the analysis result into a stable machine-readable JSON document."""
    payload = _json_report_payload(result)
    return json.dumps(payload, indent=2, ensure_ascii=True)


def render_html_report(result: AnalysisResult) -> str:
    """Render the analysis result into a standalone interactive HTML report."""
    folder_overview = _folder_overview(result)
    payload = _html_report_payload(result, folder_overview=folder_overview)
    context = _build_html_report_context(result, payload, folder_overview)

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{context.title}</title>
    <style>
      :root {{
        --bg: #1A1A2E;
        --surface: #16213E;
        --deep-surface: #0F1729;
        --border: #2A2A4A;
        --accent: #4FC3F7;
        --accent-hover: #39A8DB;
        --text: #E0E0E0;
        --muted: #888888;
        --dim: #666666;
        --success: #66BB6A;
        --error: #FF6B6B;
        --warning: #FFD54F;
        --container: 1320px;
        --radius: 18px;
        --radius-sm: 12px;
        --shadow: 0 16px 48px rgba(0, 0, 0, 0.22);
      }}

      * {{
        box-sizing: border-box;
      }}

      html {{
        scroll-behavior: smooth;
      }}

      body {{
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: "Satoshi", "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
        line-height: 1.6;
      }}

      a {{
        color: var(--accent);
        text-decoration: none;
      }}

      a:hover {{
        color: var(--accent-hover);
      }}

      code,
      pre,
      kbd,
      .mono {{
        font-family: "JetBrains Mono", "SFMono-Regular", "Menlo", "Monaco", monospace;
      }}

      .app-shell {{
        min-height: 100vh;
      }}

      .top-nav {{
        position: sticky;
        top: 0;
        z-index: 40;
        backdrop-filter: blur(8px);
        background: rgba(15, 23, 41, 0.92);
        border-bottom: 1px solid var(--border);
      }}

      .top-nav-inner,
      .container {{
        width: min(100% - 32px, var(--container));
        margin: 0 auto;
      }}

      .top-nav-inner {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 24px;
        padding: 14px 0;
      }}

      .brand {{
        display: flex;
        align-items: center;
        gap: 12px;
        font-weight: 600;
        letter-spacing: 0.02em;
      }}

      .brand-mark {{
        width: 12px;
        height: 12px;
        border-radius: 999px;
        background: var(--accent);
        box-shadow: 0 0 0 6px rgba(79, 195, 247, 0.1);
      }}

      .nav-links {{
        display: flex;
        flex-wrap: wrap;
        gap: 12px 18px;
      }}

      .nav-links a {{
        color: var(--muted);
        font-size: 0.95rem;
      }}

      .nav-links a:hover {{
        color: var(--text);
      }}

      .section {{
        padding: 48px 0;
      }}

      .hero {{
        padding: 64px 0 40px;
      }}

      .eyebrow {{
        display: inline-flex;
        align-items: center;
        gap: 10px;
        color: var(--accent);
        font-size: 0.9rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 18px;
      }}

      .hero-grid {{
        display: grid;
        grid-template-columns: minmax(0, 1.4fr) minmax(300px, 0.8fr);
        gap: 28px;
        align-items: start;
      }}

      h1,
      h2,
      h3,
      h4 {{
        margin: 0;
        line-height: 1.15;
        font-weight: 600;
        letter-spacing: -0.02em;
      }}

      h1 {{
        font-size: clamp(2.4rem, 4vw, 4.2rem);
        max-width: 18ch;
      }}

      h2 {{
        font-size: clamp(1.5rem, 2vw, 2rem);
        margin-bottom: 12px;
      }}

      p {{
        margin: 0;
      }}

      .hero-copy {{
        color: var(--muted);
        max-width: 76ch;
        margin-top: 18px;
        font-size: 1.02rem;
      }}

      .hero-actions,
      .cta-actions {{
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-top: 24px;
      }}

      .summary-shell {{
        margin-top: 28px;
        padding: 20px 24px;
      }}

      .summary-shell-header {{
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 12px;
      }}

      .summary-fact-bar,
      .summary-meta-bar {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px 18px;
        min-width: 0;
      }}

      .summary-fact-bar {{
        padding: 12px 0;
        border-top: 1px solid var(--border);
        border-bottom: 1px solid var(--border);
      }}

      .summary-card {{
        background: var(--deep-surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 12px 14px;
      }}

      .summary-fact-item,
      .summary-meta-item {{
        display: inline-flex;
        align-items: baseline;
        gap: 8px;
        min-width: 0;
      }}

      .summary-fact-label,
      .summary-card-label,
      .summary-meta-label {{
        color: var(--dim);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        white-space: nowrap;
      }}

      .summary-fact-value {{
        color: var(--text);
        font-size: 0.95rem;
        font-weight: 600;
        overflow-wrap: anywhere;
      }}

      .summary-card-value {{
        margin-top: 6px;
        color: var(--text);
        font-size: 0.94rem;
        word-break: break-word;
      }}

      .summary-meta-bar {{
        margin-top: 14px;
      }}

      .summary-meta-label {{
        font-size: 0.76rem;
      }}

      .summary-meta-value {{
        color: var(--text);
        font-size: 0.86rem;
        overflow-wrap: anywhere;
      }}

      .structure-grid {{
        display: grid;
        grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.3fr);
        gap: 18px;
        align-items: start;
      }}

      .structure-overview {{
        padding: 20px;
      }}

      .storage-chart-layout {{
        display: grid;
        gap: 16px;
        margin-top: 18px;
      }}

      .storage-donut-wrap {{
        display: flex;
        justify-content: center;
        padding: 8px 0 4px;
      }}

      .storage-donut {{
        --chart-gradient: conic-gradient(var(--accent) 0% 100%);
        position: relative;
        width: min(100%, 256px);
        aspect-ratio: 1;
        border-radius: 999px;
        background: var(--chart-gradient);
      }}

      .storage-donut::after {{
        content: "";
        position: absolute;
        inset: 22px;
        border-radius: 999px;
        background: var(--surface);
        border: 1px solid var(--border);
      }}

      .storage-donut-center {{
        position: absolute;
        inset: 0;
        z-index: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        padding: 22px;
      }}

      .storage-donut-label {{
        color: var(--dim);
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .storage-donut-value {{
        margin-top: 8px;
        color: var(--text);
        font-size: 1rem;
      }}

      .storage-legend {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
        gap: 8px;
      }}

      .storage-legend-item {{
        display: grid;
        grid-template-columns: 8px minmax(0, 1fr) auto;
        gap: 8px;
        align-items: start;
        padding: 6px 8px;
        border: 1px solid var(--border);
        border-radius: 10px;
        background: var(--deep-surface);
      }}

      .storage-swatch {{
        width: 8px;
        height: 8px;
        border-radius: 999px;
        margin-top: 5px;
      }}

      .storage-legend-label {{
        color: var(--text);
        font-size: 0.82rem;
      }}

      .storage-legend-meta {{
        color: var(--muted);
        font-size: 0.72rem;
        margin-top: 4px;
      }}

      .storage-legend-size {{
        color: var(--text);
        font-size: 0.8rem;
        text-align: right;
        white-space: nowrap;
      }}

      .structure-tree-grid {{
        display: grid;
        gap: 14px;
      }}

      .tree-panel {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 18px;
        box-shadow: var(--shadow);
      }}

      .tree-panel-title {{
        margin-bottom: 4px;
      }}

      .tree-panel-subtitle {{
        color: var(--muted);
        font-size: 0.9rem;
        margin-bottom: 14px;
      }}

      .tree-root-summary,
      .tree-summary {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: baseline;
        color: var(--text);
      }}

      .tree-summary {{
        padding: 8px 10px;
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.02);
      }}

      .tree-node {{
        margin-top: 8px;
      }}

      .tree-children {{
        margin-left: 18px;
        padding-left: 12px;
        border-left: 1px solid var(--border);
      }}

      .tree-name {{
        color: var(--text);
        font-size: 0.92rem;
      }}

      .tree-path {{
        color: var(--dim);
        font-size: 0.78rem;
        margin-top: 2px;
      }}

      .tree-meta {{
        color: var(--muted);
        font-size: 0.82rem;
        text-align: right;
        white-space: nowrap;
      }}

      .button,
      .filter-chip,
      .copy-button,
      .toggle {{
        appearance: none;
        border: 1px solid var(--border);
        background: var(--surface);
        color: var(--text);
        border-radius: 999px;
        cursor: pointer;
        transition: background-color 140ms ease, border-color 140ms ease, color 140ms ease, transform 140ms ease;
      }}

      .button {{
        padding: 10px 16px;
        font-size: 0.96rem;
        display: inline-flex;
        align-items: center;
        gap: 10px;
      }}

      .button-primary {{
        border-color: rgba(79, 195, 247, 0.35);
        background: rgba(79, 195, 247, 0.12);
        color: var(--accent);
      }}

      .button-primary:hover,
      .copy-button:hover,
      .filter-chip.active {{
        background: rgba(79, 195, 247, 0.18);
        border-color: var(--accent);
        color: var(--accent);
      }}

      .button-secondary:hover,
      .toggle:hover {{
        border-color: var(--accent-hover);
        color: var(--text);
      }}

      .surface-card,
      .command-card,
      .result-card,
      .input-card,
      .highlight-card,
      .stat-card {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        box-shadow: var(--shadow);
      }}

      .hero-panel {{
        padding: 24px;
      }}

      .hero-panel-header {{
        display: flex;
        justify-content: space-between;
        gap: 16px;
        align-items: center;
        margin-bottom: 16px;
      }}

      .hero-panel-title {{
        font-size: 0.95rem;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .hero-panel-value {{
        font-size: 1.8rem;
        font-weight: 600;
      }}

      .hero-panel-subvalue {{
        margin-top: 6px;
        color: var(--muted);
        font-size: 0.9rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }}

      .stat-grid,
      .bucket-grid,
      .command-grid,
      .input-grid {{
        display: grid;
        gap: 16px;
      }}

      .stat-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}

      .bucket-grid {{
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        margin-top: 20px;
      }}

      .bucket-strip {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-bottom: 18px;
      }}

      .bucket-chip {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border: 1px solid var(--border);
        border-radius: 999px;
        background: var(--deep-surface);
      }}

      .bucket-chip-name {{
        color: var(--muted);
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .bucket-chip-count {{
        color: var(--text);
        font-size: 0.9rem;
      }}

      .run-fact-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
        margin-top: 18px;
      }}

      .run-fact {{
        padding: 12px 14px;
        background: var(--deep-surface);
        border: 1px solid var(--border);
        border-radius: 12px;
      }}

      .run-fact-label {{
        color: var(--dim);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .run-fact-value {{
        margin-top: 6px;
        color: var(--text);
        font-size: 0.92rem;
        word-break: break-word;
      }}

      .command-grid {{
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      }}

      .input-grid {{
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      }}

      .stat-card {{
        padding: 18px 20px;
      }}

      .stat-label {{
        color: var(--muted);
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .stat-value {{
        margin-top: 10px;
        font-size: 1.6rem;
        font-weight: 600;
      }}

      .bucket-card {{
        padding: 16px 18px;
        border-radius: var(--radius-sm);
        text-align: left;
      }}

      .bucket-name {{
        display: block;
        font-size: 0.86rem;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .bucket-count {{
        display: block;
        margin-top: 10px;
        font-size: 1.6rem;
        font-weight: 600;
      }}

      .section-copy {{
        color: var(--muted);
        max-width: 74ch;
        margin-bottom: 22px;
      }}

      .structure-copy {{
        max-width: 62ch;
      }}

      .explorer-copy {{
        max-width: 62ch;
      }}

      .command-card,
      .input-card,
      .highlight-card {{
        padding: 18px;
      }}

      .command-meta {{
        color: var(--accent);
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 10px;
      }}

      .command-card pre {{
        margin: 0;
        padding: 16px;
        overflow-x: auto;
        background: var(--deep-surface);
        border-radius: var(--radius-sm);
        border: 1px solid var(--border);
        color: var(--text);
      }}

      .copy-button {{
        margin-top: 14px;
        padding: 9px 12px;
        font-size: 0.88rem;
      }}

      .copy-button.copied {{
        border-color: rgba(102, 187, 106, 0.45);
        background: rgba(102, 187, 106, 0.14);
        color: var(--success);
      }}

      .evidence-grid {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
        gap: 18px;
      }}

      .evidence-card {{
        background: var(--deep-surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 22px;
      }}

      .evidence-card ul {{
        margin: 0;
        padding-left: 18px;
        color: var(--muted);
      }}

      .evidence-card li + li {{
        margin-top: 10px;
      }}

      .input-header {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: center;
        margin-bottom: 16px;
      }}

      .pill,
      .tag,
      .reason-tag {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border-radius: 999px;
        border: 1px solid var(--border);
        padding: 5px 10px;
        font-size: 0.84rem;
      }}

      .pill {{
        color: var(--accent);
        background: rgba(79, 195, 247, 0.08);
      }}

      .kv-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 14px;
        margin: 0;
      }}

      .kv-grid dt {{
        color: var(--dim);
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .kv-grid dd {{
        margin: 6px 0 0;
        color: var(--text);
      }}

      .explorer-shell {{
        display: grid;
        grid-template-columns: 1fr;
        gap: 14px;
        align-items: start;
      }}

      .panel {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 20px;
        box-shadow: var(--shadow);
      }}

      .panel-title {{
        margin-bottom: 10px;
      }}

      .panel-header {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: flex-start;
        flex-wrap: wrap;
      }}

      .panel-copy {{
        color: var(--muted);
        margin-bottom: 12px;
      }}

      .filter-toolbar {{
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        align-items: end;
      }}

      .filter-group {{
        flex: 1 1 148px;
        min-width: 148px;
      }}

      .filter-group.filter-search {{
        flex: 2.2 1 280px;
        min-width: 240px;
      }}

      .button-compact {{
        padding: 8px 12px;
        font-size: 0.84rem;
      }}

      .filter-label {{
        display: block;
        margin-bottom: 6px;
        color: var(--muted);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .filter-input,
      .filter-select {{
        width: 100%;
        border-radius: 10px;
        border: 1px solid var(--border);
        background: var(--deep-surface);
        color: var(--text);
        padding: 10px 12px;
        font: inherit;
      }}

      .filter-select {{
        appearance: none;
      }}

      .filter-chip-row,
      .toggle-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }}

      .filter-chip {{
        padding: 8px 12px;
        border-radius: 999px;
        font-size: 0.9rem;
      }}

      .toggle {{
        padding: 8px 12px;
        border-radius: 12px;
        display: inline-flex;
        gap: 10px;
        align-items: center;
      }}

      .toggle input {{
        accent-color: var(--accent);
      }}

      .results-meta {{
        display: flex;
        justify-content: space-between;
        gap: 18px;
        flex-wrap: wrap;
        margin-bottom: 16px;
      }}

      .results-count {{
        font-size: 1rem;
      }}

      .results-subtext {{
        color: var(--muted);
        font-size: 0.92rem;
      }}

      .results-list {{
        display: grid;
        gap: 4px;
      }}

      .results-head,
      .finder-grid {{
        display: grid;
        grid-template-columns: minmax(0, 3.2fr) minmax(170px, 1fr) minmax(150px, 0.9fr) minmax(96px, 0.45fr) minmax(132px, 0.6fr) 64px;
        gap: 12px;
        align-items: center;
      }}

      .results-head {{
        padding: 0 12px 8px;
        margin-bottom: 6px;
        border-bottom: 1px solid var(--border);
      }}

      .results-head button,
      .results-head-static {{
        color: var(--dim);
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .results-head button {{
        appearance: none;
        border: 0;
        background: transparent;
        padding: 0;
        width: 100%;
        text-align: left;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 6px;
      }}

      .results-head button:hover,
      .results-head button:focus-visible {{
        color: var(--text);
        outline: none;
      }}

      .sort-indicator {{
        color: var(--accent);
        font-size: 0.72rem;
        opacity: 0;
        transition: opacity 120ms ease;
      }}

      .results-head button.active .sort-indicator {{
        opacity: 1;
      }}

      .result-card {{
        margin: 0;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 12px;
        box-shadow: none;
        transition: border-color 140ms ease, background-color 140ms ease;
      }}

      .result-card[open] {{
        border-color: var(--border);
        background: var(--surface);
      }}

      .result-card:hover {{
        border-color: rgba(79, 195, 247, 0.26);
        transform: none;
      }}

      .result-summary {{
        padding: 10px 12px;
        border-radius: 12px;
        background: var(--deep-surface);
        color: var(--text);
      }}

      .result-card[open] .result-summary {{
        border-bottom-left-radius: 0;
        border-bottom-right-radius: 0;
        border-bottom: 1px solid var(--border);
      }}

      .finder-name-cell {{
        min-width: 0;
      }}

      .finder-name-stack {{
        min-width: 0;
      }}

      .finder-path {{
        display: block;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}

      .finder-directory {{
        color: var(--muted);
        font-size: 0.86rem;
      }}

      .finder-filename {{
        color: var(--text);
        font-size: 0.94rem;
      }}

      .finder-signal {{
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        align-items: center;
      }}

      .finder-role,
      .finder-size,
      .finder-modified {{
        color: var(--muted);
        font-size: 0.88rem;
        white-space: nowrap;
      }}

      .finder-role {{
        overflow: hidden;
        text-overflow: ellipsis;
      }}

      .finder-action {{
        justify-self: end;
      }}

      .finder-info {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 52px;
        padding: 5px 8px;
        border-radius: 999px;
        border: 1px solid var(--border);
        background: rgba(79, 195, 247, 0.08);
        color: var(--accent);
        font-size: 0.78rem;
      }}

      .result-card[open] .finder-info-closed {{
        display: none;
      }}

      .result-card:not([open]) .finder-info-open {{
        display: none;
      }}

      .tag {{
        background: rgba(255, 255, 255, 0.02);
        padding: 4px 8px;
        font-size: 0.78rem;
      }}

      .tag.recommendation-keep_synced {{
        color: var(--success);
        border-color: rgba(102, 187, 106, 0.34);
      }}

      .tag.recommendation-candidate_to_sync {{
        color: var(--accent);
        border-color: rgba(79, 195, 247, 0.34);
      }}

      .tag.recommendation-review {{
        color: var(--warning);
        border-color: rgba(255, 213, 79, 0.34);
      }}

      .tag.recommendation-archive_candidate {{
        color: #F6C177;
        border-color: rgba(246, 193, 119, 0.34);
      }}

      .tag.recommendation-purge_candidate {{
        color: var(--error);
        border-color: rgba(255, 107, 107, 0.34);
      }}

      .tag.confidence-high {{
        color: var(--success);
      }}

      .tag.confidence-medium {{
        color: var(--warning);
      }}

      .tag.confidence-low {{
        color: var(--error);
      }}

      .metadata-key {{
        color: var(--dim);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .metadata-value {{
        margin-top: 6px;
        font-size: 0.95rem;
      }}

      .reason-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 12px;
      }}

      .reason-tag {{
        background: rgba(79, 195, 247, 0.08);
        color: var(--accent);
        border-color: rgba(79, 195, 247, 0.22);
        padding: 4px 8px;
        font-size: 0.78rem;
      }}

      details {{
        margin-top: 10px;
      }}

      details summary {{
        list-style: none;
        cursor: pointer;
        color: var(--accent);
        user-select: none;
        font-size: 0.9rem;
      }}

      details summary::-webkit-details-marker {{
        display: none;
      }}

      .detail-grid {{
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: 12px;
        margin-top: 10px;
      }}

      .finder-detail {{
        padding: 12px;
      }}

      .known-reference-card {{
        background: rgba(79, 195, 247, 0.06);
      }}

      .known-reference-summary {{
        margin-top: 8px;
        color: var(--text);
        font-size: 0.92rem;
      }}

      .reference-list {{
        margin: 10px 0 0;
        padding-left: 18px;
        color: var(--muted);
      }}

      .reference-list li + li {{
        margin-top: 6px;
      }}

      .reference-list strong {{
        color: var(--text);
      }}

      .reference-note {{
        margin-top: 10px;
        color: var(--muted);
        font-size: 0.84rem;
      }}

      .reference-sources {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 10px;
      }}

      .reference-link {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 10px;
        border: 1px solid var(--border);
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.02);
        color: var(--accent);
        font-size: 0.8rem;
      }}

      .reference-source-kind {{
        color: var(--dim);
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .catalog-link-list {{
        list-style: none;
        margin: 12px 0 0;
        padding: 0;
        display: grid;
        gap: 12px;
      }}

      .catalog-link-item {{
        padding: 12px 14px;
        border: 1px solid var(--border);
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.02);
      }}

      .catalog-link-header {{
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
      }}

      .catalog-link {{
        color: var(--accent);
        font-weight: 600;
      }}

      .catalog-link-description {{
        margin-top: 6px;
        color: var(--muted);
        font-size: 0.92rem;
      }}

      .catalog-link-note {{
        margin-top: 6px;
        color: var(--dim);
        font-size: 0.8rem;
      }}

      .detail-card {{
        background: var(--deep-surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 12px;
      }}

      .detail-card .mono {{
        word-break: break-word;
      }}

      .preview-disclosure {{
        margin-top: 12px;
        background: var(--deep-surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 10px 12px;
      }}

      .preview-block {{
        margin: 10px 0 0;
        padding: 12px;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid var(--border);
        border-radius: 10px;
        color: var(--text);
        white-space: pre-wrap;
        word-break: break-word;
      }}

      .preview-block-compact {{
        font-size: 0.8rem;
        line-height: 1.5;
      }}

      .preview-empty {{
        color: var(--muted);
        font-size: 0.8rem;
        line-height: 1.5;
      }}

      .pagination-bar {{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        margin-top: 12px;
        width: 100%;
      }}

      .pagination-controls {{
        display: flex;
        align-items: center;
        gap: 8px;
        justify-content: center;
      }}

      .pagination-current {{
        color: var(--muted);
        font-size: 0.88rem;
        min-width: 88px;
        text-align: center;
      }}

      button:disabled {{
        cursor: not-allowed;
        opacity: 0.45;
        transform: none;
      }}

      .highlights-nav {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-bottom: 18px;
      }}

      .highlight-shell {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 20px;
        box-shadow: var(--shadow);
      }}

      .highlight-tab {{
        appearance: none;
        border: 1px solid var(--border);
        background: var(--deep-surface);
        color: var(--muted);
        border-radius: 999px;
        padding: 10px 14px;
        cursor: pointer;
        font: inherit;
        transition: background-color 140ms ease, border-color 140ms ease, color 140ms ease;
      }}

      .highlight-tab:hover {{
        border-color: var(--accent-hover);
        color: var(--text);
      }}

      .highlight-tab.active {{
        background: rgba(79, 195, 247, 0.16);
        border-color: var(--accent);
        color: var(--accent);
      }}

      .highlight-panel {{
        min-height: 0;
      }}

      .highlight-browser {{
        display: grid;
        gap: 8px;
      }}

      .highlight-browser-grid {{
        display: grid;
        grid-template-columns: minmax(0, 1.9fr) minmax(88px, 0.42fr) minmax(164px, 0.82fr) minmax(88px, 0.34fr) minmax(64px, 0.24fr) 64px;
        gap: 12px;
        align-items: center;
      }}

      .duplicate-browser-grid {{
        display: grid;
        grid-template-columns: minmax(0, 1.8fr) minmax(72px, 0.28fr) minmax(92px, 0.32fr) minmax(112px, 0.42fr) minmax(180px, 0.95fr) 64px;
        gap: 12px;
        align-items: center;
      }}

      .highlight-browser-head {{
        padding: 0 10px 8px;
        border-bottom: 1px solid var(--border);
        color: var(--dim);
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .highlight-browser-row {{
        margin: 0;
        border-radius: 12px;
        border: 1px solid var(--border);
        background: var(--deep-surface);
        transition: border-color 140ms ease, background-color 140ms ease;
      }}

      .highlight-browser-row:hover,
      .highlight-browser-row[open] {{
        border-color: rgba(79, 195, 247, 0.3);
      }}

      .highlight-summary {{
        padding: 10px;
        cursor: pointer;
        list-style: none;
      }}

      .highlight-summary::-webkit-details-marker {{
        display: none;
      }}

      .highlight-browser-row[open] .highlight-summary {{
        border-bottom: 1px solid var(--border);
      }}

      .highlight-path-cell {{
        min-width: 0;
      }}

      .highlight-path-stack {{
        min-width: 0;
      }}

      .highlight-path {{
        display: flex;
        flex-wrap: wrap;
        gap: 0;
        word-break: break-word;
      }}

      .highlight-directory {{
        color: var(--muted);
      }}

      .highlight-name {{
        color: var(--text);
      }}

      .highlight-submeta {{
        margin-top: 2px;
        color: var(--dim);
        font-size: 0.82rem;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }}

      .highlight-cell {{
        color: var(--muted);
        font-size: 0.88rem;
      }}

      .highlight-cell.path-col {{
        min-width: 0;
      }}

      .highlight-root {{
        color: var(--accent);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 0.74rem;
      }}

      .highlight-signal {{
        display: inline-flex;
        flex-wrap: wrap;
        gap: 6px;
        align-items: center;
      }}

      .highlight-action {{
        justify-self: end;
      }}

      .highlight-info {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 52px;
        padding: 5px 8px;
        border-radius: 999px;
        border: 1px solid var(--border);
        background: rgba(79, 195, 247, 0.08);
        color: var(--accent);
        font-size: 0.78rem;
      }}

      .highlight-browser-row[open] .highlight-info-closed {{
        display: none;
      }}

      .highlight-browser-row:not([open]) .highlight-info-open {{
        display: none;
      }}

      .highlight-row-details {{
        display: grid;
        gap: 12px;
        padding: 12px;
      }}

      .duplicate-group-summary {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }}

      .duplicate-group-note {{
        color: var(--muted);
        font-size: 0.86rem;
      }}

      .duplicate-members {{
        display: grid;
        gap: 8px;
      }}

      .duplicate-members-grid {{
        display: grid;
        grid-template-columns: minmax(0, 1.9fr) minmax(88px, 0.42fr) minmax(164px, 0.9fr) minmax(88px, 0.34fr) minmax(64px, 0.24fr);
        gap: 12px;
        align-items: center;
      }}

      .duplicate-members-head {{
        padding: 0 0 8px;
        border-bottom: 1px solid var(--border);
        color: var(--dim);
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .duplicate-member-row {{
        padding: 8px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      }}

      .duplicate-member-row:last-child {{
        border-bottom: 0;
        padding-bottom: 0;
      }}

      .duplicate-member-path {{
        min-width: 0;
      }}

      .duplicate-member-reasons {{
        margin-top: 4px;
        color: var(--dim);
        font-size: 0.78rem;
        line-height: 1.4;
      }}

      .highlight-detail-card {{
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 12px;
      }}

      .highlight-detail-title {{
        color: var(--dim);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .detail-title-row {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
      }}

      .tooltip-shell {{
        position: relative;
        display: inline-flex;
        align-items: center;
      }}

      .inquiry-info-badge {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
        border-radius: 999px;
        border: 1px solid rgba(79, 195, 247, 0.28);
        background: rgba(79, 195, 247, 0.08);
        color: var(--accent);
        font-size: 0.7rem;
        font-weight: 700;
        cursor: help;
        padding: 0;
        appearance: none;
        -webkit-appearance: none;
      }}

      .inquiry-info-badge:focus-visible {{
        outline: 2px solid rgba(79, 195, 247, 0.5);
        outline-offset: 2px;
      }}

      .inquiry-tooltip {{
        position: absolute;
        left: 50%;
        bottom: calc(100% + 10px);
        transform: translateX(-50%) translateY(4px);
        width: min(260px, 70vw);
        padding: 9px 10px;
        border-radius: 10px;
        border: 1px solid rgba(79, 195, 247, 0.22);
        background: #0d1630;
        box-shadow: 0 12px 28px rgba(0, 0, 0, 0.28);
        color: var(--text);
        font-size: 0.76rem;
        line-height: 1.45;
        text-transform: none;
        letter-spacing: normal;
        opacity: 0;
        pointer-events: none;
        transition: opacity 140ms ease, transform 140ms ease;
        z-index: 12;
      }}

      .inquiry-tooltip::after {{
        content: "";
        position: absolute;
        left: 50%;
        top: 100%;
        width: 10px;
        height: 10px;
        background: #0d1630;
        border-right: 1px solid rgba(79, 195, 247, 0.22);
        border-bottom: 1px solid rgba(79, 195, 247, 0.22);
        transform: translateX(-50%) rotate(45deg);
      }}

      .tooltip-shell:hover .inquiry-tooltip,
      .tooltip-shell:focus-within .inquiry-tooltip {{
        opacity: 1;
        transform: translateX(-50%) translateY(0);
      }}

      .highlight-detail-value {{
        margin-top: 6px;
        color: var(--text);
        font-size: 0.94rem;
        word-break: break-word;
      }}

      .inquiry-card {{
        background: rgba(79, 195, 247, 0.06);
      }}

      .inquiry-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 8px;
      }}

      .inquiry-list {{
        margin: 10px 0 0;
        padding-left: 18px;
        color: var(--muted);
      }}

      .inquiry-list li + li {{
        margin-top: 6px;
      }}

      .inquiry-list strong {{
        color: var(--text);
      }}

      .inquiry-example {{
        margin-top: 10px;
        padding-top: 10px;
        border-top: 1px solid rgba(255, 255, 255, 0.06);
      }}

      .inquiry-example-label {{
        color: var(--dim);
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .highlight-preview-details {{
        margin-top: 0;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 10px 12px;
      }}

      .highlight-preview-block {{
        margin: 10px 0 0;
        padding: 12px;
        background: var(--deep-surface);
        border: 1px solid var(--border);
        border-radius: 10px;
        color: var(--text);
        white-space: pre-wrap;
        word-break: break-word;
      }}

      .highlight-empty {{
        padding: 14px;
        border-radius: 12px;
        border: 1px solid var(--border);
        background: var(--deep-surface);
        color: var(--muted);
      }}

      .reason-list {{
        margin: 0;
        padding-left: 22px;
      }}

      .reason-item + .reason-item {{
        margin-top: 14px;
      }}

      .reason-item::marker {{
        color: var(--accent);
      }}

      .reason-disclosure {{
        margin-top: 0;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 12px 14px;
      }}

      .reason-disclosure[open] {{
        border-color: rgba(79, 195, 247, 0.28);
      }}

      .reason-summary {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: baseline;
        margin: 0;
      }}

      .reason-code {{
        color: var(--text);
        font-size: 0.98rem;
      }}

      .reason-family {{
        color: var(--accent);
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .reason-count {{
        color: var(--muted);
        font-size: 0.82rem;
      }}

      .reason-body {{
        margin-top: 12px;
      }}

      .reason-description {{
        color: var(--text);
      }}

      .reason-context {{
        margin-top: 6px;
        color: var(--muted);
      }}

      .reason-detail-list {{
        margin: 12px 0 0;
        padding-left: 18px;
        color: var(--muted);
      }}

      .reason-detail-list li + li {{
        margin-top: 8px;
      }}

      .reason-detail-label {{
        color: var(--text);
        font-weight: 600;
      }}

      .reason-example {{
        margin-top: 6px;
        display: inline-flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
      }}

      .catalog-shell {{
        margin-top: 0;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 18px 20px;
        box-shadow: var(--shadow);
      }}

      .catalog-shell-summary {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        color: var(--text);
        cursor: pointer;
      }}

      .catalog-toggle-chevron {{
        color: var(--accent);
        font-size: 0.92rem;
        line-height: 1;
      }}

      .catalog-title {{
        display: block;
        font-size: clamp(1.5rem, 2vw, 2rem);
        font-weight: 600;
        line-height: 1.15;
      }}

      .catalog-copy {{
        display: block;
        margin-top: 8px;
        color: var(--muted);
        font-size: 0.96rem;
        max-width: 68ch;
      }}

      .catalog-body {{
        margin-top: 18px;
      }}

      .catalog-evidence {{
        margin-bottom: 18px;
      }}

      .catalog-evidence-card {{
        background: var(--deep-surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 18px;
      }}

      .catalog-toggle-hint {{
        color: var(--muted);
        font-size: 0.8rem;
        margin-left: auto;
      }}

      .cta-band {{
        margin-top: 20px;
        padding: 24px;
        background: var(--deep-surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
      }}

      .footer-note {{
        color: var(--dim);
        font-size: 0.92rem;
        margin-top: 18px;
      }}

      .hidden {{
        display: none !important;
      }}

      @media (max-width: 1120px) {{
        .hero-grid,
        .structure-grid,
        .explorer-shell,
        .evidence-grid {{
          grid-template-columns: 1fr;
        }}
      }}

      @media (max-width: 760px) {{
        .top-nav-inner {{
          align-items: flex-start;
          flex-direction: column;
        }}

        .stat-grid,
        .run-fact-grid,
        .kv-grid,
        .detail-grid {{
          grid-template-columns: 1fr;
        }}

        .file-row {{
          grid-template-columns: 1fr;
        }}

        .highlight-browser-head {{
          display: none;
        }}

        .results-head {{
          display: none;
        }}

        .highlight-browser-grid,
        .duplicate-browser-grid,
        .duplicate-members-grid,
        .highlight-summary {{
          grid-template-columns: 1fr;
          gap: 6px;
        }}

        .storage-chart-layout {{
          grid-template-columns: 1fr;
        }}

        .duplicate-members-head {{
          display: none;
        }}

        .finder-grid,
        .result-summary {{
          grid-template-columns: 1fr;
          gap: 6px;
        }}

        .finder-action {{
          justify-self: start;
        }}

        .filter-group,
        .filter-group.filter-search {{
          min-width: 100%;
          flex-basis: 100%;
        }}

        .summary-fact-bar,
        .summary-meta-bar {{
          flex-direction: column;
          align-items: stretch;
          gap: 8px;
        }}

        .summary-fact-item,
        .summary-meta-item {{
          width: 100%;
          justify-content: space-between;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="app-shell">
      <header class="top-nav">
        <div class="top-nav-inner">
          <div class="brand">
            <span class="brand-mark"></span>
            <span>OpenClaw File Analysis</span>
          </div>
          <nav class="nav-links" aria-label="Sections">
            <a href="#overview">Run Summary</a>
            <a href="#highlights">Check First</a>
            <a href="#folders">Folders &amp; Size</a>
            <a href="#explorer">File Explorer</a>
            <a href="#reasons">Evidence Guide &amp; External Links</a>
          </nav>
        </div>
      </header>

      <main>
        <section class="hero section" id="overview">
          <div class="container">
            <div class="eyebrow">
              <span>Offline Analysis</span>
              <span class="mono">{context.generated_at}</span>
            </div>
              <div>
                <h1>Context Census Report</h1>
                <p class="hero-copy">
                  OpenClaw writes a large number of workspace, runtime, memory, skill, and support files, and it can be hard to understand which ones matter most. This standalone HTML report keeps the analysis local and read-only while helping you understand which files are likely important, which deserve review, and which appear lower-priority.
                </p>
              </div>
            {context.run_summary_markup}
          </div>
        </section>

        <section class="section" id="highlights">
          <div class="container">
            <h2>Check First</h2>
            <p class="section-copy">
              Large files, stale files, unknowns, and top recommendations are grouped here so you can review the most important files before moving into the explorer.
            </p>
            <div class="highlight-shell">
              <div class="highlights-nav" id="highlight-tabs"></div>
              <div class="highlight-panel" id="highlight-panel"></div>
            </div>
          </div>
        </section>

        <section class="section" id="folders">
          <div class="container">
            <h2>Folders &amp; Size</h2>
            <p class="section-copy structure-copy">
              Rolled-up folder sizes show where storage is concentrated without double-counting mirrored workspace entries.
            </p>
            <div class="structure-grid">
              <div class="structure-overview surface-card">
                <div class="summary-row">
                  {context.folder_summary_cards_markup}
                </div>
                {context.folder_chart_markup}
              </div>
              <div class="structure-tree-grid">
                {context.folder_tree_markup}
              </div>
            </div>
          </div>
        </section>

        <section class="section" id="explorer">
          <div class="container">
            <h2>File Explorer</h2>
            <p class="section-copy explorer-copy">
              Search the file list by path, role, category, confidence, and duplicate status. Ignored entries and directories stay hidden here.
            </p>
            <div class="bucket-strip" aria-label="Recommendation counts">
              {context.bucket_strip_markup}
            </div>
            <div class="explorer-shell">
              <div class="panel">
                <div class="panel-header">
                  <div>
                    <h3 class="panel-title">Filters</h3>
                    <p class="panel-copy">Compact toolbar for quick narrowing. The list below stays in a Finder-style table view.</p>
                  </div>
                  <button class="button button-secondary button-compact" id="reset-filters" type="button">Reset</button>
                </div>

                <div class="filter-toolbar">
                  <div class="filter-group filter-search">
                    <label class="filter-label" for="search">Search</label>
                    <input class="filter-input mono" id="search" type="search" placeholder="path, role, category" />
                  </div>

                  <div class="filter-group">
                    <label class="filter-label" for="role-filter">Role</label>
                    <select class="filter-select mono" id="role-filter"></select>
                  </div>

                  <div class="filter-group">
                    <label class="filter-label" for="category-filter">Category</label>
                    <select class="filter-select mono" id="category-filter"></select>
                  </div>

                  <div class="filter-group">
                    <label class="filter-label" for="confidence-filter">Confidence</label>
                    <select class="filter-select mono" id="confidence-filter"></select>
                  </div>

                  <div class="filter-group">
                    <label class="filter-label" for="duplicate-filter">Duplicate</label>
                    <select class="filter-select mono" id="duplicate-filter"></select>
                  </div>
                </div>
              </div>

              <div class="panel">
                <div class="results-meta">
                  <div>
                    <div class="results-count" id="results-count">Loading results...</div>
                    <div class="results-subtext" id="results-subtext"></div>
                  </div>
                  <div class="highlights-nav" id="active-filter-summary"></div>
                </div>
                <div class="results-head finder-grid">
                  <button type="button" data-sort-key="name">Name <span class="sort-indicator" aria-hidden="true"></span></button>
                  <button type="button" data-sort-key="signal">Signal <span class="sort-indicator" aria-hidden="true"></span></button>
                  <button type="button" data-sort-key="role">Role <span class="sort-indicator" aria-hidden="true"></span></button>
                  <button type="button" data-sort-key="size">Size <span class="sort-indicator" aria-hidden="true"></span></button>
                  <button type="button" data-sort-key="modified">Modified <span class="sort-indicator" aria-hidden="true"></span></button>
                  <div class="results-head-static">Info</div>
                </div>
                <div class="results-list" id="results-list"></div>
                <div class="pagination-bar hidden" id="pagination-bar">
                  <div class="pagination-controls">
                    <button class="button button-secondary" id="page-first" type="button" aria-label="First page">&laquo;</button>
                    <button class="button button-secondary" id="page-prev" type="button" aria-label="Previous page">&lt;</button>
                    <div class="pagination-current mono" id="page-current"></div>
                    <button class="button button-secondary" id="page-next" type="button" aria-label="Next page">&gt;</button>
                    <button class="button button-secondary" id="page-last" type="button" aria-label="Last page">&raquo;</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="section" id="reasons">
          <div class="container">
            <details class="catalog-shell">
              <summary class="catalog-shell-summary">
                <div>
                  <span class="catalog-title">Evidence Guide &amp; External Links</span>
                  <span class="catalog-copy">
                    Click this header to collapse or expand the catalog. Each reason code below also toggles its own details.
                  </span>
                </div>
                <span class="pill mono">{context.reason_catalog_count} reason codes <span class="catalog-toggle-chevron" aria-hidden="true">&#9662;</span></span>
              </summary>
              <div class="catalog-body">
                {context.catalog_assumptions_markup}
                <ul class="reason-list" id="reason-catalog"></ul>
              </div>
            </details>
          </div>
        </section>
      </main>
    </div>

    <script id="report-data" type="application/json">{context.data_json}</script>
    <script>
      const data = JSON.parse(document.getElementById("report-data").textContent);

      const recommendationOrder = {{
        keep_synced: 0,
        candidate_to_sync: 1,
        review: 2,
        archive_candidate: 3,
        purge_candidate: 4,
        ignore: 5,
      }};

      const confidenceOrder = {{
        high: 0,
        medium: 1,
        low: 2,
      }};

      const bucketLabels = {{
        keep_synced: "Keep Synced",
        candidate_to_sync: "Candidates to Sync",
        review: "Review",
        archive_candidate: "Archive Candidates",
        purge_candidate: "Purge Candidates",
        ignore: "Ignore",
      }};

      const state = {{
        search: "",
        role: "all",
        category: "all",
        confidence: "all",
        duplicate: "all",
        sortKey: "signal",
        sortDirection: "asc",
        pageSize: 80,
        page: 1,
      }};

      const entries = data.entries.map((entry) => ({{
        ...entry,
        searchText: [
          entry.logical_path,
          entry.relative_path,
          entry.role,
          entry.semantic_category,
          entry.recommendation,
          entry.confidence,
          entry.source_name,
          entry.root_type,
          entry.kind,
          ...(entry.reason_codes || []),
        ].join(" ").toLowerCase(),
      }}));

      const reasonUsage = entries.reduce((accumulator, entry) => {{
        (entry.reason_codes || []).forEach((code) => {{
          if (!accumulator[code]) {{
            accumulator[code] = {{
              count: 0,
              buckets: new Set(),
              sample: null,
            }};
          }}
          accumulator[code].count += 1;
          accumulator[code].buckets.add(entry.recommendation);
          if (!accumulator[code].sample || accumulator[code].sample.kind === "dir") {{
            accumulator[code].sample = entry;
          }}
        }});
        return accumulator;
      }}, {{}});

      const elements = {{
        search: document.getElementById("search"),
        roleFilter: document.getElementById("role-filter"),
        categoryFilter: document.getElementById("category-filter"),
        confidenceFilter: document.getElementById("confidence-filter"),
        duplicateFilter: document.getElementById("duplicate-filter"),
        resetFilters: document.getElementById("reset-filters"),
        resultsCount: document.getElementById("results-count"),
        resultsSubtext: document.getElementById("results-subtext"),
        activeFilterSummary: document.getElementById("active-filter-summary"),
        resultsList: document.getElementById("results-list"),
        paginationBar: document.getElementById("pagination-bar"),
        pageFirst: document.getElementById("page-first"),
        pagePrev: document.getElementById("page-prev"),
        pageCurrent: document.getElementById("page-current"),
        pageNext: document.getElementById("page-next"),
        pageLast: document.getElementById("page-last"),
        highlightTabs: document.getElementById("highlight-tabs"),
        highlightPanel: document.getElementById("highlight-panel"),
        reasonCatalog: document.getElementById("reason-catalog"),
        sortButtons: Array.from(document.querySelectorAll("[data-sort-key]")),
      }};

      function formatNumber(value) {{
        return new Intl.NumberFormat().format(value);
      }}

      function formatBytes(bytes) {{
        if (bytes < 1024) return `${{bytes}} B`;
        const units = ["KiB", "MiB", "GiB", "TiB"];
        let size = bytes;
        for (const unit of units) {{
          size /= 1024;
          if (size < 1024) return `${{size.toFixed(1)}} ${{unit}}`;
        }}
        return `${{size.toFixed(1)}} PiB`;
      }}

      function escapeHtml(value) {{
        return String(value)
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#39;");
      }}

      function optionMarkup(values, label, formatter = (value) => value) {{
        return ['<option value="all">All ' + label + '</option>']
          .concat(values.map((value) => `<option value="${{escapeHtml(value)}}">${{escapeHtml(formatter(value))}}</option>`))
          .join("");
      }}

      function titleCaseLabel(value) {{
        return String(value || "")
          .replace(/_/g, " ")
          .split(" ")
          .filter(Boolean)
          .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
          .join(" ");
      }}

      function formatBucketLabel(bucket) {{
        return bucketLabels[bucket] || titleCaseLabel(bucket);
      }}

      function formatSourceKind(kind) {{
        const labels = {{
          official: "Official",
          third_party: "Third Party",
          research: "Research",
        }};
        return labels[kind] || titleCaseLabel(kind);
      }}

      function formatRootLabel(root) {{
        return String(root || "").replace(/_/g, " ");
      }}

      function splitPath(path) {{
        const normalized = String(path || "");
        const parts = normalized.split("/");
        if (parts.length <= 1) {{
          return {{ directory: "", name: normalized }};
        }}
        const name = parts.pop() || normalized;
        return {{ directory: parts.join("/") + "/", name }};
      }}

      function uniqueValues(key) {{
        return Array.from(new Set(entries.map((entry) => entry[key]).filter(Boolean))).sort((a, b) => String(a).localeCompare(String(b)));
      }}

      function renderFilterOptions() {{
        elements.roleFilter.innerHTML = optionMarkup(uniqueValues("role"), "roles");
        elements.categoryFilter.innerHTML = optionMarkup(uniqueValues("semantic_category"), "categories");
        const confidenceValues = ["high", "medium", "low"].filter((value) => entries.some((entry) => entry.confidence === value));
        elements.confidenceFilter.innerHTML = optionMarkup(confidenceValues, "confidence levels", titleCaseLabel);
        elements.duplicateFilter.innerHTML = [
          '<option value="all">All files</option>',
          '<option value="duplicates_only">Duplicates Only</option>',
        ].join("");
      }}

      function activeFilters() {{
        const filters = [];
        if (state.search) filters.push(`search:${{state.search}}`);
        if (state.role !== "all") filters.push(`role:${{state.role}}`);
        if (state.category !== "all") filters.push(`category:${{state.category}}`);
        if (state.confidence !== "all") filters.push(`confidence:${{state.confidence}}`);
        if (state.duplicate !== "all") filters.push(`duplicate:${{state.duplicate}}`);
        return filters;
      }}

      function filterEntries() {{
        return entries.filter((entry) => {{
          if (state.search && !entry.searchText.includes(state.search.toLowerCase())) return false;
          if (state.role !== "all" && entry.role !== state.role) return false;
          if (state.category !== "all" && entry.semantic_category !== state.category) return false;
          if (state.confidence !== "all" && entry.confidence !== state.confidence) return false;
          if (state.duplicate === "duplicates_only" && !entry.has_duplicate_hash) return false;
          if (entry.recommendation === "ignore") return false;
          if (entry.kind === "dir") return false;
          return true;
        }});
      }}

      function sortEntries(filtered) {{
        const items = filtered.slice();
        items.sort((a, b) => {{
          let comparison = 0;
          if (state.sortKey === "name") {{
            comparison = a.logical_path.localeCompare(b.logical_path) || a.source_name.localeCompare(b.source_name);
          }} else if (state.sortKey === "role") {{
            comparison = a.role.localeCompare(b.role) || a.logical_path.localeCompare(b.logical_path);
          }} else if (state.sortKey === "size") {{
            comparison = a.size_bytes - b.size_bytes || a.logical_path.localeCompare(b.logical_path);
          }} else if (state.sortKey === "modified") {{
            comparison = String(a.modified_time_utc).localeCompare(String(b.modified_time_utc)) || a.logical_path.localeCompare(b.logical_path);
          }} else {{
            comparison = recommendationOrder[a.recommendation] - recommendationOrder[b.recommendation]
              || confidenceOrder[a.confidence] - confidenceOrder[b.confidence]
              || b.size_bytes - a.size_bytes
              || a.logical_path.localeCompare(b.logical_path);
          }}

          if (state.sortDirection === "desc") {{
            comparison *= -1;
          }}
          return comparison;
        }});
        return items;
      }}

      function updateSortButtons() {{
        elements.sortButtons.forEach((button) => {{
          const key = button.dataset.sortKey || "";
          const active = key === state.sortKey;
          button.classList.toggle("active", active);
          button.setAttribute("aria-pressed", active ? "true" : "false");
          const indicator = button.querySelector(".sort-indicator");
          if (!indicator) return;
          indicator.textContent = active ? (state.sortDirection === "desc" ? "↓" : "↑") : "";
        }});
      }}

      function renderPagination(totalCount, totalPages, startIndex, endIndex) {{
        if (totalCount === 0 || totalPages <= 1) {{
          elements.paginationBar.classList.add("hidden");
          elements.pageCurrent.textContent = "";
          return;
        }}

        elements.paginationBar.classList.remove("hidden");
        elements.pageFirst.disabled = state.page <= 1;
        elements.pagePrev.disabled = state.page <= 1;
        elements.pageNext.disabled = state.page >= totalPages;
        elements.pageLast.disabled = state.page >= totalPages;
        elements.pageCurrent.textContent = `Page ${{formatNumber(state.page)}} of ${{formatNumber(totalPages)}}`;
      }}

      function formatShortDate(value) {{
        try {{
          return new Intl.DateTimeFormat(undefined, {{
            month: "short",
            day: "numeric",
            year: "numeric",
            timeZone: "UTC",
          }}).format(new Date(value));
        }} catch (_error) {{
          return value;
        }}
      }}

      function renderReferenceCard(reference) {{
        if (!reference) {{
          return "";
        }}

        const sourceMarkup = (reference.sources || []).map((source) => `
          <a class="reference-link mono" href="${{escapeHtml(source.url)}}" target="_blank" rel="noreferrer noopener">
            <span>${{escapeHtml(source.label)}}</span>
            <span class="reference-source-kind">${{escapeHtml(formatSourceKind(source.kind || "official"))}}</span>
          </a>
        `).join("");
        const fieldNotes = (reference.field_notes || []).length
          ? `
            <ul class="reference-list">
              ${{(reference.field_notes || []).map((item) => `<li>${{escapeHtml(item)}}</li>`).join("")}}
            </ul>
          `
          : "";
        const cautions = (reference.cautions || []).length
          ? `
            <ul class="reference-list">
              ${{(reference.cautions || []).map((item) => `<li>${{escapeHtml(item)}}</li>`).join("")}}
            </ul>
          `
          : "";
        const sourceSection = sourceMarkup
          ? `<div class="reference-sources">${{sourceMarkup}}</div>`
          : "";

        return `
          <div class="highlight-detail-card known-reference-card">
            <div class="highlight-detail-title">${{escapeHtml(reference.panel_title || "OpenClaw Reference")}}</div>
            <div class="known-reference-summary">${{escapeHtml(reference.title)}} · ${{escapeHtml(titleCaseLabel(reference.category))}}</div>
            <div class="highlight-detail-value">${{escapeHtml(reference.summary)}}</div>
            <ul class="reference-list">
              <li><strong>Purpose:</strong> ${{escapeHtml(reference.purpose)}}</li>
              <li><strong>How OpenClaw uses it:</strong> ${{escapeHtml(reference.openclaw_use)}}</li>
              <li><strong>Standard location:</strong> <span class="mono">${{escapeHtml(reference.location)}}</span></li>
            </ul>
            ${{fieldNotes ? `<div class="reference-note"><strong>Field notes</strong></div>${{fieldNotes}}` : ""}}
            ${{cautions ? `<div class="reference-note"><strong>Cautions</strong></div>${{cautions}}` : ""}}
            <div class="reference-note">${{escapeHtml(reference.note)}}</div>
            ${{sourceSection}}
          </div>
        `;
      }}

      function resultCard(entry) {{
        const pathParts = splitPath(entry.logical_path);
        const previewMarkup = entry.text_preview
          ? `
            <details class="preview-disclosure">
              <summary>Preview Bytes</summary>
              <pre class="preview-block preview-block-compact mono">${{escapeHtml(entry.text_preview)}}</pre>
            </details>
          `
          : `
            <div class="preview-empty">No preview captured for this file.</div>
          `;

        return `
          <details class="result-card">
            <summary class="result-summary finder-grid">
              <div class="finder-name-cell">
                <div class="finder-name-stack">
                  <div class="finder-path mono" title="${{escapeHtml(entry.logical_path)}}">
                    <span class="finder-directory">${{escapeHtml(pathParts.directory || "/")}}</span><span class="finder-filename">${{escapeHtml(pathParts.name)}}</span>
                  </div>
                </div>
              </div>
              <div class="finder-signal">
                <span class="tag recommendation-${{entry.recommendation}}">${{escapeHtml(formatBucketLabel(entry.recommendation))}}</span>
                <span class="tag confidence-${{entry.confidence}}">${{escapeHtml(titleCaseLabel(entry.confidence))}}</span>
              </div>
              <div class="finder-role">${{escapeHtml(entry.role)}}</div>
              <div class="finder-size mono">${{formatBytes(entry.size_bytes)}}</div>
              <div class="finder-modified mono" title="${{escapeHtml(entry.modified_time_utc)}}">${{escapeHtml(formatShortDate(entry.modified_time_utc))}}</div>
              <div class="finder-action">
                <span class="finder-info">
                  <span class="finder-info-closed">Info</span>
                  <span class="finder-info-open">Hide</span>
                </span>
              </div>
            </summary>
            <div class="finder-detail">
              ${{renderReferenceCard(entry.known_reference)}}
              ${{renderReferenceCard(entry.skill_registry_reference)}}
              ${{renderReferenceCard(entry.file_type_reference)}}
              ${{previewMarkup}}
            </div>
          </details>
        `;
      }}

      function renderResults() {{
        const filtered = sortEntries(filterEntries());
        const totalPages = Math.max(1, Math.ceil(filtered.length / state.pageSize));
        if (state.page > totalPages) {{
          state.page = totalPages;
        }}
        const startIndex = filtered.length ? (state.page - 1) * state.pageSize + 1 : 0;
        const endIndex = Math.min(filtered.length, state.page * state.pageSize);
        const visible = filtered.slice(startIndex ? startIndex - 1 : 0, endIndex);

        elements.resultsCount.textContent = `${{formatNumber(filtered.length)}} matching entries`;
        elements.resultsSubtext.textContent = filtered.length
          ? (state.duplicate === "duplicates_only"
            ? "Showing paginated duplicate files only. Ignored entries and directories stay hidden in this view."
            : "Ignored entries and directories stay hidden in this view.")
          : "No rows match the current filter set.";

        const filters = activeFilters();
        elements.activeFilterSummary.innerHTML = filters.length
          ? filters.map((item) => `<span class="tag mono">${{escapeHtml(item)}}</span>`).join("")
          : `<span class="tag mono">default view</span>`;

        if (!visible.length) {{
          elements.resultsList.innerHTML = `
            <div class="result-card" style="padding: 12px;">
              <h3>No matching entries</h3>
              <p class="section-copy">Try widening the search or clearing one of the remaining filters.</p>
            </div>
          `;
          renderPagination(0, 0, 0, 0);
          return;
        }}

        elements.resultsList.innerHTML = visible.map(resultCard).join("");
        updateSortButtons();
        renderPagination(filtered.length, totalPages, startIndex, endIndex);
      }}

      function renderHighlightInquiry(item) {{
        const inquiry = item.inquiry || item.sleuth;
        const inquiryInfoLabel = "For selected files, the OpenClaw instance is directly asked to assess what the file does, why it exists, and whether it appears important.";
        const inquiryTooltipId = `inquiry-tooltip-${{escapeHtml(String(item.absolute_path || item.path || "row")).replace(/[^a-zA-Z0-9_-]/g, "-")}}`;
        const inquiryTitle = `
          <div class="detail-title-row">
            <span>OpenClaw File Inquiry</span>
            <span class="tooltip-shell">
              <button class="inquiry-info-badge" type="button" aria-label="${{escapeHtml(inquiryInfoLabel)}}" aria-describedby="${{inquiryTooltipId}}">
                i
              </button>
              <span class="inquiry-tooltip" id="${{inquiryTooltipId}}" role="tooltip">${{escapeHtml(inquiryInfoLabel)}}</span>
            </span>
          </div>
        `;
        if (!inquiry) {{
          return `
            <div class="highlight-detail-card inquiry-card">
              <div class="highlight-detail-title">${{inquiryTitle}}</div>
              <div class="highlight-detail-value">Not captured for this row in this run.</div>
              <div class="inquiry-example">
                <div class="inquiry-example-label">Example response</div>
                <ul class="inquiry-list">
                  <li><strong>What it is:</strong> Likely a durable OpenClaw workspace or control file.</li>
                  <li><strong>Why it exists:</strong> Supports agent behavior, memory, skills, or runtime setup for this installation.</li>
                  <li><strong>If deleted:</strong> OpenClaw may lose context, configuration, or a workflow dependency.</li>
                  <li><strong>Recommended action:</strong> Keep. Durable context and configuration files usually deserve preservation.</li>
                </ul>
              </div>
            </div>
          `;
        }}

        if (inquiry.status && inquiry.status !== "ok") {{
          return `
            <div class="highlight-detail-card inquiry-card">
              <div class="highlight-detail-title">${{inquiryTitle}}</div>
              <div class="highlight-detail-value">${{escapeHtml(inquiry.message || "OpenClaw did not return a structured explanation.")}}</div>
            </div>
          `;
        }}

        const meta = [
          inquiry.importance ? `<span class="tag mono">${{escapeHtml(titleCaseLabel(String(inquiry.importance).replace(/_/g, " ")))}}</span>` : "",
          inquiry.standardness ? `<span class="tag mono">${{escapeHtml(titleCaseLabel(String(inquiry.standardness).replace(/_/g, " ")))}}</span>` : "",
          inquiry.confidence ? `<span class="tag mono">${{escapeHtml(titleCaseLabel(inquiry.confidence))}} confidence</span>` : "",
          inquiry.model ? `<span class="tag mono">${{escapeHtml(inquiry.model)}}</span>` : "",
          inquiry.duration_ms ? `<span class="tag mono">${{escapeHtml(formatNumber(inquiry.duration_ms))}} ms</span>` : "",
        ].filter(Boolean).join("");
        const evidenceBasis = Array.isArray(inquiry.evidence_basis) && inquiry.evidence_basis.length
          ? inquiry.evidence_basis.map((item) => titleCaseLabel(String(item).replace(/_/g, " "))).join(", ")
          : "";
        const actionSummary = inquiry.recommended_action && inquiry.action_reason
          ? `${{titleCaseLabel(String(inquiry.recommended_action).replace(/_/g, " "))}}. ${{inquiry.action_reason}}`
          : inquiry.action_reason || inquiry.keep_note || inquiry.recommended_action || "unsure";
        const archiveNote = inquiry.archive_note && inquiry.archive_note !== "not_needed"
          ? `<li><strong>Archive note:</strong> ${{escapeHtml(inquiry.archive_note)}}</li>`
          : "";
        const evidenceMarkup = evidenceBasis
          ? `<li><strong>Evidence basis:</strong> ${{escapeHtml(evidenceBasis)}}</li>`
          : "";
        const authorship = inquiry.authorship || "unsure";

        return `
          <div class="highlight-detail-card inquiry-card">
            <div class="highlight-detail-title">${{inquiryTitle}}</div>
            <ul class="inquiry-list">
              <li><strong>What it is:</strong> ${{escapeHtml(inquiry.what_it_is || "unsure")}}</li>
              <li><strong>Why it exists:</strong> ${{escapeHtml(inquiry.why_it_exists || "unsure")}}</li>
              <li><strong>Authorship:</strong> ${{escapeHtml(authorship)}}</li>
              <li><strong>If deleted:</strong> ${{escapeHtml(inquiry.if_deleted || "unsure")}}</li>
              <li><strong>Recommended action:</strong> ${{escapeHtml(actionSummary)}}</li>
              ${{archiveNote}}
              ${{evidenceMarkup}}
            </ul>
            <div class="inquiry-meta">${{meta}}</div>
          </div>
        `;
      }}

      function renderDuplicateHighlightCard(item) {{
        if (!item || !item.duplicate_count || item.duplicate_count < 2) {{
          return "";
        }}

        return `
          <div class="highlight-detail-card">
            <div class="highlight-detail-title">Duplicate Summary</div>
            <div class="duplicate-group-summary">
              <span class="tag mono">${{escapeHtml(formatNumber(item.duplicate_count))}} files in group</span>
              <span class="tag mono">${{escapeHtml(formatBytes(item.reclaimable_bytes || 0))}} reclaimable</span>
              <span class="tag mono">hash ${{escapeHtml(item.sha256_prefix || "")}}</span>
            </div>
            <div class="highlight-detail-value duplicate-group-note">
              This tab shows a representative sample only. Use File Explorer with Duplicate set to Duplicates Only to browse and page through the full duplicate file list.
            </div>
          </div>
        `;
      }}

      function renderHighlightSupplement(item, options = {{}}) {{
        const includeInquiry = options.includeInquiry !== false;
        const previewMarkup = item.text_preview
          ? `
            <details class="highlight-preview-details">
              <summary>Preview Bytes</summary>
              <pre class="highlight-preview-block mono">${{escapeHtml(item.text_preview)}}</pre>
            </details>
          `
          : "";

        return `
          ${{renderDuplicateHighlightCard(item)}}
          ${{renderReferenceCard(item.known_reference)}}
          ${{renderReferenceCard(item.skill_registry_reference)}}
          ${{renderReferenceCard(item.file_type_reference)}}
          ${{includeInquiry ? renderHighlightInquiry(item) : ""}}
          ${{previewMarkup}}
        `;
      }}

      function renderHighlightDetails(item, options = {{}}) {{
        return `
          <div class="highlight-row-details">
            ${{renderHighlightSupplement(item, options)}}
          </div>
        `;
      }}

      function duplicateSampleBrowser(items, summary) {{
        const summaryMarkup = `
          <div class="highlight-detail-card">
            <div class="highlight-detail-title">Duplicates</div>
            <div class="duplicate-group-summary">
              <span class="tag mono">${{escapeHtml(formatNumber(summary.group_count || 0))}} groups</span>
              <span class="tag mono">${{escapeHtml(formatNumber(summary.duplicate_file_count || 0))}} files</span>
              <span class="tag mono">${{escapeHtml(formatBytes(summary.reclaimable_bytes || 0))}} reclaimable</span>
            </div>
            <div class="highlight-detail-value duplicate-group-note">
              Showing 10 representative duplicate files only. Use File Explorer with Duplicate set to Duplicates Only to browse and page through the full duplicate file list. OpenClaw workspace mirror entries are excluded.
            </div>
          </div>
        `;

        if (!items.length) {{
          return `
            <div class="highlight-browser">
              ${{summaryMarkup}}
              <div class="highlight-empty">
                No exact duplicate file groups were found.
              </div>
            </div>
          `;
        }}

        return `
          <div class="highlight-browser">
            ${{summaryMarkup}}
            ${{highlightBrowser(items, {{ includeInquiry: false }})}}
          </div>
        `;
      }}

      function highlightBrowser(items, options = {{}}) {{
        if (!items.length) {{
          return `<div class="highlight-empty">No entries matched this highlight.</div>`;
        }}

        const rows = items.slice(0, 10).map((item) => {{
          const pathParts = splitPath(item.path);
          const duplicateMeta = item.duplicate_count && item.duplicate_count > 1
            ? `<span>${{escapeHtml(formatNumber(item.duplicate_count))}} duplicate files</span>`
            : "";
          return `
            <details class="highlight-browser-row">
              <summary class="highlight-summary highlight-browser-grid">
                <div class="highlight-cell path-col">
                  <div class="highlight-path-cell">
                    <div class="highlight-path-stack">
                      <div class="highlight-path mono">
                        <span class="highlight-directory">${{escapeHtml(pathParts.directory || "/")}}</span><span class="highlight-name">${{escapeHtml(pathParts.name)}}</span>
                      </div>
                      <div class="highlight-submeta">
                        <span>${{escapeHtml(item.role)}}</span>
                        <span>${{escapeHtml(item.semantic_category)}}</span>
                        ${{duplicateMeta}}
                      </div>
                    </div>
                  </div>
                </div>
                <div class="highlight-cell highlight-root">${{escapeHtml(formatRootLabel(item.root_type))}}</div>
                <div class="highlight-cell">
                  <span class="highlight-signal">
                    <span class="tag recommendation-${{item.recommendation}}">${{escapeHtml(formatBucketLabel(item.recommendation))}}</span>
                    <span class="tag confidence-${{item.confidence}}">${{escapeHtml(titleCaseLabel(item.confidence))}}</span>
                  </span>
                </div>
                <div class="highlight-cell mono">${{formatBytes(item.size_bytes)}}</div>
                <div class="highlight-cell mono">${{formatNumber(item.age_days)}}d</div>
                <div class="highlight-action">
                  <span class="highlight-info">
                    <span class="highlight-info-closed">Info</span>
                    <span class="highlight-info-open">Hide</span>
                  </span>
                </div>
              </summary>
              ${{renderHighlightDetails(item, options)}}
            </details>
          `;
        }}).join("");

        return `
          <div class="highlight-browser">
            <div class="highlight-browser-head highlight-browser-grid">
              <div>Path</div>
              <div>Root</div>
              <div>Signal</div>
              <div>Size</div>
              <div>Age</div>
              <div>Info</div>
            </div>
            ${{rows}}
          </div>
        `;
      }}

      let highlightSections = [];
      let activeHighlightTab = 0;

      const highlightLabels = {{
        largest_files: "Largest",
        stalest_files: "Stale",
        duplicate_groups: "Duplicates",
        notable_unknown_files: "Unknown",
        symlinks: "Symlinks",
        keep_synced: "Keep Synced",
        candidate_to_sync: "Sync Candidates",
        review: "Review",
        archive_candidate: "Archive Candidates",
        purge_candidate: "Purge Candidates",
      }};

      function renderHighlights() {{
        highlightSections = [
          ["largest_files", highlightLabels.largest_files, data.highlights.largest_files || []],
          ["stalest_files", highlightLabels.stalest_files, data.highlights.stalest_files || []],
          ["duplicate_groups", highlightLabels.duplicate_groups, data.highlights.duplicate_groups || []],
          ["notable_unknown_files", highlightLabels.notable_unknown_files, data.highlights.notable_unknown_files || []],
          ["symlinks", highlightLabels.symlinks, data.highlights.symlinks || []],
        ];

        Object.entries(data.highlights.top_recommendations_by_bucket || {{}}).forEach(([bucket, items]) => {{
          highlightSections.push([bucket, highlightLabels[bucket] || formatBucketLabel(bucket), items]);
        }});

        if (activeHighlightTab >= highlightSections.length) {{
          activeHighlightTab = 0;
        }}

        elements.highlightTabs.innerHTML = highlightSections.map(([, label], index) => `
          <button
            type="button"
            class="highlight-tab${{index === activeHighlightTab ? " active" : ""}}"
            data-highlight-tab="${{index}}"
          >
            ${{escapeHtml(label)}}
          </button>
        `).join("");

        const [key, , items] = highlightSections[activeHighlightTab];
        elements.highlightPanel.innerHTML = key === "duplicate_groups"
          ? duplicateSampleBrowser(items, data.highlights.duplicate_groups_summary || {{}})
          : highlightBrowser(items);

        elements.highlightTabs.querySelectorAll("[data-highlight-tab]").forEach((button) => {{
          button.addEventListener("click", () => {{
            activeHighlightTab = Number(button.dataset.highlightTab || 0);
            renderHighlights();
          }});
        }});
      }}

      function reasonCatalogDetails(code) {{
        if (code.startsWith("ROLE_")) {{
          return {{
            family: "Role signal",
            meaning: "The snapshot already assigned a semantic role to the file, so this is closer to an explicit classification than a filename guess.",
            context: "Snapshot role semantics are one of the strongest inputs, so these codes often drive the recommendation directly.",
          }};
        }}
        if (code.startsWith("PATH_")) {{
          return {{
            family: "Path signal",
            meaning: "The file path or filename matched a known pattern such as memory, meeting notes, models, tools, or backup-like locations.",
            context: "Path and filename patterns are supporting evidence that help identify durable files, hidden data, or generated artifacts.",
          }};
        }}
        if (code.startsWith("GIT_")) {{
          return {{
            family: "Git signal",
            meaning: "The snapshot captured Git state for this path, such as tracked, ignored, or untracked.",
            context: "Git state reflects repository intent and can separate tracked source material from ignored or transient files.",
          }};
        }}
        if (code.startsWith("STALE_")) {{
          return {{
            family: "Age signal",
            meaning: "The file crossed a staleness threshold relative to the snapshot timestamp used for this run.",
            context: "Staleness is advisory only. It raises review attention, but age by itself should not imply cleanup.",
          }};
        }}
        if (code.startsWith("ROOT_")) {{
          return {{
            family: "Root signal",
            meaning: "The file lives under a specific root, such as the OpenClaw internal root or the workspace root.",
            context: "Root location helps distinguish OpenClaw internals from workspace content and other mirrored areas.",
          }};
        }}
        if (code.startsWith("KIND_") || code.startsWith("SYMLINK_")) {{
          return {{
            family: "Filesystem signal",
            meaning: "The filesystem type itself influenced the recommendation, especially for directories and symlinks.",
            context: "Filesystem kind is primarily a safety check, especially for directories and symlinks that should be handled conservatively.",
          }};
        }}
        if (code === "LARGE_FILE" || code.startsWith("SIZE_")) {{
          return {{
            family: "Size signal",
            meaning: "The file size crossed a threshold that makes storage, transport, or sync cost materially higher.",
            context: "Large files affect storage and sync cost, so size is used to surface higher-friction items for review.",
          }};
        }}
        if (code === "DUPLICATE_HASH") {{
          return {{
            family: "Duplicate signal",
            meaning: "Another analyzed entry had the same content hash, so the report detected duplicate content.",
            context: "Matching content hashes suggest redundancy, but duplicate content still needs human confirmation before any action.",
          }};
        }}
        if (code === "TEXT_LIKE" || code === "BINARY_LIKE") {{
          return {{
            family: "Content signal",
            meaning: "A lightweight content heuristic classified the file as document-like text or blob-like binary data.",
            context: "Content-shape heuristics help separate document-like files from media or blobs, but they are secondary evidence.",
          }};
        }}
        if (code.startsWith("UNKNOWN_")) {{
          return {{
            family: "Unknown signal",
            meaning: "The analyzer could not confidently map the file into a stronger semantic category or role.",
            context: "Unknown roles or categories keep the recommendation conservative until stronger evidence appears.",
          }};
        }}
        return {{
          family: "Supporting signal",
          meaning: "This code is supporting evidence rather than a primary classification source.",
          context: "This code contributes supporting evidence to the recommendation and confidence estimate.",
        }};
      }}

      function reasonUsageSummary(code) {{
        const usage = reasonUsage[code];
        if (!usage) {{
          return {{
            count: 0,
            bucketLabels: [],
            sample: null,
          }};
        }}
        const bucketLabels = Array.from(usage.buckets)
          .sort((left, right) => recommendationOrder[left] - recommendationOrder[right])
          .map((bucket) => formatBucketLabel(bucket));
        return {{
          count: usage.count,
          bucketLabels,
          sample: usage.sample,
        }};
      }}

      function renderReasonCatalog() {{
        const reasonEntries = Object.entries(data.reason_catalog || {{}})
          .sort(([left], [right]) => left.localeCompare(right));
        elements.reasonCatalog.innerHTML = reasonEntries.map(([code, description]) => {{
          const details = reasonCatalogDetails(code);
          const usage = reasonUsageSummary(code);
          const usageText = usage.count
            ? `Seen on ${{formatNumber(usage.count)}} entr${{usage.count === 1 ? "y" : "ies"}}`
            : "Not present in this snapshot";
          const bucketText = usage.bucketLabels.length
            ? usage.bucketLabels.join(", ")
            : "No recommendation outcomes in this report";
          const exampleMarkup = usage.sample
            ? `<span class="reason-example"><code class="mono">${{escapeHtml(usage.sample.logical_path)}}</code><span class="tag recommendation-${{usage.sample.recommendation}}">${{escapeHtml(formatBucketLabel(usage.sample.recommendation))}}</span></span>`
            : "No concrete example in this snapshot.";
          return `
          <li class="reason-item">
            <details class="reason-disclosure" open>
              <summary class="reason-summary">
                <span class="reason-code mono">${{escapeHtml(code)}}</span>
                <span class="reason-family">${{escapeHtml(details.family)}}</span>
                <span class="reason-count mono">${{escapeHtml(usageText)}}</span>
                <span class="reason-toggle-hint">Click to collapse or expand</span>
              </summary>
              <div class="reason-body">
                <div class="reason-description">${{escapeHtml(description)}}</div>
                <ul class="reason-detail-list">
                  <li><span class="reason-detail-label">Meaning:</span> ${{escapeHtml(details.meaning)}}</li>
                  <li><span class="reason-detail-label">Why it matters:</span> ${{escapeHtml(details.context)}}</li>
                  <li><span class="reason-detail-label">Common outcomes here:</span> ${{escapeHtml(bucketText)}}</li>
                  <li><span class="reason-detail-label">Example:</span> ${{exampleMarkup}}</li>
                </ul>
              </div>
            </details>
          </li>
        `;
        }}).join("");
      }}

      function render() {{
        renderResults();
      }}

      function bindEvents() {{
        elements.search.addEventListener("input", (event) => {{
          state.search = event.target.value.trim();
          state.page = 1;
          render();
        }});

        [
          ["roleFilter", "role"],
          ["categoryFilter", "category"],
          ["confidenceFilter", "confidence"],
          ["duplicateFilter", "duplicate"],
        ].forEach(([elementName, stateKey]) => {{
          elements[elementName].addEventListener("change", (event) => {{
            state[stateKey] = event.target.value;
            state.page = 1;
            render();
          }});
        }});

        elements.resetFilters.addEventListener("click", () => {{
          state.search = "";
          state.role = "all";
          state.category = "all";
          state.confidence = "all";
          state.duplicate = "all";
          state.sortKey = "signal";
          state.sortDirection = "asc";
          state.page = 1;

          elements.search.value = "";
          elements.roleFilter.value = "all";
          elements.categoryFilter.value = "all";
          elements.confidenceFilter.value = "all";
          elements.duplicateFilter.value = "all";
          render();
        }});

        elements.sortButtons.forEach((button) => {{
          button.addEventListener("click", () => {{
            const key = button.dataset.sortKey || "signal";
            const defaultDirections = {{
              name: "asc",
              signal: "asc",
              role: "asc",
              size: "desc",
              modified: "desc",
            }};

            if (state.sortKey === key) {{
              state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
            }} else {{
              state.sortKey = key;
              state.sortDirection = defaultDirections[key] || "asc";
            }}
            state.page = 1;
            render();
          }});
        }});

        elements.pageFirst.addEventListener("click", () => {{
          if (state.page > 1) {{
            state.page = 1;
            renderResults();
          }}
        }});

        elements.pagePrev.addEventListener("click", () => {{
          if (state.page > 1) {{
            state.page -= 1;
            renderResults();
          }}
        }});

        elements.pageNext.addEventListener("click", () => {{
          state.page += 1;
          renderResults();
        }});

        elements.pageLast.addEventListener("click", () => {{
          const totalItems = filterEntries().length;
          const totalPages = Math.max(1, Math.ceil(totalItems / state.pageSize));
          if (state.page < totalPages) {{
            state.page = totalPages;
            renderResults();
          }}
        }});

        document.querySelectorAll("[data-copy]").forEach((button) => {{
          button.addEventListener("click", async () => {{
            try {{
              await navigator.clipboard.writeText(button.dataset.copy || "");
              button.classList.add("copied");
              const original = button.textContent;
              button.textContent = "Copied";
              window.setTimeout(() => {{
                button.classList.remove("copied");
                button.textContent = original;
              }}, 1200);
            }} catch (_error) {{
              button.textContent = "Copy failed";
            }}
          }});
        }});
      }}

      renderFilterOptions();
      renderHighlights();
      renderReasonCatalog();
      bindEvents();
      render();
    </script>
  </body>
</html>
"""
# --- End inlined module: report.py ---
