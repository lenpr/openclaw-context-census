from __future__ import annotations

import importlib.util
import os
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "content_census_report.py"
REFERENCE_TIME = datetime(2026, 3, 15, tzinfo=UTC)


@lru_cache(maxsize=1)
def load_content_census_module():
    spec = importlib.util.spec_from_file_location("content_census_report_module", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module spec for {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_fixture_tree(root: Path) -> Path:
    openclaw_root = root / ".openclaw"
    workspace = openclaw_root / "workspace"

    (workspace / "memory").mkdir(parents=True)
    (workspace / "skills" / "find-skills" / "hooks" / "openclaw").mkdir(parents=True)
    (workspace / "tools" / "whisper.cpp" / "models").mkdir(parents=True)
    (workspace / "ops" / "chat-icons").mkdir(parents=True)
    (openclaw_root / "agents" / "main" / "sessions").mkdir(parents=True)
    (openclaw_root / "credentials").mkdir(parents=True)
    (openclaw_root / "cron" / "runs").mkdir(parents=True)

    _write_text(workspace / "AGENTS.md", "# agents\n")
    _write_text(workspace / "SOUL.md", "# soul\n")
    _write_text(workspace / "memory" / "2026-03-14.md", "# 2026-03-14\n- note\n")
    _write_text(workspace / "skills" / "find-skills" / "SKILL.md", "# skill\n")
    _write_text(workspace / "skills" / "find-skills" / "hooks" / "openclaw" / "HOOK.md", "# hook\n")
    _write_text(workspace / "package-lock.json", '{\n  "lockfileVersion": 3\n}\n')
    _write_bytes(workspace / "ops" / "chat-icons" / "bot-assistant-inbox.png", b"\x89PNG\r\n\x1a\nfixture")
    _write_bytes(workspace / "tools" / "whisper.cpp" / "models" / "ggml-base.bin", b"x" * (80 * 1024))
    _write_text(openclaw_root / "agents" / "main" / "sessions" / "sessions.json", '{"sessions":[]}\n')
    _write_text(openclaw_root / "agents" / "main" / "sessions" / "abc.jsonl", '{"event":1}\n')
    _write_text(openclaw_root / "credentials" / "openai.key", "token\n")
    _write_text(openclaw_root / "cron" / "runs" / "run-1.jsonl", '{"run":1}\n')
    _write_text(openclaw_root / "openclaw.json", '{\n  "model": "gpt-test"\n}\n')

    _set_mtime(workspace / "memory" / "2026-03-14.md", datetime(2026, 3, 14, tzinfo=UTC))
    _set_mtime(workspace / "skills" / "find-skills" / "SKILL.md", datetime(2026, 3, 12, tzinfo=UTC))
    _set_mtime(workspace / "tools" / "whisper.cpp" / "models" / "ggml-base.bin", datetime(2025, 12, 31, tzinfo=UTC))
    _set_mtime(openclaw_root / "credentials" / "openai.key", datetime(2026, 3, 10, tzinfo=UTC))
    _set_mtime(openclaw_root / "openclaw.json", datetime(2026, 3, 13, tzinfo=UTC))

    return workspace


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _write_bytes(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def _set_mtime(path: Path, value: datetime) -> None:
    timestamp = value.timestamp()
    os.utime(path, (timestamp, timestamp))
