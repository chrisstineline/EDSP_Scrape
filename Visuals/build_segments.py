from __future__ import annotations

import json
import re
from collections import Counter
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Sorting" / "sorted.json"
TARGET = ROOT / "Visuals" / "Segments.md"
STATS_TARGET = ROOT / "Visuals" / "Stats.md"
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


def average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def build_pie_chart(title: str, data: dict[str, int]) -> str:
    lines = ["```mermaid", "pie showData", f"    title {json.dumps(title)}"]
    for label, value in data.items():
        lines.append(f"    {json.dumps(label)} : {value}")
    lines.append("```")
    return "\n".join(lines)


def build_xychart(title: str, x_labels: list[str], y_title: str, series: list[tuple[str, str, list[float | int]]]) -> str:
    max_value = 0.0
    min_value = 0.0
    for _, _, values in series:
        if values:
            max_value = max(max_value, max(float(value) for value in values))
            min_value = min(min_value, min(float(value) for value in values))

    lower_bound = int(min_value) - (1 if min_value < 0 else 0)
    upper_bound = max(1, int(max_value) + (2 if max_value <= 10 else 10))
    lines = [
        "```mermaid",
        "---",
        "config:",
        "    xyChart:",
        "        width: 1100",
        "        height: 520",
        "---",
        "xychart-beta",
        f"    title {json.dumps(title)}",
        f"    x-axis [{', '.join(json.dumps(label) for label in x_labels)}]",
        f"    y-axis {json.dumps(y_title)} {lower_bound} --> {upper_bound}",
    ]

    for chart_type, _, values in series:
        value_list = ", ".join(f"{float(value):.2f}" if isinstance(value, float) and not float(value).is_integer() else str(int(value) if float(value).is_integer() else value) for value in values)
        lines.append(f"    {chart_type} [{value_list}]")

    lines.append("```")
    return "\n".join(lines)


def build_stats_markdown(data: dict) -> str:
    years = sorted(data["years"].keys())
    sentiment_order = ["negative", "mixed", "neutral", "positive"]

    yearly_sentiment_counts = {
        sentiment: [data["years"][year]["sentiment_groups"].get(sentiment, {}).get("count", 0) for year in years]
        for sentiment in sentiment_order
    }

    yearly_average_scores = []
    yearly_medianish_scores = []
    theme_average_scores: Counter[str] = Counter()
    theme_score_totals: defaultdict[str, list[int]] = defaultdict(list)

    for year in years:
        posts = data["years"][year]["posts"]
        scores = [post["sentiment"]["score"] for post in posts]
        yearly_average_scores.append(round(average(scores), 2))
        sorted_scores = sorted(scores)
        yearly_medianish_scores.append(sorted_scores[len(sorted_scores) // 2] if sorted_scores else 0)
        for post in posts:
            primary_theme = (post.get("themes") or ["uncategorized"])[0]
            theme_score_totals[primary_theme].append(post["sentiment"]["score"])

    theme_average_pairs = sorted(
        ((theme, round(average(scores), 2), len(scores)) for theme, scores in theme_score_totals.items()),
        key=lambda item: (-item[2], item[0]),
    )[:8]

    overall_scores = [
        post["sentiment"]["score"]
        for year in years
        for post in data["years"][year]["posts"]
    ]

    lines = [
        "# EDSP Sentiment Stats",
        "",
        "Generated from `Sorting/sorted.json`.",
        "",
        "## Summary",
        "",
        f"- Total posts analyzed: {data['total_posts']}",
        f"- Years covered: {', '.join(years)}",
        f"- Overall average sentiment score: {average(overall_scores):.2f}",
        f"- Lowest / highest sentiment score: {min(overall_scores)} / {max(overall_scores)}",
        "",
        "## Overall Sentiment Distribution",
        "",
        build_pie_chart(
            "Overall sentiment labels across all posts",
            {SENTIMENT_LABELS[key]: data["sentiment_summary"].get(key, 0) for key in sentiment_order},
        ),
        "",
        "## Sentiment Counts by Year",
        "",
        build_xychart(
            "Sentiment label counts by year",
            years,
            "Posts",
            [("bar", sentiment, yearly_sentiment_counts[sentiment]) for sentiment in sentiment_order],
        ),
        "",
        "## Average Sentiment Score by Year",
        "",
        build_xychart(
            "Average sentiment score by year",
            years,
            "Average score",
            [("line", "average_score", yearly_average_scores), ("bar", "medianish_score", yearly_medianish_scores)],
        ),
        "",
        "## Average Sentiment Score by Major Theme",
        "",
        build_xychart(
            "Average sentiment score for the most common primary themes",
            [THEME_LABELS.get(theme, theme.title()) for theme, _, _ in theme_average_pairs],
            "Average score",
            [("bar", "average_score", [score for _, score, _ in theme_average_pairs])],
        ),
        "",
        "## Theme Coverage Used For Score Chart",
        "",
    ]

    for theme, score, count in theme_average_pairs:
        lines.append(f"- {THEME_LABELS.get(theme, theme.title())}: {count} posts, average score {score:.2f}")

    lines.append("")
    return "\n".join(lines)


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
    stats_markdown = build_stats_markdown(data)
    TARGET.write_text(markdown, encoding="utf-8")
    STATS_TARGET.write_text(stats_markdown, encoding="utf-8")
    print(f"Wrote {TARGET}")
    print(f"Wrote {STATS_TARGET}")


if __name__ == "__main__":
    main()
