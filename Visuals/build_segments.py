from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Sorting" / "sorted.json"
TARGET = ROOT / "Visuals" / "Segments.md"
TITLE_LIMIT = 60

THEME_LABELS = {
    "dismissal_gaslighting": "Dismissal / Gaslighting",
    "gender_roles": "Gender Roles",
    "harassment_abuse": "Harassment / Abuse",
    "body_sexualization": "Body / Sexualization",
    "healthcare_system": "Healthcare System",
    "reproductive_health": "Reproductive Health",
    "pain_diagnosis": "Pain / Diagnosis",
    "mental_health": "Mental Health",
    "uncategorized": "Uncategorized",
}

SENTIMENT_LABELS = {
    "negative": "Negative",
    "mixed": "Mixed",
    "neutral": "Neutral",
    "positive": "Positive",
}


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "node"


def clean_label(value: str, limit: int | None = None) -> str:
    value = value.replace("\n", " ").replace("\r", " ")
    value = re.sub(r"\s+", " ", value).strip()
    value = value.replace('"', "'")
    value = value.replace("[", "(").replace("]", ")")
    value = value.replace("`", "'")
    if limit and len(value) > limit:
        value = value[: limit - 1].rstrip() + "…"
    return value


def mermaid_node(node_id: str, label: str) -> str:
    return f'{node_id}["{clean_label(label)}"]'


def build_year_mindmap(year: str, posts: list[dict]) -> str:
    theme_buckets: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))

    for post in posts:
        themes = post.get("themes") or ["uncategorized"]
        primary_theme = themes[0]
        sentiment = post["sentiment"]["label"]
        theme_buckets[primary_theme][sentiment].append(post)

    lines = ["```mermaid", "mindmap", f'  {mermaid_node(f"y{year}", f"{year} ({len(posts)} posts)")}']

    for theme in sorted(theme_buckets, key=lambda key: (-sum(len(v) for v in theme_buckets[key].values()), key)):
        theme_posts = theme_buckets[theme]
        theme_total = sum(len(items) for items in theme_posts.values())
        theme_id = f"y{year}_{slugify(theme)}"
        theme_label = f"{THEME_LABELS.get(theme, theme.title())} ({theme_total})"
        lines.append(f'    {mermaid_node(theme_id, theme_label)}')

        for sentiment in sorted(theme_posts, key=lambda key: (-len(theme_posts[key]), key)):
            sentiment_items = sorted(theme_posts[sentiment], key=lambda post: post["id"])
            sentiment_id = f"{theme_id}_{slugify(sentiment)}"
            sentiment_label = f"{SENTIMENT_LABELS.get(sentiment, sentiment.title())} ({len(sentiment_items)})"
            lines.append(f'      {mermaid_node(sentiment_id, sentiment_label)}')

            for post in sentiment_items:
                post_id = f"{sentiment_id}_p{post['id']}"
                post_label = f"{post['id']}: {clean_label(post['title'], TITLE_LIMIT)}"
                lines.append(f'        {mermaid_node(post_id, post_label)}')

    lines.append("```")
    return "\n".join(lines)


def build_markdown(data: dict) -> str:
    years = data["years"]
    lines = [
        "# EDSP Segments",
        "",
        "Generated from `Sorting/sorted.json`.",
        "",
        "> Mermaid mindmaps in Markdown do not support true per-node click/expand interactions in a portable way.",
        "> To keep the file usable, each year is wrapped in an expandable section and posts appear as leaf nodes under `Year -> Theme -> Sentiment`.",
        "",
        "## Overview",
        "",
        f"- Total posts: {data['total_posts']}",
        f"- Years covered: {', '.join(sorted(years.keys()))}",
        "- Segmenting rule: primary theme = first assigned theme in `sorted.json`",
        "",
    ]

    for year in sorted(years.keys()):
        year_data = years[year]
        posts = year_data["posts"]
        lines.extend([
            f"<details>",
            f"<summary><strong>{year}</strong> — {len(posts)} posts</summary>",
            "",
            build_year_mindmap(year, posts),
            "",
            "</details>",
            "",
        ])

    return "\n".join(lines)


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    markdown = build_markdown(data)
    TARGET.write_text(markdown, encoding="utf-8")
    print(f"Wrote {TARGET}")


if __name__ == "__main__":
    main()
