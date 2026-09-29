"""Агент рекламы собран целиком и ничего лишнего с собой не несёт."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".claude" / "skills"

TEAM_SKILLS = {
    "ads-agent", "fb-api", "account-onboarding", "creative-analyzer",
    "targeting-expert", "creative-copywriter", "campaign-manager", "naming-rules",
}


def test_all_skills_present() -> None:
    have = {p.name for p in SKILLS.iterdir() if (p / "SKILL.md").exists()}
    assert TEAM_SKILLS <= have, f"нет скиллов: {sorted(TEAM_SKILLS - have)}"


def test_skills_have_frontmatter() -> None:
    for name in TEAM_SKILLS:
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---") and "description:" in text.split("---")[1], name


def test_every_mcp_call_is_mapped() -> None:
    """Каждый MCP-вызов, который встречается в скиллах запуска, есть в таблице fb-api."""
    mapping = (SKILLS / "fb-api" / "SKILL.md").read_text(encoding="utf-8")
    table = mapping[mapping.index("## Инструменты MCP → вызовы API"):]
    used = set()
    for name in ("campaign-manager", "targeting-expert", "account-onboarding"):
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        used |= set(re.findall(r"\b(search_interests|search_geo_locations|estimate_audience_size|"
                               r"create_campaign|create_adset|create_ad_creative|create_ad|"
                               r"upload_ad_image|upload_video|resume_adset|resume_campaign)\(", text))
    missing = [u for u in used if u not in table]
    assert not missing, f"вызовы без соответствия в fb-api: {missing}"


def test_knowledge_the_skills_rely_on() -> None:
    for rel in ("config/knowledge/safety_rules.md", "config/knowledge/troubleshooting.md",
                "config/naming_convention.md", "config/creatives.md", "config/briefs/_template.md",
                "config/ad_accounts.md"):
        assert (ROOT / rel).is_file(), f"нет {rel}"


def test_state_template_matches_office() -> None:
    """Порядок субагентов в заготовке совпадает с рассадкой офиса."""
    sys.path.insert(0, str(SKILLS / "ads-agent"))
    import ofis  # noqa: E402

    state = json.loads((SKILLS / "ads-agent" / "state.example.json").read_text(encoding="utf-8"))
    names = [m["name"] for m in state["team"]]
    assert names == [c[0] for c in ofis.CREW], "порядок субагентов разошёлся с офисом"
    assert len(state["steps"]) == len(state["team"]), "этапов должно быть столько же, сколько субагентов"


def test_screen_builds_from_template(tmp_path: Path) -> None:
    """Экран собирается из пустой заготовки — это первое, что агент делает в прогоне."""
    import shutil
    work = tmp_path / "agent"
    shutil.copytree(ROOT / ".claude", work / ".claude")
    shutil.copytree(ROOT / "assets", work / "assets")
    (work / "build").mkdir()
    shutil.copy(SKILLS / "ads-agent" / "state.example.json", work / "build" / "state.json")
    out = subprocess.run([sys.executable, str(work / ".claude/skills/ads-agent/artifact.py")],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert (work / "build" / "Экран.html").stat().st_size > 10_000


SECRETS = (
    re.compile(r"EAA[A-Za-z0-9]{20,}"),
    re.compile(r"act_\d{8,}"),
    re.compile(r"(APP_SECRET|ACCESS_TOKEN)\s*=\s*[A-Za-z0-9]{16,}"),
)


def test_no_real_accounts_or_keys() -> None:
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".json", ".txt", ".py", ".example"}:
            continue
        if path.name == ".env" or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pat in SECRETS:
            assert not pat.search(text), f"похоже на реальный кабинет или ключ: {path.relative_to(ROOT)}"
