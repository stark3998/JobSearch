"""
Step 3: Generate structured JD analysis per job (CLAUDE.md Section 8.7).

Usage:
    python analyze_jobs.py                                # Analyze latest filtered set
    python analyze_jobs.py --input path/to/filtered.csv   # Specific file
    python analyze_jobs.py --tier shortlist                # Only shortlisted
    python analyze_jobs.py --limit 20                     # Cap analysis count
"""

import argparse
import logging
import re
import sys
import textwrap
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PIPELINE_DIR = Path(__file__).parent
REPO_ROOT = PIPELINE_DIR.parent

# Skills vocabulary from CLAUDE.md Section 4
SKILLS_VOCAB = {
    "cloud": [
        "azure", "aws", "gcp", "google cloud", "multi-cloud",
        "aks", "eks", "gke", "key vault", "entra id", "azure ad",
        "s3", "lambda", "ec2", "bigquery", "cosmos db", "redis cache",
        "app service", "function apps", "event hubs", "service bus",
        "log analytics", "vmss", "container instances", "sql server",
        "azure synapse", "azure data factory", "application gateway",
        "vnet", "waf", "azure monitor",
    ],
    "security": [
        "cspm", "cwpp", "ciem", "siem", "soar", "zero trust",
        "iam", "rbac", "abac", "oauth", "oauth 2.0", "oidc", "saml",
        "spiffe", "spire", "threat modeling", "penetration testing",
        "vulnerability management", "sast", "dast", "iast",
        "code review", "security architecture", "risk assessment",
        "encryption", "cryptography", "secrets management",
        "credential rotation", "identity lifecycle",
        "conditional access", "mfa", "sso", "api security",
        "network segmentation", "vpc", "firewall",
        "supply chain security", "workload identity",
        "red team", "red-teaming", "adversarial testing",
        "nist", "iso 27001", "csa", "cis benchmarks", "mcsb",
        "admission controllers", "pod security", "network policies",
        "sentinel", "defender for cloud", "purview",
    ],
    "devops_iac": [
        "terraform", "bicep", "ansible", "pulumi", "cloudformation",
        "docker", "kubernetes", "helm", "github actions", "ghas",
        "azure devops", "jenkins", "artifactory", "ci/cd",
        "github copilot", "argocd", "flux",
    ],
    "monitoring": [
        "sentinel", "defender for cloud", "dynatrace", "datadog",
        "grafana", "splunk", "elastic", "prometheus", "new relic",
        "azure monitor", "log analytics", "power bi",
    ],
    "languages": [
        "python", "go", "golang", "rust", "java", "c#", ".net",
        "javascript", "typescript", "powershell", "bash", "sql",
        "swift", "c++", "ruby",
    ],
    "data": [
        "databricks", "apache spark", "pyspark", "delta lake",
        "unity catalog", "pandas", "numpy",
    ],
}

# User's skills (from CLAUDE.md Section 4)
USER_SKILLS = set()
for category_skills in SKILLS_VOCAB.values():
    USER_SKILLS.update(s.lower() for s in category_skills)
USER_SKILLS.update([
    "python", "c#", "asp.net", "powershell", "bash", "sql", "java",
    "javascript", "swift", "yaml", "html", "azure", "aws", "gcp",
    "kubernetes", "docker", "terraform", "bicep", "github actions",
    "ghas", "azure devops", "jenkins", "artifactory",
    "sentinel", "defender for cloud", "purview", "databricks",
    "power bi", "postman", "pyspark", "pandas", "nltk", "django",
    "oidc", "oauth 2.0", "saml", "rbac", "iam", "zero trust",
    "threat modeling", "cspm", "cwpp", "ciem", "sast", "dast",
    "secrets management", "workload identity",
    "entra id", "key vault", "aks", "cosmos db", "redis cache",
    "grafana", "datadog", "dynatrace",
])

