from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "Scraper" / "edspdk2.json"
DEFAULT_OUTPUT = ROOT / "Sorting" / "sorted.json"
MAX_KEYWORDS_PER_POST = 6
MAX_KEYWORD_GROUPS_PER_YEAR = 30

TOKEN_RE = re.compile(r"[a-zA-ZÀ-ÿ]+")

STOPWORDS = {
    "af", "aldrig", "alle", "allerede", "alt", "altid", "andre", "at", "blev", "bliver", "bare",
    "begyndte", "blevet", "blev", "både", "ca", "da", "de", "dem", "den", "dengang", "denne",
    "der", "deres", "det", "dette", "dig", "din", "dine", "dit", "dog", "du", "efter", "egen",
    "eller", "en", "end", "endelig", "ene", "eneste", "ens", "er", "et", "faktisk", "far", "få",
    "fik", "for", "fordi", "forløb", "fra", "frem", "får", "før", "først", "gennem", "gerne", "godt",
    "gør", "gjorde", "gøre", "ham", "han", "hans", "har", "havde", "hele", "heller", "hellere",
    "helt", "her", "hende", "hendes", "herefter", "herfra", "hos", "hun", "hvad", "hvem", "hver",
    "hvis", "hvor", "hvordan", "hvorfor", "i", "iblandt", "ikke", "igen", "igennem", "ind", "inde",
    "ingen", "intet", "jeg", "jer", "jo", "kan", "kom", "komme", "kun", "kunne", "kvinde", "kvinder",
    "læge", "lægen", "lægger", "man", "med", "meget", "mere", "mig", "min", "mine", "mit", "mod",
    "må", "måtte", "mænd", "mødte", "ned", "nej", "nok", "noget", "nogle", "nu", "når", "og", "også",
    "om", "op", "oplevede", "oplever", "os", "over", "på", "prøvede", "ret", "rigtig", "rigtig", "sagde",
    "samme", "selv", "selvom", "sig", "sin", "sine", "skal", "skulle", "som", "stadig", "stor", "store",
    "så", "sådan", "taget", "talte", "til", "tilbage", "tit", "to", "tog", "ud", "uden", "var", "ved",
    "vi", "ville", "virkelig", "vores", "være", "været", "år", "årig", "årige"
}

POSITIVE_WORDS = {
    "bedre", "berettiget", "endelig", "engel", "engle", "glad", "gladere", "god", "gode", "godt",
    "hjalp", "hjulpet", "hjælp", "hjælpe", "imponeret", "lettelse", "lyttet", "mulighed", "nyt", "respekterede",
    "seriøst", "støtter", "sød", "søde", "taget", "tryg", "værdig"
}

NEGATIVE_WORDS = {
    "afvist", "alvorligt", "angst", "arrogant", "bekymret", "blindtarm", "blodforgiftning", "blodprop",
    "bristet", "chikane", "chokeret", "cyste", "depression", "dickpick", "dårligt", "død", "døde", "ekstreme",
    "feber", "fikseret", "forkert", "frøs", "galt", "gaslightet", "graviditet", "græd", "grænseoverskridende",
    "hade", "hysterisk", "infektion", "koldbrand", "kræft", "krænkende", "lungebetændelse", "ondt", "opkast",
    "overgreb", "overgreb", "panik", "pornhub", "psykisk", "rystet", "seksisme", "sindssygt", "skam", "skriger",
    "slem", "smerte", "smerter", "sprunget", "stress", "svimmel", "syg", "sygdom", "svær", "tabu", "traumatisk",
    "tumor", "udholdelige", "ubehageligt", "uforklarlige", "ulykkelig", "vold", "voldsom", "voldsomme", "vred",
    "værre"
}

THEME_KEYWORDS = {
    "healthcare_system": {
        "1813", "akut", "ambulance", "behandling", "gynækolog", "hospital", "indlagt", "jordemoder",
        "kirurg", "læge", "lægehus", "lægevagt", "operation", "patient", "scanning", "sygehus", "sygeplejerske",
        "undersøgelse", "vagtlæge"
    },
    "reproductive_health": {
        "abort", "adenomyose", "bækken", "celleforandring", "endometriose", "fødsel", "gravid", "graviditet",
        "gynækolog", "hymen", "keglesnit", "livmoder", "menstruation", "underliv", "vaginisme", "vulvodyni",
        "ægløsning", "æggeleder", "æggestok"
    },
    "harassment_abuse": {
        "blindfolded", "buskene", "dickpick", "filme", "filmet", "filmede", "forgreb", "instagram", "karneval",
        "kondom", "krænkende", "marketplace", "overgreb", "pornhub", "roskilde", "samtykke", "sex", "stealthing",
        "toilet", "voldtægt"
    },
    "mental_health": {
        "adhd", "angst", "bipolar", "depression", "deprimeret", "psykisk", "psykiater", "psykolog",
        "selvmord", "stress", "stresset"
    },
    "pain_diagnosis": {
        "blindtarm", "blodprop", "cyste", "diagnose", "feber", "galde", "infektion", "kræft", "lungebetændelse",
        "morfin", "ondt", "opkast", "smerte", "smerter", "svimmel", "tumor", "undersøgelser"
    },
    "dismissal_gaslighting": {
        "afvist", "arrogant", "bare", "bildte", "hysterisk", "indbildte", "inget", "normalt", "overfølsom",
        "psykisk", "slap", "tag", "taget", "tog", "tages", "tog", "tror"
    },
    "gender_roles": {
        "børn", "datter", "far", "føde", "født", "husholdersken", "kone", "mand", "manden", "mor", "søn"
    },
    "body_sexualization": {
        "bryst", "bryster", "charmerende", "date", "fertilitet", "flot", "hofter", "køn", "krop", "lækker",
        "partner", "promiskuøse", "smuk", "trøjen", "udseende"
    },
}


