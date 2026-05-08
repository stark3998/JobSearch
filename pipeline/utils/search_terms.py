def build_search_configs(archetype, locations, boards, include_remote):
    configs = []

    for board in boards:
        if board == "google":
            google_terms = archetype.get("search_terms", {}).get("google", [])
            for loc in locations:
                for template in google_terms:
                    configs.append({
                        "board": "google",
                        "search_term": "",
                        "google_search_term": template.format(
                            location=loc["name"]
                        ),
                        "location": loc["name"],
                        "is_remote": False,
                    })
        else:
            default_terms = archetype.get("search_terms", {}).get("default", [])
            for term in default_terms:
                for loc in locations:
                    configs.append({
                        "board": board,
                        "search_term": term,
                        "location": loc["name"],
                        "is_remote": False,
                    })
                if include_remote:
                    configs.append({
                        "board": board,
                        "search_term": term,
                        "location": "USA",
                        "is_remote": True,
                    })

    return configs
