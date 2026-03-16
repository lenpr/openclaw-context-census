# --- Begin inlined module: file_knowledge.py ---
import re
from pathlib import PurePosixPath


_source = _reference_source
_entry = _reference_entry


FILE_KNOWLEDGE: dict[str, dict[str, object]] = {
    "agents_md": _entry(
        identifier="agents_md",
        title="AGENTS.md",
        category="bootstrap",
        summary="Workspace operating instructions and session-start contract.",
        purpose="Defines how the agent should behave in this workspace, what context it should read first, and what rules it should follow every session.",
        openclaw_use="OpenClaw injects AGENTS.md as part of the user-editable workspace files. The default template tells the agent to read SOUL.md, USER.md, recent daily memory, and MEMORY.md in the main private session before doing anything else.",
        location="Workspace root: AGENTS.md",
        note="This is the highest-leverage workspace file because it tells the agent what to load and how to operate.",
        field_notes=[
            "Community guides consistently describe AGENTS.md as the operating manual for the agent.",
            "Operational plugins exist because agents sometimes skip AGENTS instructions under pressure; this is a common field complaint rather than an official behavior guarantee.",
            "If you need stable instructions in every Discord channel or other isolated session, official docs recommend placing them in AGENTS.md or USER.md rather than MEMORY.md.",
        ],
        cautions=[
            "Do not overload AGENTS.md with raw logs or unstable facts; it works best as durable operating policy.",
            "Conflicting instructions across AGENTS.md, SOUL.md, and USER.md are a common source of setup drift in community reports.",
        ],
        sources=[
            _source("Agent Runtime", "https://docs.openclaw.ai/concepts/agent", "official"),
            _source("AGENTS.md Template", "https://docs.openclaw.ai/reference/templates/AGENTS", "official"),
            _source("Discord Memory Guidance", "https://docs.openclaw.ai/channels/discord", "official"),
            _source("AGENTS.md + SOUL.md Deep Dive", "https://www.reddit.com/r/openclawsetup/comments/1r7ei3o/agentsmd_soulmd_deep_dive/", "third_party", "Community walkthrough of common bootstrap patterns."),
            _source("Memory Guardian Plugin", "https://gist.github.com/joe-rlo/3c3193285804b05c99bbfe541ed53c4d", "third_party", "Operational workaround for agents ignoring memory instructions."),
        ],
    ),
    "soul_md": _entry(
        identifier="soul_md",
        title="SOUL.md",
        category="bootstrap",
        summary="Personality, values, tone, and behavioral boundaries for the agent.",
        purpose="Captures who the agent is supposed to be, how it should sound, what boundaries it should respect, and what kind of assistant it is trying to become.",
        openclaw_use="OpenClaw treats SOUL.md as a standard injected workspace file. The template frames it as the agent's identity and boundary document, and community tooling often treats it as the main persona layer.",
        location="Workspace root: SOUL.md",
        note="Use SOUL.md for durable identity and boundaries, not for volatile task state.",
        field_notes=[
            "Community ecosystems have formed around SOUL.md templates, including dedicated sharing sites and curation directories.",
            "Third-party explainers often describe SOUL.md as the first file the agent 'reads into being,' which matches the general intent but is still explanatory language rather than a formal API contract.",
        ],
        cautions=[
            "Community advice strongly warns against letting untrusted content or scraped web data write directly into SOUL.md.",
            "Security research has flagged instruction-heavy SKILL.md and persistent identity layers as prompt-injection surfaces, so keep SOUL.md concise and deliberate.",
        ],
        sources=[
            _source("Agent Runtime", "https://docs.openclaw.ai/concepts/agent", "official"),
            _source("SOUL.md Template", "https://docs.openclaw.ai/reference/templates/SOUL", "official"),
            _source("OpenClaw Lore", "https://docs.openclaw.ai/start/lore", "official"),
            _source("OpenClaw Soul", "https://openclawsoul.org/", "third_party", "Community explanation and ecosystem site around SOUL.md."),
            _source("souls.directory", "https://souls.directory/", "third_party", "Community directory for reusable SOUL.md templates."),
            _source("How I Finally Understood soul.md, user.md, and memory.md", "https://www.reddit.com/r/openclaw/comments/1r2kfs0/how_i_finally_understood_soulmd_usermd_and/", "third_party", "Community mental model and memory-poisoning caution."),
        ],
    ),
    "tools_md": _entry(
        identifier="tools_md",
        title="TOOLS.md",
        category="bootstrap",
        summary="Local environment notes that complement reusable skills.",
        purpose="Stores setup-specific facts such as device names, host aliases, room names, or local conventions that should not live inside reusable skill instructions.",
        openclaw_use="OpenClaw includes TOOLS.md among the standard workspace files. The template explicitly says skills define how tools work and TOOLS.md is for local specifics unique to one installation.",
        location="Workspace root: TOOLS.md",
        note="TOOLS.md is best for host-specific context that would be wrong or noisy in a generic skill.",
        field_notes=[
            "Community setups often leave TOOLS.md close to the default template for a long time, then grow it once hardware and automation surface area expands.",
            "The distinction 'skills are portable, TOOLS.md is local' is one of the clearest lines in the official template set.",
        ],
        cautions=[
            "Avoid duplicating skill instructions here unless they truly depend on this exact machine or home environment.",
        ],
        sources=[
            _source("Agent Runtime", "https://docs.openclaw.ai/concepts/agent", "official"),
            _source("TOOLS.md Template", "https://docs.openclaw.ai/reference/templates/TOOLS", "official"),
            _source("Four days in - TOOLS.md and SOUL.md still at template state", "https://www.reddit.com/r/openclaw/comments/1rakj0h/four_days_in_toolsmd_and_soulmd_still_at_template/", "third_party", "Community discussion about when TOOLS.md becomes useful in practice."),
        ],
    ),
    "user_md": _entry(
        identifier="user_md",
        title="USER.md",
        category="bootstrap",
        summary="Profile of the human the agent is helping.",
        purpose="Captures stable user preferences, naming, timezone, and operating constraints so the assistant can stay aligned over time.",
        openclaw_use="USER.md is one of the standard injected workspace files. The template expects it to be updated as the agent learns more about the user, and official Discord guidance recommends USER.md for context that should appear in every session.",
        location="Workspace root: USER.md",
        note="USER.md is about the human, not the assistant.",
        field_notes=[
            "Official docs imply USER.md is safer than MEMORY.md for cross-channel stable instructions because USER.md is injected every session while MEMORY.md is more restricted.",
            "Community operators often use USER.md for communication policy, recipient rules, and durable social boundaries.",
        ],
        cautions=[
            "Do not let noisy or untrusted content rewrite USER.md automatically; treat it as reviewed preference state.",
        ],
        sources=[
            _source("Agent Runtime", "https://docs.openclaw.ai/concepts/agent", "official"),
            _source("USER Template", "https://docs.openclaw.ai/reference/templates/USER", "official"),
            _source("Discord Memory Guidance", "https://docs.openclaw.ai/channels/discord", "official"),
            _source("How I Finally Understood soul.md, user.md, and memory.md", "https://www.reddit.com/r/openclaw/comments/1r2kfs0/how_i_finally_understood_soulmd_usermd_and/", "third_party"),
        ],
    ),
    "identity_md": _entry(
        identifier="identity_md",
        title="IDENTITY.md",
        category="bootstrap",
        summary="Self-description for the assistant instance.",
        purpose="Defines the assistant's name, creature, vibe, emoji, and other self-model details separate from deeper behavioral principles in SOUL.md.",
        openclaw_use="OpenClaw treats IDENTITY.md as one of the standard workspace files. The template is explicitly framed as something to fill in during the first conversation.",
        location="Workspace root: IDENTITY.md",
        note="IDENTITY.md is the short self-description layer; SOUL.md is the deeper values and behavior layer.",
        field_notes=[
            "Some community setup flows use BOOTSTRAP.md to interview the user and then generate both IDENTITY.md and SOUL.md together.",
        ],
        cautions=[
            "Do not turn IDENTITY.md into a second AGENTS.md; keep it focused on identity, not operating rules.",
        ],
        sources=[
            _source("Agent Runtime", "https://docs.openclaw.ai/concepts/agent", "official"),
            _source("IDENTITY Template", "https://docs.openclaw.ai/reference/templates/IDENTITY", "official"),
            _source("Create Soul and Identity", "https://gist.github.com/ideadude/95249fc80674d2f3f8b8b9b808623535", "third_party", "Community bootstrap flow built around official templates."),
        ],
    ),
    "heartbeat_md": _entry(
        identifier="heartbeat_md",
        title="HEARTBEAT.md",
        category="bootstrap",
        summary="Periodic-check task list for heartbeat polls.",
        purpose="Acts as the place to define what the agent should inspect or report on during periodic heartbeat runs.",
        openclaw_use="The HEARTBEAT template says to keep the file empty or comments-only to skip heartbeat API calls and add tasks only when periodic checks are wanted. The configuration reference also recognizes HEARTBEAT.md as a standard bootstrap file.",
        location="Workspace root: HEARTBEAT.md",
        note="An empty file is meaningful here; it disables heartbeat work without removing the document.",
        field_notes=[
            "Community upgrade guides often recommend making heartbeat prompts more proactive once a deployment is stable.",
            "Research on OpenClaw attack patterns has specifically called out cron and heartbeat frequency amplification as a deployment risk when prompts are poorly constrained.",
        ],
        cautions=[
            "Do not stuff heartbeat tasks with broad or high-cost scans unless you have rate, token, and messaging controls in place.",
        ],
        sources=[
            _source("Configuration Reference", "https://docs.openclaw.ai/gateway/configuration-reference", "official"),
            _source("HEARTBEAT Template", "https://docs.openclaw.ai/reference/templates/HEARTBEAT", "official"),
            _source("OpenClaw COO upgrade guide", "https://gist.github.com/1va7/baa9aa9d65c94482e0a6dc4c6bf40270", "third_party", "Community guidance for more proactive heartbeat behavior."),
            _source("Clawdrain", "https://arxiv.org/abs/2603.00902", "research", "Academic security analysis mentioning cron and heartbeat amplification."),
        ],
    ),
    "bootstrap_md": _entry(
        identifier="bootstrap_md",
        title="BOOTSTRAP.md",
        category="bootstrap",
        summary="One-time first-run bootstrap instructions.",
        purpose="Guides the agent through initial setup and identity formation in a fresh workspace before durable memory exists.",
        openclaw_use="Official docs describe BOOTSTRAP.md as a one-time first-run ritual that should be followed and then removed after setup is complete.",
        location="Workspace root: BOOTSTRAP.md",
        note="BOOTSTRAP.md is expected to be temporary.",
        field_notes=[
            "Both the official runtime docs and community guides treat BOOTSTRAP.md as a birth-certificate style onboarding file.",
        ],
        cautions=[
            "If BOOTSTRAP.md lingers long after setup, it may indicate onboarding never completed cleanly or the workspace keeps resetting.",
        ],
        sources=[
            _source("Agent Runtime", "https://docs.openclaw.ai/concepts/agent", "official"),
            _source("BOOTSTRAP Template", "https://docs.openclaw.ai/reference/templates/BOOTSTRAP", "official"),
            _source("AGENTS.md + SOUL.md Deep Dive", "https://www.reddit.com/r/openclawsetup/comments/1r7ei3o/agentsmd_soulmd_deep_dive/", "third_party"),
        ],
    ),
    "boot_md": _entry(
        identifier="boot_md",
        title="BOOT.md",
        category="bootstrap",
        summary="Per-startup hook instructions.",
        purpose="Stores short, explicit instructions OpenClaw should execute on startup when internal hooks are enabled.",
        openclaw_use="The official BOOT template says to use it for startup instructions when `hooks.internal.enabled` is on, and to send messages via the message tool followed by `NO_REPLY` if needed.",
        location="Workspace root: BOOT.md",
        note="BOOT.md is for repeated startup behavior; BOOTSTRAP.md is for one-time initialization.",
        field_notes=[
            "BOOT.md appears less frequently in community setups than AGENTS.md or SOUL.md, but it is part of the official template set.",
        ],
        cautions=[
            "Keep BOOT.md short and explicit. Startup hooks are easy to abuse with expensive or noisy actions.",
        ],
        sources=[
            _source("BOOT Template", "https://docs.openclaw.ai/reference/templates/BOOT", "official"),
        ],
    ),
    "memory_md": _entry(
        identifier="memory_md",
        title="MEMORY.md",
        category="memory",
        summary="Curated long-term memory for the assistant.",
        purpose="Stores distilled facts, decisions, and durable context worth carrying across sessions.",
        openclaw_use="Official memory docs treat MEMORY.md as the curated long-term memory layer. The AGENTS template says it should only be loaded in the main, private session rather than shared contexts.",
        location="Workspace root: MEMORY.md",
        note="MEMORY.md is for durable facts and distilled conclusions, not raw logs.",
        field_notes=[
            "Official docs say the files on disk are the source of truth; the model only 'remembers' what gets written to Markdown.",
            "Discord docs explicitly note that MEMORY.md does not auto-load in guild channels and should be accessed on demand with memory tools.",
            "Community operators often build additional project docs because MEMORY.md is intentionally not omnipresent in every context.",
        ],
        cautions=[
            "Treat MEMORY.md as reviewed memory. Community advice warns that auto-writing untrusted content here can become memory poisoning or long-term technical debt.",
            "If memory search is enabled, anything written here becomes part of semantic retrieval unless you change memory configuration.",
        ],
        sources=[
            _source("Memory", "https://docs.openclaw.ai/concepts/memory", "official"),
            _source("AGENTS.md Template", "https://docs.openclaw.ai/reference/templates/AGENTS", "official"),
            _source("Discord Memory Guidance", "https://docs.openclaw.ai/channels/discord", "official"),
            _source("FAQ", "https://docs.openclaw.ai/help/faq", "official"),
            _source("Project Knowledge Base Pattern", "https://gist.github.com/behindthegarage/1ba947e919f515ee847c107c415555b7", "third_party", "Community workaround for contexts where MEMORY.md is not injected."),
            _source("How I Finally Understood soul.md, user.md, and memory.md", "https://www.reddit.com/r/openclaw/comments/1r2kfs0/how_i_finally_understood_soulmd_usermd_and/", "third_party"),
            _source("From Assistant to Double Agent", "https://arxiv.org/abs/2602.08412", "research", "Academic warning about memory retrieval as an attack surface."),
        ],
    ),
    "memory_daily": _entry(
        identifier="memory_daily",
        title="Daily Memory File",
        category="memory",
        summary="Day-scoped running log for recent events and context.",
        purpose="Captures raw session history, notable events, and near-term context before important items are curated into long-term memory.",
        openclaw_use="Official memory docs and the AGENTS template use memory/YYYY-MM-DD.md as the daily memory pattern. OpenClaw reads today and yesterday on session start.",
        location="Workspace folder: memory/YYYY-MM-DD.md",
        note="This is the append-only working memory layer.",
        field_notes=[
            "Official memory docs describe these files as the daily log and explain that they are the primary source for semantic memory search.",
            "Community tooling like Memory Guardian exists because some operators want stronger guarantees that these files are actually updated before compaction or reset.",
        ],
        cautions=[
            "Without periodic distillation, daily memory can become stale, noisy, and expensive for search.",
            "Avoid treating daily notes as a substitute for reviewed long-term memory.",
        ],
        sources=[
            _source("Memory", "https://docs.openclaw.ai/concepts/memory", "official"),
            _source("AGENTS.md Template", "https://docs.openclaw.ai/reference/templates/AGENTS", "official"),
            _source("Memory Guardian Plugin", "https://gist.github.com/joe-rlo/3c3193285804b05c99bbfe541ed53c4d", "third_party"),
        ],
    ),
    "skill_manifest": _entry(
        identifier="skill_manifest",
        title="SKILL.md",
        category="skill",
        summary="Manifest and instruction entrypoint for an OpenClaw skill.",
        purpose="Declares the skill, describes what it does, and provides the instructions the agent should follow when the skill is invoked.",
        openclaw_use="OpenClaw skills are directories whose standard entrypoint is SKILL.md. Skills can come from bundled installs, ~/.openclaw/skills, or <workspace>/skills, with workspace skills taking precedence.",
        location="Skill folder: skills/<skill-name>/SKILL.md",
        note="SKILL.md is the portable contract for a skill; sibling files are usually support assets or implementation details.",
        field_notes=[
            "Official docs define precedence and load-time gating, including required binaries, OS gating, and config-based activation.",
            "nix-openclaw packaging guidance reinforces the same idea: plugins bundle CLI tools plus skill folders, and the SKILL.md teaches the AI how to use them.",
        ],
        cautions=[
            "Official docs explicitly say to treat third-party skills as untrusted code and read them before enabling.",
            "Security research has identified SKILL.md prompt bloat and trojanized skill instructions as realistic attack vectors in production-like deployments.",
        ],
        sources=[
            _source("Skills Guide", "https://docs.openclaw.ai/skills", "official"),
            _source("Agent Workspace", "https://docs.openclaw.ai/setup/agent-workspace", "official"),
            _source("FAQ", "https://docs.openclaw.ai/help/faq", "official"),
            _source("nix-openclaw", "https://github.com/openclaw/nix-openclaw", "third_party", "Packaging ecosystem guidance for plugin and skill authoring."),
            _source("Clawdrain", "https://arxiv.org/abs/2603.00902", "research"),
        ],
    ),
    "openclaw_json": _entry(
        identifier="openclaw_json",
        title="openclaw.json",
        category="config",
        summary="Primary OpenClaw configuration file.",
        purpose="Holds instance-level Gateway, channel, model, skill, and runtime configuration outside the workspace content tree.",
        openclaw_use="The runtime docs point to ~/.openclaw/openclaw.json and recommend `openclaw setup` to create it. Official configuration docs and packaging guides treat this file as the central state/config entrypoint.",
        location="OpenClaw root: ~/.openclaw/openclaw.json",
        note="This is platform configuration, not workspace knowledge.",
        field_notes=[
            "The file is separate from the workspace so the agent's 'mind' and the platform's control-plane config are not the same thing.",
            "Official skills docs also route extra skill directories and skill overrides through openclaw.json.",
            "Community packaging workarounds show that serialization bugs or missing template assets often surface here first because this file is the bridge between install-time and runtime behavior.",
        ],
        cautions=[
            "Changes here affect the platform itself; treat it more like system configuration than like an editable chat note.",
            "Avoid storing secrets inline unless the specific deployment model expects it; official and ecosystem docs generally prefer token files or env injection.",
        ],
        sources=[
            _source("Agent Runtime", "https://docs.openclaw.ai/concepts/agent", "official"),
            _source("Configuration Reference", "https://docs.openclaw.ai/gateway/configuration-reference", "official"),
            _source("Skills Guide", "https://docs.openclaw.ai/skills", "official"),
            _source("nix-openclaw", "https://github.com/openclaw/nix-openclaw", "third_party"),
            _source("OpenClaw NixOS Workarounds", "https://gist.github.com/gudnuf/8fe65ca0e49087105cb86543dc8f0799", "third_party", "Packaging bugs and workarounds around generated JSON and template installation."),
        ],
    ),
}


