from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from ..models import DashboardStats, Job, JobsResponse

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

REPO_ROOT = Path(__file__).resolve().parents[3]
FILTERED_DIR = REPO_ROOT / "pipeline_output" / "filtered"
ANALYSIS_DIR = REPO_ROOT / "pipeline_output" / "analyses"

ARCHETYPE_DISPLAY = {
    "cloud_security": "Cloud Security Engineering",
    "security_architecture": "Security Architecture",
    "software_security": "Software Security Engineering",
    "cloud_devops": "Cloud DevOps / Platform Engineering",
}


def _find_latest_csv(directory: Path, prefix: str) -> Optional[Path]:
    files = sorted(directory.glob(f"{prefix}*.csv"), reverse=True)
    return files[0] if files else None


def _load_jobs() -> pd.DataFrame:
    latest = _find_latest_csv(FILTERED_DIR, "filtered_")
    if not latest or not latest.exists():
        return pd.DataFrame()
    df = pd.read_csv(latest)
    df = df.reset_index(drop=True)
    df["id"] = df.index
    return df


def _job_has_analysis(company: str, title: str) -> tuple[bool, Optional[str]]:
    if not ANALYSIS_DIR.exists():
        return False, None
    import re
    def slugify(text):
        if not text or pd.isna(text):
            return "unknown"
        text = str(text).lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        return text[:50].strip("-")

    filename = f"{slugify(company)}_{slugify(title)}.md"
    filepath = ANALYSIS_DIR / filename
    if filepath.exists():
        return True, filename
    for f in ANALYSIS_DIR.glob("*.md"):
        if f.name != "summary.md" and slugify(company) in f.name:
            return True, f.name
    return False, None


def _row_to_job(row, idx: int) -> Job:
    city = str(row.get("city", "")) if pd.notna(row.get("city")) else ""
    state = str(row.get("state", "")) if pd.notna(row.get("state")) else ""
    location = ", ".join(filter(None, [city, state])) or "Not specified"

    min_amt = row.get("min_amount")
    max_amt = row.get("max_amount")
    currency = row.get("currency", "USD")
    salary = None
    if pd.notna(max_amt) and max_amt:
        if pd.notna(min_amt) and min_amt:
            salary = f"${int(float(min_amt)):,} - ${int(float(max_amt)):,}"
        else:
            salary = f"Up to ${int(float(max_amt)):,}"

    company = str(row.get("company", "Unknown"))
    title = str(row.get("title", "Unknown"))
    has_analysis, analysis_file = _job_has_analysis(company, title)

    return Job(
        id=idx,
        title=title,
        company=company,
        location=location,
        city=city,
        state=state,
        is_remote=bool(row.get("is_remote", False)),
        job_url=str(row.get("job_url", "")),
        date_posted=str(row.get("date_posted", "")) if pd.notna(row.get("date_posted")) else None,
        salary=salary,
        min_amount=float(min_amt) if pd.notna(min_amt) else None,
        max_amount=float(max_amt) if pd.notna(max_amt) else None,
        currency=str(currency) if pd.notna(currency) else "USD",
        description=str(row.get("description", ""))[:500] if pd.notna(row.get("description")) else None,
        relevance_score=int(row.get("relevance_score", 0)),
        tier=str(row.get("tier", "")) if pd.notna(row.get("tier")) else None,
        search_archetype=str(row.get("search_archetype", "")) if pd.notna(row.get("search_archetype")) else None,
        source_board=str(row.get("source_board", "")) if pd.notna(row.get("source_board")) else None,
        found_on_boards=str(row.get("found_on_boards", "")) if pd.notna(row.get("found_on_boards")) else None,
        matched_strong=str(row.get("matched_strong", "")) if pd.notna(row.get("matched_strong")) else None,
        matched_moderate=str(row.get("matched_moderate", "")) if pd.notna(row.get("matched_moderate")) else None,
        matched_negative=str(row.get("matched_negative", "")) if pd.notna(row.get("matched_negative")) else None,
        salary_flag=str(row.get("salary_flag", "")) if pd.notna(row.get("salary_flag")) else None,
        has_analysis=has_analysis,
        analysis_file=analysis_file,
    )


