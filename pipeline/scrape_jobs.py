"""
Step 1: Scrape jobs from all configured boards.

Usage:
    python scrape_jobs.py                        # Use config.yaml defaults
    python scrape_jobs.py --hours-old 24         # Override freshness
    python scrape_jobs.py --boards indeed google  # Only these boards
    python scrape_jobs.py --archetypes cloud_security software_security
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent))
from utils.retry import retry_with_backoff
from utils.search_terms import build_search_configs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PIPELINE_DIR = Path(__file__).parent
REPO_ROOT = PIPELINE_DIR.parent


def load_config(config_path=None):
    path = config_path or PIPELINE_DIR / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def scrape_single(search_term, site_name, location, config,
                   google_search_term=None, is_remote=False):
    from jobspy import scrape_jobs

    board_settings = config.get("board_settings", {}).get(site_name, {})
    kwargs = {
        "site_name": [site_name],
        "search_term": search_term,
        "location": location,
        "results_wanted": board_settings.get("results_wanted", 30),
        "hours_old": config["scrape"]["hours_old"],
        "country_indeed": "USA",
        "description_format": config["scrape"].get("description_format", "markdown"),
        "verbose": 0,
    }
    if is_remote:
        kwargs["is_remote"] = True
    if site_name == "linkedin" and board_settings.get("fetch_description", True):
        kwargs["linkedin_fetch_description"] = True
    if site_name == "google" and google_search_term:
        kwargs["google_search_term"] = google_search_term
    proxies = config.get("proxies", [])
    if proxies:
        kwargs["proxies"] = proxies

    return retry_with_backoff(scrape_jobs, max_retries=3, base_delay=5, **kwargs)


def run_scraper(config, archetypes=None, boards=None, hours_old=None,
                dry_run=False):
    if hours_old:
        config["scrape"]["hours_old"] = hours_old

    active_archetypes = archetypes or list(config["archetypes"].keys())
    active_boards = boards or config["boards"]
    locations = config["locations"]
    include_remote = config.get("include_remote", True)

    all_configs = []
    for arch_key in active_archetypes:
        arch = config["archetypes"][arch_key]
        search_configs = build_search_configs(
            arch, locations, active_boards, include_remote
        )
        for sc in search_configs:
            sc["archetype_key"] = arch_key
        all_configs.extend(search_configs)

    if dry_run:
        print(f"\n[DRY RUN] Would execute {len(all_configs)} searches:")
        by_arch = {}
        for sc in all_configs:
            by_arch.setdefault(sc["archetype_key"], []).append(sc)
        for arch_key, configs in by_arch.items():
            display = config["archetypes"][arch_key]["display_name"]
            print(f"\n  {display} ({len(configs)} searches):")
            boards_used = set(sc["board"] for sc in configs)
            locs_used = set(sc["location"] for sc in configs)
            print(f"    Boards: {', '.join(sorted(boards_used))}")
            print(f"    Locations: {', '.join(sorted(locs_used))}")
            terms = set(
                sc.get("google_search_term") or sc["search_term"]
                for sc in configs
            )
            for t in sorted(terms)[:3]:
                print(f"    e.g. {t[:80]}")
        print(f"\n  Total: {len(all_configs)} API calls")
        est_time = len(all_configs) * config["scrape"].get(
            "delay_between_searches", 2
        )
        print(f"  Estimated time: ~{est_time // 60}m {est_time % 60}s\n")
        return pd.DataFrame(), []

    all_results = []
    errors = []
    default_delay = config["scrape"].get("delay_between_searches", 2)

    for sc in tqdm(all_configs, desc="Scraping jobs", unit="search"):
        try:
            board = sc["board"]
            delay = config.get("board_settings", {}).get(
                board, {}
            ).get("delay", default_delay)
            time.sleep(delay)

            df = scrape_single(
                search_term=sc["search_term"],
                site_name=board,
                location=sc["location"],
                config=config,
                google_search_term=sc.get("google_search_term"),
                is_remote=sc.get("is_remote", False),
            )

            if df is not None and not df.empty:
                df["search_archetype"] = sc["archetype_key"]
                df["search_location"] = sc["location"]
                df["source_board"] = board
                df["scrape_timestamp"] = datetime.now().isoformat()
                all_results.append(df)
                logger.info(
                    f"[{board}] {sc['archetype_key']} @ "
                    f"{sc['location']}: {len(df)} results"
                )
        except Exception as e:
            errors.append({
                "board": sc["board"],
                "archetype": sc["archetype_key"],
                "location": sc["location"],
                "error": str(e),
            })
            logger.warning(
                f"Failed: {sc['board']} / {sc['archetype_key']} / "
                f"{sc['location']}: {e}"
            )

    if all_results:
        combined = pd.concat(all_results, ignore_index=True)
    else:
        combined = pd.DataFrame()

    output_dir = REPO_ROOT / config["output"]["raw_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output_path = output_dir / f"scrape_{timestamp}.csv"

    if not combined.empty:
        combined.to_csv(output_path, index=False)
        logger.info(
            f"Scraped {len(combined)} total jobs "
            f"({len(errors)} errors). Saved to {output_path}"
        )
    else:
        logger.warning("No jobs scraped.")

    return combined, errors


def main():
    parser = argparse.ArgumentParser(description="Scrape jobs from job boards")
    parser.add_argument("--config", help="Path to config.yaml")
    parser.add_argument("--hours-old", type=int, help="Override hours_old filter")
    parser.add_argument("--boards", nargs="+", help="Only scrape these boards")
    parser.add_argument(
        "--archetypes", nargs="+", help="Only scrape these archetypes"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show search plan without scraping"
    )
    args = parser.parse_args()

    config = load_config(args.config)
    df, errors = run_scraper(
        config,
        archetypes=args.archetypes,
        boards=args.boards,
        hours_old=args.hours_old,
        dry_run=args.dry_run,
    )
    return df, errors


if __name__ == "__main__":
    main()