ARCHETYPE_KEYWORDS = {
    "cloud_security": [
        "cspm", "cwpp", "ciem", "siem", "sentinel", "iam", "rbac",
        "zero trust", "network segmentation", "iac", "misconfiguration",
        "cloud security posture", "compliance", "remediation",
    ],
    "security_architecture": [
        "threat modeling", "security architecture", "reference architecture",
        "design review", "security design", "nist", "iso 27001",
        "risk assessment", "framework", "governance", "advisory",
        "consultative", "strategy",
    ],
    "software_security": [
        "workload identity", "oidc", "oauth", "kubernetes security",
        "supply chain", "sast", "dast", "code review",
        "secure development", "security tooling", "python",
        "ci/cd security", "admission controller", "pod security",
    ],
    "cloud_devops": [
        "terraform", "iac", "github actions", "ci/cd", "sre",
        "site reliability", "platform", "cost optimization",
        "sla", "monitoring", "grafana", "datadog", "dynatrace",
        "agile", "scrum", "artifactory",
    ],
}

ARCHETYPE_DISPLAY = {
    "cloud_security": "Cloud Security Engineering",
    "security_architecture": "Security Architecture",
    "software_security": "Software Security Engineering",
    "cloud_devops": "Cloud DevOps / Platform Engineering",
}

SKILLS_TEMPLATE_MAP = {
    "cloud_security": "Cloud Security Engineering (CLAUDE.md Section 8.5)",
    "security_architecture": "Security Architecture (CLAUDE.md Section 8.5)",
    "software_security": "Software Security Engineering (CLAUDE.md Section 8.5)",
    "cloud_devops": "Cloud DevOps (CLAUDE.md Section 8.5)",
}

CERT_MAP = {
    "cloud_security": [
        "AZ-500 (Azure Security Engineer Associate)",
        "AZ-304 (Azure Solutions Architect Expert)",
        "AZ-400 (DevOps Engineer Expert)",
        "AZ-700 (Azure Network Engineer Associate)",
        "DP-203 (Azure Data Engineer Associate)",
    ],
    "security_architecture": [
        "AZ-500 (Azure Security Engineer Associate)",
        "AZ-304 (Azure Solutions Architect Expert)",
        "AZ-400 (DevOps Engineer Expert)",
        "AZ-204 (Azure Developer Associate)",
        "AI-900 (Azure AI Fundamentals)",
    ],
    "software_security": [
        "AZ-500 (Azure Security Engineer Associate)",
        "AZ-304 (Azure Solutions Architect Expert)",
        "AZ-400 (DevOps Engineer Expert)",
        "AZ-204 (Azure Developer Associate)",
        "AZ-700 (Azure Network Engineer Associate)",
    ],
    "cloud_devops": [
        "AZ-304 (Azure Solutions Architect Expert)",
        "AZ-400 (DevOps Engineer Expert)",
        "AZ-500 (Azure Security Engineer Associate)",
        "AZ-700 (Azure Network Engineer Associate)",
        "DP-203 (Azure Data Engineer Associate)",
    ],
}


def load_config(config_path=None):
    path = config_path or PIPELINE_DIR / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def find_latest_file(directory, prefix):
    files = sorted(Path(directory).glob(f"{prefix}*.csv"), reverse=True)
    return files[0] if files else None


def slugify(text):
    if not text or pd.isna(text):
        return "unknown"
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text[:50].strip("-")


def extract_top_keywords(description, n=10):
    if not description or pd.isna(description):
        return []
    desc_lower = str(description).lower()
    found = {}
    all_skills = []
    for category_skills in SKILLS_VOCAB.values():
        all_skills.extend(category_skills)

    for skill in set(all_skills):
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        count = len(re.findall(pattern, desc_lower))
        if count > 0:
            found[skill] = count

    sorted_skills = sorted(found.items(), key=lambda x: -x[1])
    return sorted_skills[:n]


def classify_archetype(description, search_archetype):
    if not description or pd.isna(description):
        return search_archetype or "software_security", "low"

    desc_lower = str(description).lower()
    scores = {}
    for arch_key, keywords in ARCHETYPE_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", desc_lower):
                score += 1
        scores[arch_key] = score

    best = max(scores, key=scores.get)
    best_score = scores[best]

    if best_score == 0:
        return search_archetype or "software_security", "low"

    second_best = sorted(scores.values(), reverse=True)[1]
    if best_score - second_best >= 3:
        confidence = "high"
    elif best_score - second_best >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    if search_archetype and search_archetype != best:
        if scores.get(search_archetype, 0) >= best_score - 1:
            return search_archetype, confidence

    return best, confidence


