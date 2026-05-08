import re


def _match_keyword(keyword, text):
    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
    return bool(re.search(pattern, text))


def score_single_job(title, description, location, is_remote, scoring_config):
    title_lower = (title or "").lower()
    desc_lower = (description or "").lower()

    score = 0
    matched_strong = []
    matched_moderate = []
    matched_negative = []

    for keyword in scoring_config.get("strong_positive", []):
        in_title = _match_keyword(keyword, title_lower)
        in_desc = _match_keyword(keyword, desc_lower)
        if in_title:
            score += 6
            matched_strong.append(f"{keyword} [title]")
        elif in_desc:
            score += 3
            matched_strong.append(keyword)

    for keyword in scoring_config.get("moderate_positive", []):
        in_title = _match_keyword(keyword, title_lower)
        in_desc = _match_keyword(keyword, desc_lower)
        if in_title:
            score += 2
            matched_moderate.append(f"{keyword} [title]")
        elif in_desc:
            score += 1
            matched_moderate.append(keyword)

    for keyword in scoring_config.get("negative", []):
        if _match_keyword(keyword, desc_lower) or _match_keyword(
            keyword, title_lower
        ):
            score -= 5
            matched_negative.append(keyword)

    if is_remote:
        score += 2
    loc_lower = (location or "").lower()
    if "seattle" in loc_lower:
        score += 3
    elif any(
        city in loc_lower
        for city in [
            "san francisco",
            "new york",
            "austin",
            "denver",
            "boston",
            "los angeles",
        ]
    ):
        score += 1

    return {
        "relevance_score": max(score, 0),
        "matched_strong": "; ".join(matched_strong),
        "matched_moderate": "; ".join(matched_moderate),
        "matched_negative": "; ".join(matched_negative),
        "strong_count": len(matched_strong),
        "moderate_count": len(matched_moderate),
        "negative_count": len(matched_negative),
    }


def score_jobs(df, scoring_config):
    import pandas as pd

    scores = df.apply(
        lambda row: score_single_job(
            row.get("title", ""),
            row.get("description", ""),
            str(row.get("location", "")),
            bool(row.get("is_remote", False)),
            scoring_config,
        ),
        axis=1,
        result_type="expand",
    )
    return pd.concat([df, scores], axis=1)
