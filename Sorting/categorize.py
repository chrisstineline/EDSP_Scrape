import json
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = ROOT_DIR / "Scraper" / "edspdk2.json"
OUTPUT_FILE = ROOT_DIR / "SortedByCategory.json"

CATEGORIES = {
    "Healthcare & Medicine": ["sundhedssystem", "læge", "gynækolog", "smerter", "hospital", "sygehus", "sygdom", "sundhed", "p-piller", "endometriose", "blødning", "sygeplejerske", "operation"],
    "Online & Social Media": ["facebook", "instagram", "beskeder", "dickpick", "tinder", "sociale medier", "internet", "online", "opslag", "skrev"],
    "Festivals & Events": ["roskilde", "festival", "karneval", "koncert", "rf25", "telt", "frivilligcampen"],
    "Workplace & Career": ["arbejde", "chef", "kollega", "job", "møde", "kontor", "firma"],
    "School & Education": ["skole", "efterskole", "gymnasie", "lærer", "undervisning", "elev", "studie", "universitet"],
    "Nightlife & Parties": ["byen", "bar", "diskotek", "fulde", "alkohol", "fest", "druk", "klub"],
    "Family & Relationships": ["eksmand", "kæreste", "mand", "børn", "hjemmet", "ægteskab", "familie", "sviger"],
    "Public Transport": ["bus", "tog", "station", "toget", "bussen", "metro", "offentlig transport"],
    "Street & Public Spaces": ["gaden", "tisse i det fri", "råbte", "fløjtede", "parken", "cykel", "offentlig", "tissede", "buskene"],
    "Other": []
}

def get_category(text):
    text = text.lower()
    scores = {cat: 0 for cat in CATEGORIES}
    
    for cat, keywords in CATEGORIES.items():
        if cat == "Other":
            continue
        for kw in keywords:
            # count occurrences of the keyword
            scores[cat] += text.count(kw.lower())
    
    # Find category with max score
    best_cat = max(scores, key=scores.get)
    if scores[best_cat] > 0:
        return best_cat
    return "Other"

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for item in data:
        full_text = (item.get("title", "") + " " + item.get("text", "")).lower()
        item["category"] = get_category(full_text)
        
    data_sorted = sorted(data, key=lambda x: (x.get("year") or 0, x.get("category", "")))
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data_sorted, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully sorted into {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