def detect_cloud_platform(description):
    if not description or pd.isna(description):
        return "Unknown", {"Azure": 0, "AWS": 0, "GCP": 0}
    desc = str(description)
    counts = {
        "Azure": len(re.findall(r"\bazure\b", desc, re.I)),
        "AWS": len(re.findall(r"\baws\b|\bamazon web services\b", desc, re.I)),
        "GCP": len(re.findall(r"\bgcp\b|\bgoogle cloud\b", desc, re.I)),
    }
    total = sum(counts.values())
    if total == 0:
        return "Not specified", counts

    primary = max(counts, key=counts.get)
    if counts[primary] == 0:
        return "Not specified", counts

    non_zero = [k for k, v in counts.items() if v > 0]
    if len(non_zero) >= 2:
        top_val = counts[primary]
        second_val = sorted(counts.values(), reverse=True)[1]
        if second_val >= top_val * 0.5:
            return "Multi-cloud", counts

    return primary, counts


def extract_tools(description):
    if not description or pd.isna(description):
        return {}
    desc_lower = str(description).lower()
    result = {}
    for category, tools in SKILLS_VOCAB.items():
        found = []
        for tool in tools:
            if re.search(r"\b" + re.escape(tool.lower()) + r"\b", desc_lower):
                found.append(tool)
        if found:
            result[category] = found
    return result


def detect_tone(description, title):
    if not description or pd.isna(description):
        return "Unknown"
    desc_lower = str(description).lower()
    title_lower = str(title or "").lower()
    combined = f"{title_lower} {desc_lower}"

    builder_signals = [
        "build", "develop", "implement", "ship", "code",
        "engineer", "write", "create", "deliver",
    ]
    architect_signals = [
        "design", "architect", "review", "advise", "strategy",
        "framework", "governance", "guide", "mentor", "consult",
    ]
    operator_signals = [
        "maintain", "monitor", "operate", "support", "troubleshoot",
        "sla", "incident", "on-call", "oncall", "optimize", "cost",
    ]

    scores = {
        "Builder/Executor": sum(
            1 for w in builder_signals
            if re.search(r"\b" + w + r"\b", combined)
        ),
        "Architect/Advisor": sum(
            1 for w in architect_signals
            if re.search(r"\b" + w + r"\b", combined)
        ),
        "DevOps/Operator": sum(
            1 for w in operator_signals
            if re.search(r"\b" + w + r"\b", combined)
        ),
    }
    return max(scores, key=scores.get)


def find_gaps(top_keywords):
    gaps = []
    for skill, count in top_keywords:
        if skill.lower() not in USER_SKILLS:
            gaps.append(skill)
    return gaps


def get_summary_sentences(description, max_sentences=3):
    if not description or pd.isna(description):
        return "No description available."
    text = str(description)
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"[#*_`]", "", text)
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    return " ".join(sentences[:max_sentences]) if sentences else text[:300]


def get_bullet_suggestions(archetype):
    suggestions = {
        "cloud_security": {
            "deloitte_us": "CSPM/CWPP, SIEM (Sentinel), IAM/RBAC overhaul, IaC guardrails, multi-cloud assessment",
            "zs": "Docker hardening, Unity Catalog RBAC, security misconfig remediation",
            "uci": "Hybrid identity infrastructure, credential rotation, threat modeling",
            "deloitte_india": "Automated M365 security assessment tool, Zero Trust, IaC scanning extension",
        },
        "security_architecture": {
            "deloitte_us": "Threat modeling, architecture review, reference designs, mentoring, security frameworks",
            "zs": "Data security architecture review, access control gap analysis",
            "uci": "Hybrid identity architecture, authentication flow debugging, threat modeling",
            "deloitte_india": "Zero Trust architecture, secure design patterns, governance frameworks",
        },
        "software_security": {
            "deloitte_us": "MCP server OIDC/workload identity, K8s security controls, CI/CD supply chain hardening, Python security tooling",
            "zs": "Hardened Docker image, Unity Catalog fine-grained RBAC, cloud misconfig remediation",
            "uci": "Hybrid workload identity (OIDC federation), threat modeling, token replay fix",
            "deloitte_india": "Multi-cloud security assessment tool (Python), IaC scanning, K8s IAM overhaul, OAuth/SAML patterns",
        },
        "cloud_devops": {
            "deloitte_us": "IaC guardrails (Terraform), CI/CD pipeline design, GitHub Actions/GHAS, AKS platform engineering",
            "zs": "Delta Lake ETL overhaul (Spark/Databricks), custom Docker image, Grafana dashboards",
            "uci": "Hybrid infrastructure engineering (F5, DNS, Application Proxy)",
            "deloitte_india": "Azure DevOps IaC scanning extension, ETL workflows (Synapse/SQL), platform solutions",
        },
    }
    return suggestions.get(archetype, suggestions["software_security"])


