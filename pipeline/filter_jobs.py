"""
Step 2: Score, deduplicate, and rank scraped jobs.

Usage:
    python filter_jobs.py                              # Process latest raw scrape
    python filter_jobs.py --input path/to/scrape.csv   # Specific file
    python filter_jobs.py --min-score 10               # Override threshold
"""

import argparse
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from utils.dedup import deduplicate
from utils.scoring import score_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PIPELINE_DIR = Path(__file__).parent
REPO_ROOT = PIPELINE_DIR.parent

REJECT_TITLE_PATTERNS = [
    r"\bjunior\b", r"\bintern\b", r"\bentry[\s-]level\b",
    r"\bnew grad\b", r"\bassociate\b(?!.*consult)",
    r"\bengineer i\b", r"\banalyst i\b",
]


def load_config(config_path=None):
    path = config_path or PIPELINE_DIR / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def find_latest_file(directory, prefix):
    files = sorted(Path(directory).glob(f"{prefix}*.csv"), reverse=True)
    return files[0] if files else None


def apply_level_filter(df, level_keywords):
    if df.empty:
        return df

    def should_reject(row):
        title = str(row.get("title", "")).lower()
        for pattern in REJECT_TITLE_PATTERNS:
            if re.search(pattern, title):
                return True
        return False

    mask = ~df.apply(should_reject, axis=1)
    rejected = len(df) - mask.sum()
    if rejected > 0:
        logger.info(f"Level filter rejected {rejected} junior/intern postings")
    return df[mask].copy()


def run_filter(df, config, min_score_override=None):
    logger.info(f"Starting filter: {len(df)} raw jobs")

    df = deduplicate(df)
    logger.info(f"After dedup: {len(df)} unique jobs")

    df = apply_level_filter(df, config.get("level_filter", []))
    logger.info(f"After level filter: {len(df)} jobs")

    df = score_jobs(df, config["scoring"])

    shortlist_min = min_score_override or config["thresholds"]["shortlist_min_score"]
    consider_min = config["thresholds"]["consider_min_score"]
    discard_below = config["thresholds"]["discard_below"]

    def assign_tier(score):
        if score >= shortlist_min:
            return "shortlist"
        if score >= consider_min:
            return "consider"
        if score >= discard_below:
            return "discard"
        return "reject"

    df["tier"] = df["relevance_score"].apply(assign_tier)

    df = df.sort_values("relevance_score", ascending=False)

    salary_floor = config.get("salary_floor", 120000)
    df["salary_flag"] = df.apply(
        lambda r: "below_target"
        if pd.notna(r.get("max_amount")) and r.get("max_amount", 0) < salary_floor
        else "",
        axis=1,
    )

    output_dir = REPO_ROOT / config["output"]["filtered_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output_path = output_dir / f"filtered_{timestamp}.csv"

    df_out = df[df["tier"] != "reject"].copy()
    df_out.to_csv(output_path, index=False)

    stats = df["tier"].value_counts().to_dict()
    logger.info(f"Filtered: {stats}. Saved to {output_path}")

    return df_out


def main():
    parser = argparse.ArgumentParser(description="Filter and score scraped jobs")
    parser.add_argument("--config", help="Path to config.yaml")
    parser.add_argument("--input", help="Path to raw scrape CSV")
    parser.add_argument(
        "--min-score", type=int, help="Override shortlist minimum score"
    )
    args = parser.parse_args()

    config = load_config(args.config)

    if args.input:
        input_path = Path(args.input)
    else:
        raw_dir = REPO_ROOT / config["output"]["raw_dir"]
        input_path = find_latest_file(raw_dir, "scrape_")

    if not input_path or not input_path.exists():
        logger.error(
            "No raw scrape file found. Run scrape_jobs.py first."
        )
        return pd.DataFrame()

    logger.info(f"Loading {input_path}")
    df = pd.read_csv(input_path)
    return run_filter(df, config, min_score_override=args.min_score)


if __name__ == "__main__":
    main()
