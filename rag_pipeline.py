#!/usr/bin/env python3
"""RAG retrieval pipeline for Danbooru tag generation.

Parses user descriptions into aspects, queries Chroma per aspect
using metadata filtering, returns relevant tag chunks for prompt assembly.
"""
import json
import os
import chromadb
from sentence_transformers import SentenceTransformer

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")
TAGS_FILE = os.path.join(DATA_DIR, "tags.json")
MODEL_NAME = "all-MiniLM-L6-v2"

# Subcategory -> what the user might say
ASPECT_MAP = {
    "hair_color": "hair color",
    "hair_style": "hair style",
    "eye": "eye color and features",
    "expression": "facial expression emotion",
    "body_type": "body type build",
    "clothing": "clothing outfit garment",
    "footwear": "footwear shoes legwear",
    "accessory": "accessory decoration jewelry",
    "pose": "pose position stance",
    "viewpoint": "camera angle viewpoint",
    "background": "background setting scene",
    "lighting": "lighting visual effect",
    "action": "action activity holding",
    "animal": "animal creature features",
    "quality": "quality tags",
    "character_count": "character count",
}

# Keywords to detect aspects from user description
ASPECT_KEYWORDS = {
    "hair_color": ["hair"],
    "hair_style": ["hair", "ponytail", "braid", "twintail", "bun", "bangs", "mohawk", "afro", "curl"],
    "eye": ["eyes", "pupil", "iris", "heterochromia"],
    "expression": ["smile", "frown", "grin", "cry", "serious", "angry", "sad", "happy", "blush", "expression"],
    "body_type": ["tall", "short", "muscular", "thin", "petite", "body", "build"],
    "clothing": ["dress", "shirt", "pants", "skirt", "robe", "uniform", "armor", "jacket", "coat", "suit", "kimono", "outfit", "clothes", "qipao", "hoodie", "sweater", "swimsuit"],
    "footwear": ["shoes", "boots", "heels", "sandals", "socks", "stockings", "thighhighs"],
    "accessory": ["hat", "scarf", "gloves", "necklace", "earring", "ribbon", "bandage", "belt", "mask", "wings", "horns", "halo", "bandages"],
    "pose": ["standing", "sitting", "lying", "kneeling", "walking", "running", "pose", "leaning"],
    "viewpoint": ["full body", "upper body", "portrait", "close-up", "looking at viewer", "from side", "profile", "cowboy shot"],
    "background": ["background", "outdoor", "indoor", "forest", "city", "beach", "room", "sky", "night", "day", "sunset", "school", "mountain", "field", "garden"],
    "lighting": ["lighting", "glow", "shadow", "sunlight", "cinematic", "dramatic", "bokeh"],
    "action": ["holding", "carrying", "fighting", "weapon", "sword", "gun", "shield", "bow"],
    "animal": ["cat", "dog", "bird", "rabbit", "horse", "dragon", "fox", "wolf"],
}

# Always-included subcategories
DEFAULT_SUBCATEGORIES = ["character_count", "quality"]


