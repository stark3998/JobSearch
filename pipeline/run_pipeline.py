"""
Job Search Pipeline Orchestrator.

Usage:
    python run_pipeline.py                          # Full pipeline
    python run_pipeline.py --step scrape            # Only scrape
    python run_pipeline.py --step filter            # Filter latest raw
    python run_pipeline.py --step analyze           # Analyze latest filtered
    python run_pipeline.py --hours-old 24           # Daily quick scan
    python run_pipeline.py --boards indeed          # Indeed-only (fastest)
    python run_pipeline.py --archetypes cloud_security software_security
    python run_pipeline.py --limit 20               # Cap analysis count
    python run_pipeline.py --dry-run                # Preview search plan
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from scrape_jobs import load_config, run_scraper
from filter_jobs import run_filter, find_latest_file
from analyze_jobs import run_analyzer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PIPELINE_DIR = Path(__file__).parent
REPO_ROOT = PIPELINE_DIR.parent


def main():
    parser = argparse.ArgumentParser(
        description="Job Search Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py                          # Full pipeline
  python run_pipeline.py --dry-run                # Preview search plan
  python run_pipeline.py --boards indeed          # Quick scan (Indeed only)
  python run_pipeline.py --hours-old 24           # Last 24 hours only
  python run_pipeline.py --step filter            # Re-filter latest scrape
  python run_pipeline.py --step analyze --limit 5 # Analyze top 5 only
        """,
    )
    parser.add_argument("--config", help="Path to config.yaml")
    parser.add_argument(
        "--step",
        choices=["scrape", "filter", "analyze", "all"],
        default="all",
        help="Run a specific step or all (default: all)",
    )
    parser.add_argument("--hours-old", type=int, help="Override hours_old filter")
    parser.add_argument("--boards", nargs="+", help="Only scrape these boards")
    parser.add_argument(
        "--archetypes", nargs="+", help="Only scrape these archetypes"
    )
    parser.add_argument("--input", help="Input file for filter/analyze step")
    parser.add_argument(
        "--tier",
        default="shortlist,consider",
        help="Tiers to analyze (default: shortlist,consider)",
    )
    parser.add_argument(
        "--limit", type=int, default=30, help="Max jobs to analyze (default: 30)"
    )
    parser.add_argument(
        "--min-score", type=int, help="Override shortlist minimum score"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show search plan without executing",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    step = args.step
    errors = []

    # --- SCRAPE ---
    scraped_df = None
    if step in ("scrape", "all"):
        print("\n=== Step 1: Scraping Jobs ===\n")
        scraped_df, errors = run_scraper(
            config,
            archetypes=args.archetypes,
            boards=args.boards,
            hours_old=args.hours_old,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            return
        print(f"  Scraped {len(scraped_df)} raw jobs.\n")

    # --- FILTER ---
    filtered_df = None
    if step in ("filter", "all"):
        print("=== Step 2: Filtering & Scoring ===\n")
        if scraped_df is not None and not scraped_df.empty:
            df_input = scraped_df
        elif args.input:
            df_input = pd.read_csv(args.input)
        else:
            raw_dir = REPO_ROOT / config["output"]["raw_dir"]
            latest = find_latest_file(raw_dir, "scrape_")
            if not latest:
                logger.error("No raw scrape file found. Run with --step scrape first.")
                return
            logger.info(f"Using latest raw file: {latest}")
            df_input = pd.read_csv(latest)

        filtered_df = run_filter(df_input, config, min_score_override=args.min_score)
        shortlisted = len(filtered_df[filtered_df["tier"] == "shortlist"])
        considered = len(filtered_df[filtered_df["tier"] == "consider"])
        print(
            f"  After filtering: {len(filtered_df)} jobs "
            f"({shortlisted} shortlisted, {considered} to consider)\n"
        )

    # --- ANALYZE ---
    if step in ("analyze", "all"):
        print("=== Step 3: Generating JD Analyses ===\n")
        if filtered_df is not None and not filtered_df.empty:
            df_input = filtered_df
        elif args.input:
            df_input = pd.read_csv(args.input)
        else:
            filtered_dir = REPO_ROOT / config["output"]["filtered_dir"]
            latest = find_latest_file(filtered_dir, "filtered_")
            if not latest:
                logger.error(
                    "No filtered file found. Run with --step filter first."
                )
                return
            logger.info(f"Using latest filtered file: {latest}")
            df_input = pd.read_csv(latest)

        tiers = [t.strip() for t in args.tier.split(",")]
        analyses = run_analyzer(
            df_input, config, tier_filter=tiers, limit=args.limit, errors=errors
        )
        print(f"  Generated {len(analyses)} analysis files.\n")

    # --- FINAL SUMMARY ---
    print("=" * 50)
    print("Pipeline Complete!")
    print("=" * 50)

    summary_path = REPO_ROOT / config["output"]["summary_file"]
    if summary_path.exists():
        print(f"\n  Review results: {summary_path}")
    print(
        f"  Analysis files:  {REPO_ROOT / config['output']['analysis_dir']}/\n"
    )
    print("  Next steps:")
    print("  1. Open pipeline_output/summary.md for top matches")
    print("  2. Browse pipeline_output/analyses/ for detailed breakdowns")
    print("  3. For each job to apply to, run:")
    print(
        '     claude "Read CLAUDE.md and pipeline_output/analyses/FILE.md. '
        'Generate Resumes/cv_COMPANY.tex following Section 8 instructions."'
    )
    print()


if __name__ == "__main__":
    main()