@router.get("", response_model=JobsResponse)
def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    tier: Optional[str] = None,
    archetype: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = Query("relevance_score", pattern="^(relevance_score|company|title|date_posted)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    is_remote: Optional[bool] = None,
    min_score: Optional[int] = None,
    board: Optional[str] = None,
):
    df = _load_jobs()
    if df.empty:
        return JobsResponse(jobs=[], total=0, page=1, per_page=per_page, total_pages=0)

    if tier:
        tiers = [t.strip() for t in tier.split(",")]
        df = df[df["tier"].isin(tiers)]
    if archetype:
        df = df[df["search_archetype"] == archetype]
    if board:
        df = df[df["source_board"] == board]
    if is_remote is not None:
        df = df[df["is_remote"] == is_remote]
    if min_score is not None:
        df = df[df["relevance_score"] >= min_score]
    if search:
        q = search.lower()
        mask = (
            df["title"].str.lower().str.contains(q, na=False)
            | df["company"].str.lower().str.contains(q, na=False)
            | df.get("description", pd.Series(dtype=str)).str.lower().str.contains(q, na=False)
        )
        df = df[mask]

    ascending = sort_order == "asc"
    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=ascending, na_position="last")

    total = len(df)
    total_pages = max(1, math.ceil(total / per_page))
    start = (page - 1) * per_page
    end = start + per_page
    page_df = df.iloc[start:end]

    jobs = [_row_to_job(row, row.get("id", idx)) for idx, (_, row) in enumerate(page_df.iterrows(), start)]

    return JobsResponse(
        jobs=jobs, total=total, page=page, per_page=per_page, total_pages=total_pages
    )


@router.get("/stats", response_model=DashboardStats)
def get_stats():
    df = _load_jobs()
    if df.empty:
        return DashboardStats()

    shortlisted = len(df[df["tier"] == "shortlist"]) if "tier" in df.columns else 0
    consider = len(df[df["tier"] == "consider"]) if "tier" in df.columns else 0
    discarded = len(df[df["tier"] == "discard"]) if "tier" in df.columns else 0

    analysis_count = 0
    if ANALYSIS_DIR.exists():
        analysis_count = len([f for f in ANALYSIS_DIR.glob("*.md") if f.name != "summary.md"])

    avg_score = float(df["relevance_score"].mean()) if "relevance_score" in df.columns else 0.0

    top_archetypes = {}
    if "search_archetype" in df.columns:
        for arch, count in df["search_archetype"].value_counts().head(5).items():
            display = ARCHETYPE_DISPLAY.get(arch, arch)
            top_archetypes[display] = int(count)

    top_companies = []
    if "company" in df.columns:
        for company, count in df["company"].value_counts().head(10).items():
            avg = float(df[df["company"] == company]["relevance_score"].mean())
            top_companies.append({"name": str(company), "count": int(count), "avg_score": round(avg, 1)})

    score_dist = {"0-5": 0, "6-10": 0, "11-15": 0, "16-20": 0, "21-30": 0, "31+": 0}
    if "relevance_score" in df.columns:
        for score in df["relevance_score"]:
            if score <= 5: score_dist["0-5"] += 1
            elif score <= 10: score_dist["6-10"] += 1
            elif score <= 15: score_dist["11-15"] += 1
            elif score <= 20: score_dist["16-20"] += 1
            elif score <= 30: score_dist["21-30"] += 1
            else: score_dist["31+"] += 1

    boards = {}
    if "source_board" in df.columns:
        for b, count in df["source_board"].value_counts().items():
            boards[str(b)] = int(count)

    remote_count = int(df["is_remote"].sum()) if "is_remote" in df.columns else 0

    last_scrape = None
    raw_dir = REPO_ROOT / "pipeline_output" / "raw"
    if raw_dir.exists():
        raw_files = sorted(raw_dir.glob("scrape_*.csv"), reverse=True)
        if raw_files:
            last_scrape = raw_files[0].stem.replace("scrape_", "").replace("_", " ")

    return DashboardStats(
        total_jobs=len(df),
        shortlisted=shortlisted,
        consider=consider,
        discarded=discarded,
        with_analysis=analysis_count,
        avg_score=round(avg_score, 1),
        top_archetypes=top_archetypes,
        top_companies=top_companies,
        score_distribution=score_dist,
        boards_breakdown=boards,
        remote_count=remote_count,
        last_scrape=last_scrape,
    )


@router.get("/{job_id}")
def get_job(job_id: int):
    df = _load_jobs()
    if df.empty or job_id >= len(df):
        raise HTTPException(status_code=404, detail="Job not found")

    row = df.iloc[job_id]
    company = str(row.get("company", "Unknown"))
    title = str(row.get("title", "Unknown"))

    job = _row_to_job(row, job_id)
    job.description = str(row.get("description", "")) if pd.notna(row.get("description")) else None

    analysis_content = None
    has_analysis, analysis_file = _job_has_analysis(company, title)
    if has_analysis and analysis_file:
        filepath = ANALYSIS_DIR / analysis_file
        if filepath.exists():
            analysis_content = filepath.read_text(encoding="utf-8")

    return {
        "job": job,
        "analysis": analysis_content,
    }