def all_file_knowledge() -> dict[str, dict[str, object]]:
    return {key: dict(value) for key, value in FILE_KNOWLEDGE.items()}


def lookup_known_file_reference(logical_path: str, role: str, root_type: str) -> dict[str, object] | None:
    """Return official or curated OpenClaw file knowledge for well-known paths and roles."""
    normalized = _normalize_reference_path(logical_path)
    path = PurePosixPath(normalized or ".")
    basename = path.name
    parts = path.parts

    if normalized == "AGENTS.md" or role == "workspace_bootstrap_agents":
        return FILE_KNOWLEDGE["agents_md"]
    if normalized == "SOUL.md" or role == "workspace_bootstrap_soul":
        return FILE_KNOWLEDGE["soul_md"]
    if normalized == "TOOLS.md" or role == "workspace_bootstrap_tools":
        return FILE_KNOWLEDGE["tools_md"]
    if normalized == "USER.md" or role == "workspace_bootstrap_user":
        return FILE_KNOWLEDGE["user_md"]
    if normalized == "IDENTITY.md" or role == "workspace_bootstrap_identity":
        return FILE_KNOWLEDGE["identity_md"]
    if normalized == "HEARTBEAT.md" or role == "workspace_bootstrap_heartbeat":
        return FILE_KNOWLEDGE["heartbeat_md"]
    if normalized == "BOOTSTRAP.md":
        return FILE_KNOWLEDGE["bootstrap_md"]
    if normalized == "BOOT.md":
        return FILE_KNOWLEDGE["boot_md"]
    if basename.upper() == "MEMORY.MD" or role == "memory_longterm":
        return FILE_KNOWLEDGE["memory_md"]
    if role == "memory_daily" or (len(parts) == 2 and parts[0] == "memory" and re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", basename)):
        return FILE_KNOWLEDGE["memory_daily"]
    if (len(parts) >= 3 and parts[0] == "skills" and basename == "SKILL.md") or role == "skill_manifest":
        return FILE_KNOWLEDGE["skill_manifest"]
    if normalized == "openclaw.json" or (root_type == "openclaw" and basename == "openclaw.json"):
        return FILE_KNOWLEDGE["openclaw_json"]
    return None
# --- End inlined module: file_knowledge.py ---
