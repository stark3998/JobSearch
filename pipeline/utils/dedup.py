import re
import pandas as pd


def _normalize_company(name):
    if not name or pd.isna(name):
        return ""
    name = str(name).lower().strip()
    for suffix in [
        ", inc.", ", inc", " inc.", " inc",
        ", llc", " llc", ", corp.", " corp.",
        " corp", ", ltd.", " ltd.", " ltd",
        ", co.", " co.", " company",
    ]:
        name = name.replace(suffix, "")
    return name.strip()


def _normalize_title(title):
    if not title or pd.isna(title):
        return ""
    title = str(title).lower().strip()
    title = re.sub(r"\s*[-–—]\s*(remote|hybrid|on.?site).*$", "", title)
    title = re.sub(r"\s*\(.*?\)\s*", " ", title)
    return " ".join(title.split())


def _title_similarity(t1, t2):
    words1 = set(_normalize_title(t1).split())
    words2 = set(_normalize_title(t2).split())
    if not words1 or not words2:
        return 0.0
    return len(words1 & words2) / len(words1 | words2)


def deduplicate(df):
    if df.empty:
        return df

    df = df.copy()
    df["_url_norm"] = df["job_url"].astype(str).str.strip().str.lower()
    df["_company_norm"] = df["company"].apply(_normalize_company)
    df["_title_norm"] = df["title"].apply(_normalize_title)
    df["_desc_len"] = df["description"].astype(str).str.len()

    # Pass 1: Exact URL dedup — keep longest description per URL
    df = df.sort_values("_desc_len", ascending=False)

    board_map = (
        df.groupby("_url_norm")["source_board"]
        .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
        .to_dict()
    )
    df["found_on_boards"] = df["_url_norm"].map(board_map)
    df = df.drop_duplicates(subset=["_url_norm"], keep="first")

    # Pass 2: Fuzzy company+title dedup
    to_drop = set()
    indices = df.index.tolist()
    for i, idx_a in enumerate(indices):
        if idx_a in to_drop:
            continue
        for idx_b in indices[i + 1 :]:
            if idx_b in to_drop:
                continue
            if df.loc[idx_a, "_company_norm"] != df.loc[idx_b, "_company_norm"]:
                continue
            sim = _title_similarity(
                df.loc[idx_a, "title"], df.loc[idx_b, "title"]
            )
            if sim >= 0.8:
                # Merge board info into the keeper
                boards_a = df.loc[idx_a, "found_on_boards"]
                boards_b = df.loc[idx_b, "found_on_boards"]
                merged = ", ".join(
                    sorted(set(f"{boards_a}, {boards_b}".split(", ")))
                )
                df.loc[idx_a, "found_on_boards"] = merged
                to_drop.add(idx_b)

    df = df.drop(index=to_drop)

    df = df.drop(columns=["_url_norm", "_company_norm", "_title_norm", "_desc_len"])
    return df.reset_index(drop=True)
