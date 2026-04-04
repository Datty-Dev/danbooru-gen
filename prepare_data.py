#!/usr/bin/env python3
"""Download and prepare tag data from three sources into a clean deduplicated dataset."""
import csv
import json
import os

DATA_DIR = os.path.dirname(os.path.abspath(__file__)) + "/data"

def load_wdv3():
    """Load WDv3 selected_tags.csv - primary validation source."""
    tags = {}
    with open(f"{DATA_DIR}/../wdv3_tags.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["name"].strip()
            # Skip rating/meta tags
            if row["category"] in ("9",):
                continue
            tags[name] = {
                "name": name,
                "category": "character" if row["category"] == "4" else "general",
                "count": int(row["count"]),
                "source": "wdv3",
            }
    print(f"WDv3: {len(tags)} tags")
    return tags

def load_danbooru_json():
    """Load danbooru.json - provides descriptions."""
    tags = {}
    with open(f"{DATA_DIR}/danbooru.json") as f:
        data = json.load(f)
    for entry in data:
        name = entry["tag"].strip()
        tags[name] = {
            "name": name,
            "description": entry.get("description", ""),
            "source": "danbooru_json",
        }
    print(f"danbooru.json: {len(tags)} tags")
    return tags

def load_a1111():
    """Load a1111 danbooru.csv - large tag list with aliases."""
    tags = {}
    with open(f"{DATA_DIR}/a1111-temp/tags/danbooru.csv") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 4:
                continue
            name = row[0].strip()
            cat_id = row[1].strip()
            count = int(row[2]) if row[2].strip().isdigit() else 0
            aliases = row[3].strip() if len(row) > 3 else ""
            
            cat_map = {"0": "general", "1": "artist", "3": "copyright", "4": "character", "5": "meta"}
            category = cat_map.get(cat_id, "general")
            
            tags[name] = {
                "name": name,
                "category": category,
                "count": count,
                "aliases": [a.strip() for a in aliases.split(",") if a.strip()] if aliases else [],
                "source": "a1111",
            }
    print(f"a1111: {len(tags)} tags")
    return tags

def main():
    # Load all sources
    wdv3 = load_wdv3()
    danbooru_json = load_danbooru_json()
    a1111 = load_a1111()
    
    # Build unified dataset - WDv3 takes priority
    unified = {}
    
    # Start with a1111 (largest, has aliases)
    for name, tag in a1111.items():
        unified[name] = tag
    
    # Overlay danbooru.json (adds descriptions)
    for name, tag in danbooru_json.items():
        if name in unified:
            if tag.get("description"):
                unified[name]["description"] = tag["description"]
        else:
            unified[name] = tag
    
    # Overlay WDv3 (priority source - overwrites category/count)
    for name, tag in wdv3.items():
        if name in unified:
            unified[name]["category"] = tag["category"]
            unified[name]["count"] = tag["count"]
            unified[name]["wdv3_validated"] = True
        else:
            tag["wdv3_validated"] = True
            unified[name] = tag
    
    # Mark which tags are WDv3-validated (our validation set)
    wdv3_names = set(wdv3.keys())
    
    # Build output
    output = {
        "metadata": {
            "total_tags": len(unified),
            "wdv3_validated_count": len([t for t in unified.values() if t.get("wdv3_validated")]),
            "sources": ["wdv3", "danbooru_json", "a1111"],
        },
        "validation_tags": sorted(wdv3_names),
        "tags": dict(sorted(unified.items())),
    }
    
    out_path = f"{DATA_DIR}/tags.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\nUnified dataset: {len(unified)} tags")
    print(f"WDv3 validated: {len(wdv3_names)} tags")
    print(f"Saved to {out_path}")
    
    # Category breakdown
    cats = {}
    for t in unified.values():
        c = t.get("category", "unknown")
        cats[c] = cats.get(c, 0) + 1
    print("\nCategory breakdown:")
    for c, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {c}: {n}")

if __name__ == "__main__":
    main()
