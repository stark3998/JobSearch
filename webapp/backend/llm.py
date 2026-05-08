"""LLM provider abstraction for resume generation using Claude or Microsoft Foundry."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
BASE_TEX = REPO_ROOT / "Base" / "cv.tex"

ARCHETYPE_LABELS = {
    "cloud_security": "Cloud Security Engineering",
    "security_architecture": "Security Architecture",
    "software_security": "Software Security Engineering",
    "cloud_devops": "Cloud DevOps / Platform Engineering",
}


def _read_system_prompt() -> str:
    if not CLAUDE_MD.exists():
        raise FileNotFoundError(f"CLAUDE.md not found at {CLAUDE_MD}")
    return CLAUDE_MD.read_text(encoding="utf-8")


def _read_base_template() -> str:
    if BASE_TEX.exists():
        return BASE_TEX.read_text(encoding="utf-8")
    return ""


def build_prompt(
    title: str,
    company: str,
    location: str,
    archetype: str,
    one_page: bool,
    analysis: str | None,
    description: str | None,
    matched_strong: str,
) -> tuple[str, str]:
    system = _read_system_prompt()
    base_tex = _read_base_template()
    archetype_display = ARCHETYPE_LABELS.get(archetype, archetype)
    page_format = "1-page (compact)" if one_page else "2-page (standard)"

    user = f"""Generate a tailored resume and cover letter for this job application.

## Job Details
- **Position:** {title}
- **Company:** {company}
- **Location:** {location}
- **Resume Archetype:** {archetype_display} ({archetype})
- **Format:** {page_format}
"""

    if analysis:
        user += f"\n## JD Analysis\n{analysis}\n"

    if description:
        desc_trimmed = description[:6000] if len(description) > 6000 else description
        user += f"\n## Job Description\n{desc_trimmed}\n"

    if matched_strong:
        user += f"\n## Strong Keyword Matches\n{matched_strong}\n"

    if base_tex:
        user += f"\n## Base LaTeX Template\nUse this EXACT preamble, header (name/contact), and education section. Do NOT modify packages, font settings, or the header block:\n\n```latex\n{base_tex}\n```\n"

    user += f"""
## Output Instructions

Generate TWO outputs using the EXACT delimiters shown below.

### 1. Complete LaTeX Resume
Follow ALL rules from the system prompt (CLAUDE.md):
- Use the EXACT preamble, header, and education from the base template above
- Tailor the Skills section per Section 8.5 for the "{archetype}" archetype
- Tailor Experience bullets per Sections 8.3 and 8.4 — mirror the JD's exact language and keywords
- 4 roles always: Deloitte US (title: Engineering Manager), ZS Associates, UCI Fellow, Deloitte India
- Bold technologies and metrics with \\textbf{{}}
- Include a quantitative metric on every bullet — use ONLY metrics from Section 10
- Use \\texorpdfstring wrapper on the Certifications section header with \\hfill
"""

    if one_page:
        user += """- **1-page format:** Insert tighter geometry after packages: \\geometry{scale=0.93, top=0.4cm, bottom=0.4cm}
- Reduced \\titlespacing{{\\section}}{{0pt}}{{2pt}}{{2pt}} and \\setlength{{\\parskip}}{{0pt}}
- Fewer bullets: 3 Deloitte US, 2 ZS, 1 UCI, 3 Deloitte India
- Show only 3 most relevant certifications
- Use itemsep=2pt
"""
    else:
        user += """- **2-page format:** Full bullets: 6 Deloitte US, 3 ZS, 3 UCI, 4-5 Deloitte India
- Show ALL 11 Microsoft certifications (archetype-relevant first, then remaining)
- Use itemsep=3pt
"""

    user += """
### 2. Cover Letter (Markdown)
Follow Section 8.8: hook → current role evidence → career depth → why this company.
Mirror JD language. Personalize "why this company." End with a concrete ask.

### Response Format
Use these EXACT delimiters — no other text outside them:

<RESUME_TEX>
[Complete LaTeX from \\documentclass to \\end{document}]
</RESUME_TEX>

<COVER_LETTER>
[Complete cover letter in markdown]
</COVER_LETTER>
"""

    return system, user


def parse_response(response: str) -> tuple[str, str]:
    tex_match = re.search(r"<RESUME_TEX>\s*(.*?)\s*</RESUME_TEX>", response, re.DOTALL)
    cl_match = re.search(r"<COVER_LETTER>\s*(.*?)\s*</COVER_LETTER>", response, re.DOTALL)

    if not tex_match:
        raise ValueError("LLM response did not contain a <RESUME_TEX> section")

    tex = tex_match.group(1).strip()
    tex = re.sub(r"^```(?:latex|tex)?\s*\n", "", tex)
    tex = re.sub(r"\n```\s*$", "", tex)
    tex = tex.replace("\x1b", "")

    cl = cl_match.group(1).strip() if cl_match else ""
    cl = re.sub(r"^```(?:markdown|md)?\s*\n", "", cl)
    cl = re.sub(r"\n```\s*$", "", cl)

    return tex, cl


def _call_claude(system: str, user: str) -> str:
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    client = anthropic.Anthropic(api_key=api_key)

    logger.info(f"Calling Claude ({model})...")
    response = client.messages.create(
        model=model,
        max_tokens=12000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def _call_foundry(system: str, user: str) -> str:
    from openai import AzureOpenAI

    endpoint = os.getenv("FOUNDRY_ENDPOINT")
    api_key = os.getenv("FOUNDRY_API_KEY")
    model = os.getenv("FOUNDRY_MODEL", "gpt-4o")
    api_version = os.getenv("FOUNDRY_API_VERSION", "2024-12-01-preview")

    if not endpoint:
        raise ValueError("FOUNDRY_ENDPOINT environment variable not set")
    if not api_key:
        raise ValueError("FOUNDRY_API_KEY environment variable not set")

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
    )

    logger.info(f"Calling Foundry ({model}) at {endpoint}...")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=12000,
    )
    return response.choices[0].message.content


def generate(provider: str, system: str, user: str) -> tuple[str, str]:
    """Call the specified provider and return (provider_used, raw_response)."""
    if provider == "claude":
        return "claude", _call_claude(system, user)

    if provider == "foundry":
        return "foundry", _call_foundry(system, user)

    if provider == "auto":
        try:
            return "claude", _call_claude(system, user)
        except Exception as e:
            logger.warning(f"Claude failed ({e}), falling back to Foundry")
            try:
                return "foundry", _call_foundry(system, user)
            except Exception as e2:
                raise ValueError(
                    f"Both providers failed. Claude: {e} | Foundry: {e2}"
                ) from e2

    raise ValueError(f"Unknown provider: {provider}")