GAP_MITIGATIONS = {
    "go": "Mention C++ from SwiftNet/IoT and Python systems tooling as proxy; note willingness to learn",
    "golang": "Mention C++ from SwiftNet/IoT and Python systems tooling as proxy; note willingness to learn",
    "rust": "Highlight C++ experience from SwiftNet; frame as quick ramp-up given systems background",
    "cissp": "Lean on 11 Microsoft certifications as equivalency; mention pursuit if applicable",
    "splunk": "Frame Microsoft Sentinel experience as direct equivalent; both are SIEM platforms",
    "elastic": "Frame Sentinel/Log Analytics as equivalent SIEM/log analysis experience",
    "gke": "AKS experience transfers directly; mention GCP GKE familiarity from Costco prep",
    "cloudformation": "Terraform and Bicep expertise transfers directly; all are declarative IaC",
    "ansible": "Terraform expertise covers IaC; PowerShell/Bash cover configuration management",
    "new relic": "Dynatrace, Grafana, Datadog experience covers APM/observability domain",
}


def generate_analysis(row, config):
    title = str(row.get("title", "Unknown"))
    company = str(row.get("company", "Unknown"))
    description = str(row.get("description", ""))
    job_url = str(row.get("job_url", ""))
    date_posted = str(row.get("date_posted", ""))
    is_remote = row.get("is_remote", False)
    min_amount = row.get("min_amount", "")
    max_amount = row.get("max_amount", "")
    currency = row.get("currency", "USD")
    city = row.get("city", "")
    state = row.get("state", "")
    score = row.get("relevance_score", 0)
    tier = row.get("tier", "")
    found_on = row.get("found_on_boards", "")
    search_arch = row.get("search_archetype", "")
    matched_strong = row.get("matched_strong", "")
    matched_moderate = row.get("matched_moderate", "")
    matched_negative = row.get("matched_negative", "")

    location_str = ", ".join(filter(None, [str(city) if pd.notna(city) else "", str(state) if pd.notna(state) else ""]))
    if not location_str or location_str == ", ":
        location_str = "Not specified"

    salary_str = ""
    if pd.notna(min_amount) and pd.notna(max_amount) and min_amount and max_amount:
        salary_str = f"${int(float(min_amount)):,} - ${int(float(max_amount)):,} {currency if pd.notna(currency) else 'USD'}"
    elif pd.notna(max_amount) and max_amount:
        salary_str = f"Up to ${int(float(max_amount)):,}"
    else:
        salary_str = "Not listed"

    top_keywords = extract_top_keywords(description)
    archetype, arch_confidence = classify_archetype(description, search_arch)
    primary_cloud, cloud_counts = detect_cloud_platform(description)
    tools = extract_tools(description)
    tone = detect_tone(description, title)
    gaps = find_gaps(top_keywords)
    summary = get_summary_sentences(description)
    bullet_suggestions = get_bullet_suggestions(archetype)
    company_slug = slugify(company)

    kw_lines = []
    for i, (skill, count) in enumerate(top_keywords, 1):
        status = "MATCHED" if skill.lower() in USER_SKILLS else "GAP"
        kw_lines.append(f"{i}. **{skill}** (mentioned {count}x) -- {status}")
    matched_count = sum(1 for s, _ in top_keywords if s.lower() in USER_SKILLS)
    gap_list = [s for s, _ in top_keywords if s.lower() not in USER_SKILLS]

    tools_table = ""
    category_labels = {
        "cloud": "Cloud",
        "security": "Security",
        "devops_iac": "DevOps/IaC",
        "monitoring": "Monitoring",
        "languages": "Languages",
        "data": "Data",
    }
    for cat_key, cat_label in category_labels.items():
        if cat_key in tools:
            tools_table += f"| {cat_label} | {', '.join(tools[cat_key])} |\n"

    gap_table = ""
    for gap in gaps:
        mitigation = GAP_MITIGATIONS.get(
            gap.lower(),
            "Address in cover letter; highlight adjacent experience"
        )
        gap_table += f"| {gap} | {mitigation} |\n"

    certs = CERT_MAP.get(archetype, CERT_MAP["software_security"])
    certs_lines = "\n".join(f"- {c}" for c in certs)

    md = f"""# JD Analysis: {title} at {company}

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
**Source:** {job_url}
**Board(s):** {found_on}
**Date Posted:** {date_posted}
**Location:** {location_str} | Remote: {"Yes" if is_remote else "No"}
**Salary:** {salary_str}
**Relevance Score:** {score} (Tier: {tier})

---

## 1. JD Summary

{summary}

## 2. Top 10 Required Skills/Keywords

{chr(10).join(kw_lines) if kw_lines else "No keywords extracted (description may be empty)"}

**Matched:** {matched_count}/{len(top_keywords)} | **Gaps:** {', '.join(gap_list) if gap_list else 'None'}

## 3. Role Archetype

**Classification:** {ARCHETYPE_DISPLAY.get(archetype, archetype)}
**Confidence:** {arch_confidence}
**CLAUDE.md Section:** 8.3 -> {ARCHETYPE_DISPLAY.get(archetype, archetype)}

## 4. Primary Cloud Platform

**Primary:** {primary_cloud}
**Mentions:** Azure ({cloud_counts['Azure']}), AWS ({cloud_counts['AWS']}), GCP ({cloud_counts['GCP']})

## 5. Specific Tools & Technologies Named in JD

| Category | Tools |
|----------|-------|
{tools_table if tools_table else "| - | No specific tools detected |"}

## 6. Suggested CLAUDE.md Skills Template

Use: **{SKILLS_TEMPLATE_MAP.get(archetype, "Software Security Engineering")}**

## 7. Suggested Certifications (4-5 from Section 8.6)

{certs_lines}

## 8. Tone & Framing

**JD Tone:** {tone}
**Suggested Framing:**
- Deloitte US bullets -> emphasize {bullet_suggestions['deloitte_us']}
- ZS bullets -> emphasize {bullet_suggestions['zs']}
- UCI bullets -> emphasize {bullet_suggestions['uci']}
- Deloitte India bullets -> emphasize {bullet_suggestions['deloitte_india']}

## 9. Cover Letter Talking Points

- **Hook:** Reference the specific role at {company} and mirror JD language
- **Evidence 1:** Deloitte US -- most relevant accomplishment for this archetype
- **Evidence 2:** Choose from ZS/UCI/Deloitte India based on archetype fit
- **Why {company}:** Research company mission/tech stack for personalized angle

## 10. Gaps & Risks

| Gap | Mitigation |
|-----|-----------|
{gap_table if gap_table else "| None detected | Strong profile match |"}

## 11. Matched Keywords Detail

**Strong matches:** {matched_strong if matched_strong else 'N/A'}
**Moderate matches:** {matched_moderate if matched_moderate else 'N/A'}
**Negative flags:** {matched_negative if matched_negative else 'None'}

---

## Next Step

To generate a tailored resume for this role, run:

```
claude "Read CLAUDE.md and pipeline_output/analyses/{company_slug}_{slugify(title)}.md. Generate Resumes/cv_{company_slug}.tex following Section 8 instructions. Also generate CoverLetters/coverletter_{company_slug}.md."
```
"""
    return md.strip()


