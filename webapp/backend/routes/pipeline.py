from __future__ import annotations

import asyncio
import sys
import threading
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from ..models import PipelineRequest, PipelineStatus

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

REPO_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_DIR = REPO_ROOT / "pipeline"

sys.path.insert(0, str(PIPELINE_DIR))

_pipeline_state = {
    "running": False,
    "step": None,
    "progress": None,
    "started_at": None,
    "last_run": None,
    "last_run_stats": None,
}
_lock = threading.Lock()


def _run_pipeline_sync(request: PipelineRequest):
    from scrape_jobs import load_config, run_scraper
    from filter_jobs import run_filter, find_latest_file
    from analyze_jobs import run_analyzer

    config = load_config(str(PIPELINE_DIR / "config.yaml"))
    errors = []
    stats = {}

    try:
        with _lock:
            _pipeline_state["step"] = "scraping"
            _pipeline_state["progress"] = "Scraping jobs from boards..."

        scraped_df, errors = run_scraper(
            config,
            archetypes=request.archetypes,
            boards=request.boards,
            hours_old=request.hours_old,
        )
        stats["scraped"] = len(scraped_df) if scraped_df is not None else 0

        with _lock:
            _pipeline_state["step"] = "filtering"
            _pipeline_state["progress"] = f"Filtering {stats['scraped']} jobs..."

        if scraped_df is not None and not scraped_df.empty:
            filtered_df = run_filter(scraped_df, config, min_score_override=request.min_score)
        else:
            import pandas as pd
            raw_dir = REPO_ROOT / config["output"]["raw_dir"]
            latest = find_latest_file(raw_dir, "scrape_")
            if latest:
                filtered_df = run_filter(pd.read_csv(latest), config, min_score_override=request.min_score)
            else:
                filtered_df = pd.DataFrame()

        stats["filtered"] = len(filtered_df) if filtered_df is not None else 0
        stats["shortlisted"] = len(filtered_df[filtered_df["tier"] == "shortlist"]) if not filtered_df.empty and "tier" in filtered_df.columns else 0
        stats["consider"] = len(filtered_df[filtered_df["tier"] == "consider"]) if not filtered_df.empty and "tier" in filtered_df.columns else 0

        with _lock:
            _pipeline_state["step"] = "analyzing"
            _pipeline_state["progress"] = f"Analyzing {stats['shortlisted']} shortlisted jobs..."

        if filtered_df is not None and not filtered_df.empty:
            tiers = ["shortlist", "consider"]
            analyses = run_analyzer(
                filtered_df, config, tier_filter=tiers, limit=request.limit, errors=errors,
            )
            stats["analyses"] = len(analyses)
        else:
            stats["analyses"] = 0

        stats["errors"] = len(errors)

    except Exception as e:
        stats["error"] = str(e)
    finally:
        with _lock:
            _pipeline_state["running"] = False
            _pipeline_state["step"] = None
            _pipeline_state["progress"] = "Complete"
            _pipeline_state["last_run"] = datetime.now().isoformat()
            _pipeline_state["last_run_stats"] = stats


@router.get("/status", response_model=PipelineStatus)
def pipeline_status():
    with _lock:
        return PipelineStatus(**_pipeline_state)


@router.post("/run")
def run_pipeline(request: PipelineRequest):
    with _lock:
        if _pipeline_state["running"]:
            return {"status": "already_running", "message": "Pipeline is already running"}
        _pipeline_state["running"] = True
        _pipeline_state["started_at"] = datetime.now().isoformat()
        _pipeline_state["progress"] = "Starting..."

    thread = threading.Thread(target=_run_pipeline_sync, args=(request,), daemon=True)
    thread.start()

    return {"status": "started", "message": "Pipeline started in background"}


@router.post("/scrape-only")
def scrape_only(request: PipelineRequest):
    with _lock:
        if _pipeline_state["running"]:
            return {"status": "already_running"}
        _pipeline_state["running"] = True
        _pipeline_state["started_at"] = datetime.now().isoformat()

    def _run():
        from scrape_jobs import load_config, run_scraper
        config = load_config(str(PIPELINE_DIR / "config.yaml"))
        try:
            with _lock:
                _pipeline_state["step"] = "scraping"
                _pipeline_state["progress"] = "Scraping..."
            df, errors = run_scraper(config, archetypes=request.archetypes, boards=request.boards, hours_old=request.hours_old)
            stats = {"scraped": len(df) if df is not None else 0, "errors": len(errors)}
        except Exception as e:
            stats = {"error": str(e)}
        finally:
            with _lock:
                _pipeline_state["running"] = False
                _pipeline_state["step"] = None
                _pipeline_state["progress"] = "Complete"
                _pipeline_state["last_run"] = datetime.now().isoformat()
                _pipeline_state["last_run_stats"] = stats

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started"}


@router.get("/archetypes")
def get_archetypes():
    import yaml
    config_path = PIPELINE_DIR / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return {
        key: {"display_name": val["display_name"], "key": key}
        for key, val in config["archetypes"].items()
    }


@router.get("/boards")
def get_boards():
    import yaml
    config_path = PIPELINE_DIR / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return config["boards"]