@dataclass
class PostAnalysis:
    index: int
    title: str
    month: str
    year: int
    text: str
    sentiment_label: str
    sentiment_score: int
    positive_hits: list[str]
    negative_hits: list[str]
    themes: list[str]
    keywords: list[str]


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def extract_keywords(title: str, text: str) -> list[str]:
    tokens = [token for token in tokenize(f"{title} {text}") if len(token) > 3 and token not in STOPWORDS]
    counts = Counter(tokens)
    return [token for token, _ in counts.most_common(MAX_KEYWORDS_PER_POST)]


def analyze_sentiment(title: str, text: str) -> tuple[str, int, list[str], list[str]]:
    tokens = tokenize(f"{title} {text}")
    positive_hits = [token for token in tokens if token in POSITIVE_WORDS]
    negative_hits = [token for token in tokens if token in NEGATIVE_WORDS]
    score = len(positive_hits) - len(negative_hits)

    if score <= -2:
        label = "negative"
    elif score >= 2:
        label = "positive"
    elif positive_hits or negative_hits:
        label = "mixed"
    else:
        label = "neutral"

    return label, score, sorted(set(positive_hits)), sorted(set(negative_hits))


def analyze_themes(title: str, text: str, keywords: list[str]) -> list[str]:
    token_set = set(tokenize(f"{title} {text}")) | set(keywords)
    matched = []

    for theme, theme_words in THEME_KEYWORDS.items():
        overlap = token_set & theme_words
        if overlap:
            matched.append((theme, len(overlap)))

    if not matched:
        return ["uncategorized"]

    matched.sort(key=lambda item: (-item[1], item[0]))
    return [theme for theme, _ in matched[:3]]


def analyze_posts(posts: list[dict]) -> list[PostAnalysis]:
    analyzed = []
    for index, post in enumerate(posts, start=1):
        title = post["title"]
        month = post["month"]
        year = int(post["year"])
        text = post["text"]
        keywords = extract_keywords(title, text)
        sentiment_label, sentiment_score, positive_hits, negative_hits = analyze_sentiment(title, text)
        themes = analyze_themes(title, text, keywords)
        analyzed.append(
            PostAnalysis(
                index=index,
                title=title,
                month=month,
                year=year,
                text=text,
                sentiment_label=sentiment_label,
                sentiment_score=sentiment_score,
                positive_hits=positive_hits,
                negative_hits=negative_hits,
                themes=themes,
                keywords=keywords,
            )
        )
    return analyzed


def build_output(analyzed_posts: list[PostAnalysis]) -> dict:
    years: dict[str, dict] = {}

    grouped_by_year: dict[int, list[PostAnalysis]] = defaultdict(list)
    for post in analyzed_posts:
        grouped_by_year[post.year].append(post)

    for year in sorted(grouped_by_year):
        posts = grouped_by_year[year]
        sentiment_groups: dict[str, list[int]] = defaultdict(list)
        theme_groups: dict[str, list[int]] = defaultdict(list)
        keyword_groups: dict[str, list[int]] = defaultdict(list)

        for post in posts:
            sentiment_groups[post.sentiment_label].append(post.index)
            for theme in post.themes:
                theme_groups[theme].append(post.index)
            for keyword in post.keywords:
                keyword_groups[keyword].append(post.index)

        keyword_groups_sorted = dict(
            sorted(keyword_groups.items(), key=lambda item: (-len(item[1]), item[0]))[:MAX_KEYWORD_GROUPS_PER_YEAR]
        )

        years[str(year)] = {
            "post_count": len(posts),
            "sentiment_groups": {
                label: {"count": len(ids), "post_ids": ids}
                for label, ids in sorted(sentiment_groups.items())
            },
            "theme_groups": {
                theme: {"count": len(ids), "post_ids": ids}
                for theme, ids in sorted(theme_groups.items(), key=lambda item: (-len(item[1]), item[0]))
            },
            "keyword_groups": {
                keyword: {"count": len(ids), "post_ids": ids}
                for keyword, ids in keyword_groups_sorted.items()
            },
            "posts": [
                {
                    "id": post.index,
                    "title": post.title,
                    "month": post.month,
                    "year": post.year,
                    "text": post.text,
                    "sentiment": {
                        "label": post.sentiment_label,
                        "score": post.sentiment_score,
                        "positive_hits": post.positive_hits,
                        "negative_hits": post.negative_hits,
                    },
                    "themes": post.themes,
                    "keywords": post.keywords,
                }
                for post in posts
            ],
        }

    theme_counts = Counter(theme for post in analyzed_posts for theme in post.themes)
    sentiment_counts = Counter(post.sentiment_label for post in analyzed_posts)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": str(DEFAULT_INPUT.relative_to(ROOT)),
        "total_posts": len(analyzed_posts),
        "year_count": len(years),
        "sentiment_summary": dict(sorted(sentiment_counts.items())),
        "theme_summary": dict(sorted(theme_counts.items(), key=lambda item: (-item[1], item[0]))),
        "years": years,
    }


def main() -> None:
    posts = json.loads(DEFAULT_INPUT.read_text(encoding="utf-8"))
    analyzed_posts = analyze_posts(posts)
    output = build_output(analyzed_posts)
    DEFAULT_OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote analysis for {len(analyzed_posts)} posts to {DEFAULT_OUTPUT}")


if __name__ == "__main__":
    main()
