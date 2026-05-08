from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Tier(str, Enum):
    shortlist = "shortlist"
    consider = "consider"
    discard = "discard"
    reject = "reject"


class Job(BaseModel):
    id: int
    title: str
    company: str
    location: str
    city: Optional[str] = None
    state: Optional[str] = None
    is_remote: bool = False
    job_url: str = ""
    date_posted: Optional[str] = None
    salary: Optional[str] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    currency: Optional[str] = "USD"
    description: Optional[str] = None
    relevance_score: int = 0
    tier: Optional[str] = None
    search_archetype: Optional[str] = None
    source_board: Optional[str] = None
    found_on_boards: Optional[str] = None
    matched_strong: Optional[str] = None
    matched_moderate: Optional[str] = None
    matched_negative: Optional[str] = None
    salary_flag: Optional[str] = None
    has_analysis: bool = False
    analysis_file: Optional[str] = None


class JobsResponse(BaseModel):
    jobs: list[Job]
    total: int
    page: int
    per_page: int
    total_pages: int


class DashboardStats(BaseModel):
    total_jobs: int = 0
    shortlisted: int = 0
    consider: int = 0
    discarded: int = 0
    with_analysis: int = 0
    avg_score: float = 0.0
    top_archetypes: dict[str, int] = {}
    top_companies: list[dict] = []
    score_distribution: dict[str, int] = {}
    boards_breakdown: dict[str, int] = {}
    remote_count: int = 0
    last_scrape: Optional[str] = None


class PipelineStatus(BaseModel):
    running: bool = False
    step: Optional[str] = None
    progress: Optional[str] = None
    started_at: Optional[str] = None
    last_run: Optional[str] = None
    last_run_stats: Optional[dict] = None


class PipelineRequest(BaseModel):
    boards: Optional[list[str]] = None
    archetypes: Optional[list[str]] = None
    hours_old: Optional[int] = None
    limit: Optional[int] = 30
    min_score: Optional[int] = None


class ResumeRequest(BaseModel):
    job_id: int
    archetype_override: Optional[str] = None
    one_page: bool = False
    provider: str = "auto"


class ValidationResult(BaseModel):
    matched_keywords: list[str] = []
    missing_keywords: list[str] = []
    coverage_percent: float = 0.0
    total_keywords: int = 0


class ResumeResponse(BaseModel):
    success: bool
    tex_path: Optional[str] = None
    pdf_path: Optional[str] = None
    cover_letter_path: Optional[str] = None
    analysis_path: Optional[str] = None
    message: str = ""
    validation: Optional[ValidationResult] = None
    provider_used: Optional[str] = None