def generate_summary(df, analysis_paths, config, errors=None):
    output_path = REPO_ROOT / config["output"]["summary_file"]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = len(df)
    shortlisted = df[df["tier"] == "shortlist"] if "tier" in df.columns else pd.DataFrame()
    considered = df[df["tier"] == "consider"] if "tier" in df.columns else pd.DataFrame()

    top_jobs = shortlisted.head(10) if not shortlisted.empty else df.head(10)

    table_rows = []
    for i, (_, row) in enumerate(top_jobs.iterrows(), 1):
        score = row.get("relevance_score", 0)
        company = str(row.get("company", "?"))[:25]
        title = str(row.get("title", "?"))[:40]
        city = str(row.get("city", "")) if pd.notna(row.get("city")) else ""
        state = str(row.get("state", "")) if pd.notna(row.get("state")) else ""
        loc = ", ".join(filter(None, [city, state])) or "?"
        remote = "Yes" if row.get("is_remote") else "No"
        sal_min = row.get("min_amount", "")
        sal_max = row.get("max_amount", "")
        salary = ""
        if pd.notna(sal_max) and sal_max:
            salary = f"${int(float(sal_max)):,}"
        arch = str(row.get("search_archetype", ""))
        url = str(row.get("job_url", ""))
        table_rows.append(
            f"| {i} | {score} | {company} | {title} | {loc} | "
            f"{remote} | {salary} | {arch} | [Apply]({url}) |"
        )

    arch_counts = ""
    if "search_archetype" in shortlisted.columns:
        for arch, count in shortlisted["search_archetype"].value_counts().items():
            display = ARCHETYPE_DISPLAY.get(arch, arch)
            arch_counts += f"- {display}: {count} jobs\n"

    table = "\n".join(table_rows)

    error_section = ""
    if errors:
        error_lines = "\n".join(
            f"- [{e['board']}] {e['archetype']} @ {e['location']}: {e['error']}"
            for e in errors[:10]
        )
        error_section = f"\n## Errors\n\n{error_lines}\n"

    md = f"""# Job Search Pipeline Run -- {datetime.now().strftime("%Y-%m-%d")}

## Run Stats

- **Total filtered jobs:** {total}
- **Shortlisted (score >= {config['thresholds']['shortlist_min_score']}):** {len(shortlisted)}
- **Consider (score >= {config['thresholds']['consider_min_score']}):** {len(considered)}
- **Analyses generated:** {len(analysis_paths)} files

## Top Shortlisted Jobs

| # | Score | Company | Title | Location | Remote | Salary | Archetype | Link |
|---|-------|---------|-------|----------|--------|--------|-----------|------|
{table}

## Shortlisted by Archetype

{arch_counts if arch_counts else "No shortlisted jobs in this run."}

## Next Steps

For each job you want to apply to, run:

```
claude "Read CLAUDE.md and pipeline_output/analyses/FILENAME.md. Generate Resumes/cv_COMPANY.tex following Section 8 instructions."
```
{error_section}
---

*Generated by JobSpy Pipeline on {datetime.now().strftime("%Y-%m-%d %H:%M")}*
"""

    output_path.write_text(md.strip(), encoding="utf-8")
    logger.info(f"Summary written to {output_path}")