class RAGPipeline:
    def __init__(self):
        print("Loading embedding model...")
        self.model = SentenceTransformer(MODEL_NAME)
        
        print("Loading Chroma DB...")
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        self.collection = client.get_collection("danbooru_tags")
        
        print("Loading validation tags...")
        with open(TAGS_FILE) as f:
            data = json.load(f)
        self.wdv3_tags = set(data.get("validation_tags", []))
        
        # Build a flat tag->info lookup for quick access
        self.tag_lookup = data.get("tags", {})
        
        print(f"Ready — {self.collection.count()} chunks, {len(self.wdv3_tags)} validation tags")

    def detect_subcategories(self, description: str) -> list[str]:
        """Detect which subcategories are relevant from user description."""
        desc_lower = description.lower()
        detected = []
        
        for subcat, keywords in ASPECT_KEYWORDS.items():
            for kw in keywords:
                if kw in desc_lower:
                    if subcat not in detected:
                        detected.append(subcat)
                    break
        
        # Always include defaults
        for d in DEFAULT_SUBCATEGORIES:
            if d not in detected:
                detected.append(d)
        
        return detected

    def retrieve(self, description: str, subcategories: list[str] = None, results_per_aspect: int = 3) -> dict:
        """Run RAG retrieval for a character description.
        
        Uses metadata filtering to target the right subcategory,
        then semantic search within that subcategory.
        """
        if subcategories is None:
            subcategories = self.detect_subcategories(description)
        
        results = {}
        for subcat in subcategories:
            # Build a focused query from the description
            query_text = f"{ASPECT_MAP.get(subcat, subcat)}: {description}"
            query_emb = self.model.encode([query_text]).tolist()
            
            # Use metadata filter to only search relevant subcategory
            try:
                chroma_results = self.collection.query(
                    query_embeddings=query_emb,
                    n_results=results_per_aspect,
                    where={"subcategory": subcat},
                )
            except Exception:
                # Fallback without filter
                chroma_results = self.collection.query(
                    query_embeddings=query_emb,
                    n_results=results_per_aspect,
                )
            
            # Extract tags from retrieved chunks
            all_tags = []
            seen = set()
            for doc in chroma_results["documents"][0]:
                parts = doc.split(": ", 1)
                tag_str = parts[1] if len(parts) == 2 else doc
                tags = [t.strip() for t in tag_str.split(",")]
                for tag in tags:
                    tag = tag.strip()
                    if tag and tag not in seen:
                        seen.add(tag)
                        all_tags.append(tag)
            
            results[subcat] = all_tags
        
        return {
            "description": description,
            "subcategories": subcategories,
            "tags": results,
        }

    def retrieve_multi_character(self, characters: list[dict], shared_context: str = "") -> list[dict]:
        """Run retrieval for multiple characters separately to avoid trait bleed."""
        results = []
        for char in characters:
            full_desc = f"{char['name']}: {char['description']}"
            if shared_context:
                full_desc += f". Scene: {shared_context}"
            
            subcats = self.detect_subcategories(full_desc)
            result = self.retrieve(full_desc, subcats)
            result["character"] = char["name"]
            results.append(result)
        
        return results


if __name__ == "__main__":
    pipeline = RAGPipeline()
    
    # Test 1: Single character
    print("\n" + "="*60)
    print("TEST 1: Single character — Tzubaki")
    print("="*60)
    
    desc = ("Tzubaki, a young man with messy black hair and sharp red eyes "
            "wearing a black Chinese martial arts robe with red trim and "
            "white bandages on his forearms, standing in a bamboo forest, "
            "serious expression")
    result = pipeline.retrieve(desc)
    
    print(f"\nSubcategories: {result['subcategories']}")
    for subcat, tags in result["tags"].items():
        top = tags[:12]
        print(f"\n  {subcat} ({len(tags)} tags):")
        print(f"    {', '.join(top)}")
    
    # Test 2: Two characters
    print("\n" + "="*60)
    print("TEST 2: Multi-character — Tzubaki & Sakura")
    print("="*60)
    
    chars = [
        {"name": "Tzubaki", "description": "black hair, red eyes, black robe, chinese clothes"},
        {"name": "Sakura", "description": "pink hair, green eyes, red qipao dress"},
    ]
    results = pipeline.retrieve_multi_character(chars, "standing together outdoors")
    
    for r in results:
        print(f"\n  --- {r['character']} ---")
        print(f"  Subcategories: {r['subcategories']}")
        for subcat, tags in r["tags"].items():
            print(f"    {subcat}: {', '.join(tags[:8])}")
    
    # Test 3: Minimal
    print("\n" + "="*60)
    print("TEST 3: Minimal — 'a girl with blue hair'")
    print("="*60)
    
    result = pipeline.retrieve("a girl with blue hair")
    print(f"\nSubcategories: {result['subcategories']}")
    for subcat, tags in result["tags"].items():
        print(f"  {subcat}: {', '.join(tags[:10])}")