def run_analyzer(df, config, tier_filter=None, limit=None, errors=None):
    if tier_filter:
        tiers = tier_filter if isinstance(tier_filter, list) else [tier_filter]
        df = df[df["tier"].isin(tiers)].copy()
    else:
        df = df[df["tier"].isin(["shortlist", "consider"])].copy()

    if limit:
        df = df.head(limit)

    if df.empty:
        logger.warning("No jobs to analyze after filtering.")
        generate_summary(df, [], config, errors)
        return []

    output_dir = REPO_ROOT / config["output"]["analysis_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    analyses = []
    for _, row in df.iterrows():
        try:
            analysis = generate_analysis(row, config)
            company_slug = slugify(row.get("company", "unknown"))
            title_slug = slugify(row.get("title", "unknown"))
            filename = f"{company_slug}_{title_slug}.md"
            filepath = output_dir / filename
            filepath.write_text(analysis, encoding="utf-8")
            analyses.append(filepath)
        except Exception as e:
            logger.warning(
                f"Failed to analyze {row.get('company', '?')} / "
                f"{row.get('title', '?')}: {e}"
            )

    generate_summary(df, analyses, config, errors)
    logger.info(f"Generated {len(analyses)} analysis files in {output_dir}")
    return analyses


def main():
    parser = argparse.ArgumentParser(
        description="Generate structured JD analysis per job"
    )
    parser.add_argument("--config", help="Path to config.yaml")
    parser.add_argument("--input", help="Path to filtered CSV")
    parser.add_argument(
        "--tier",
        default="shortlist,consider",
        help="Comma-separated tiers to analyze",
    )
    parser.add_argument("--limit", type=int, help="Max jobs to analyze")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.input:
        input_path = Path(args.input)
    else:
        filtered_dir = REPO_ROOT / config["output"]["filtered_dir"]
        input_path = find_latest_file(filtered_dir, "filtered_")

    if not input_path or not input_path.exists():
        logger.error("No filtered file found. Run filter_jobs.py first.")
        return []

    logger.info(f"Loading {input_path}")
    df = pd.read_csv(input_path)
    tiers = [t.strip() for t in args.tier.split(",")]
    return run_analyzer(df, config, tier_filter=tiers, limit=args.limit)


if __name__ == "__main__":
    main()
