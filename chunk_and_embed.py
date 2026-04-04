#!/usr/bin/env python3
"""Chunk WDv3-validated general tags, embed, store in Chroma.

All general tags are embedded — WDv3 list used for validation separately.
This is the set we'll actually retrieve and output.
Artist/character/copyright are skipped — not needed for prompt generation.
"""
import json
import os
import chromadb
from sentence_transformers import SentenceTransformer

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")
TAGS_FILE = os.path.join(DATA_DIR, "tags.json")
MODEL_NAME = "all-MiniLM-L6-v2"

# Keyword-based subcategory assignment
SUBCATEGORY_RULES = [
    # (subcategory, keywords, description)
    ("quality", ["masterpiece", "best quality", "highres", "absurdres", "lowres", "official art"], "quality tags for anime image generation"),
    ("character_count", ["1girl", "1boy", "2girls", "2boys", "multiple", "solo", "group"], "character count tags"),
    ("hair_color", ["hair"], "hair colors for anime characters"),  # broad — catches most hair tags
    ("hair_style", ["ponytail", "braid", "twintail", "bun", "ahoge", "sidelocks", "bob cut", "hair over", "hair between", "hair pulled", "hair across", "hair behind", "hair swept", "hair flipped", "hair pulled back", "hair up", "hair down", "hair tied"], "hair styles and hairstyles"),
    ("eye", ["eyes", "pupil", "heterochromia", "iris"], "eye colors and eye features"),
    ("expression", ["smile", "blush", "frown", "grin", "cry", "tears", "expression", "angry", "surprised", "sad", "happy", "serious", "open mouth", "closed mouth", "tongue", "clenched teeth", "furrowed", "closed eyes", "one eye closed", "half-closed", "wink", "pout", "smirk", "scowl", "gasp", "panting"], "facial expressions and emotions"),
    ("body_type", ["breasts", "muscular", "petite", "mature female", "mature male", "loli", "child", "tall", "abs", "navel", "hips", "thighs", "stomach", "waist", "buff", "chubby", "plump", "slim"], "body types and physical features"),
    ("clothing", ["dress", "shirt", "skirt", "pants", "uniform", "armor", "robe", "jacket", "coat", "suit", "swimsuit", "underwear", "kimono", "qipao", "cheongsam", "clothes", "wear", "bra", "panties", "hoodie", "sweater", "vest", "blouse", "apron", "bikini", "leotard", "chinese clothes", "navel", "midriff", "bare shoulders", "bare legs", "bare arms", "bare back", "bare feet", "bare chest", "bare shoulders", "collar", "sleeve", "cape"], "clothing items and garments"),
    ("footwear", ["shoes", "boots", "heels", "sandals", "socks", "stockings", "thighhighs", "pantyhose", "knee boots", "loafers", "footwear"], "footwear and legwear"),
    ("accessory", ["glasses", "earrings", "necklace", "hat", "scarf", "gloves", "belt", "ribbon", "bow", "headband", "headwear", "choker", "bracelet", "watch", "mask", "bandages", "collar", "cape", "wings", "halo", "horns", "tail", "hair ornament", "hair ribbon", "hairband", "hair clip", "bandaid", "bandage"], "accessories and decorations"),
    ("pose", ["standing", "sitting", "lying", "kneeling", "walking", "running", "jumping", "arms up", "arms behind", "crossed arms", "hand on hip", "stretch", "leaning", "crouching", "squatting", "bent over", "spread arms", "on back", "on stomach", "legs apart", "legs together", "legs crossed", "arms at sides"], "body poses and positions"),
    ("viewpoint", ["looking at viewer", "from above", "from below", "from behind", "from side", "profile", "close-up", "full body", "upper body", "cowboy shot", "portrait", "dutch angle", "fisheye", "wide shot", "multiple views", "background character"], "camera angles and viewpoints"),
    ("background", ["background", "outdoors", "indoors", "sky", "forest", "city", "room", "water", "beach", "night", "day", "sunset", "cloudy", "rain", "snow", "mountain", "field", "garden", "park", "street", "school", "castle", "temple", "nature", "landscape", "flowers", "tree", "grass", "ground"], "backgrounds and settings"),
    ("lighting", ["lighting", "backlight", "rim light", "lens flare", "sunlight", "moonlight", "shadow", "glow", "sparkle", "bokeh", "depth of field", "blur", "motion blur", "chromatic", "film grain", "cinematic", "dramatic lighting", "volumetric"], "lighting and visual effects"),
    ("action", ["holding", "carrying", "fighting", "reading", "eating", "drinking", "sleeping", "weapon", "sword", "gun", "shield", "staff", "bow", "playing", "singing", "dancing", "cooking", "painting", "grab", "touch", "hug", "kiss", "punch", "kick"], "actions and activities"),
    ("animal", ["cat", "dog", "bird", "rabbit", "horse", "fish", "dragon", "fox", "wolf", "snake", "butterfly", "animal ears", "cat ears", "paw", "fur", "feather", "claw", "fang"], "animals and creature features"),
]

def assign_subcategory(tag_name):
    """Assign subcategory based on keyword matching. First match wins."""
    name_lower = tag_name.lower().replace(" ", "_")
    # Check specific rules first (order matters — more specific before broad)
    for subcat, keywords, desc in SUBCATEGORY_RULES:
        for kw in keywords:
            if kw in name_lower:
                return subcat
    return "other"

def main():
    print("Loading tags...")
    with open(TAGS_FILE) as f:
        data = json.load(f)
    
    # Only WDv3-validated general tags
    tags = {
        k: v for k, v in data["tags"].items()
        if v.get("category") in ("general", "unknown")
    }
    print(f"All general tags: {len(tags)}")
    
    # Assign subcategories
    subcategorized = {}
    for name, info in tags.items():
        subcat = assign_subcategory(name)
        subcategorized.setdefault(subcat, []).append((name, info))
    
    print("\nSubcategory breakdown:")
    for sc in sorted(subcategorized.keys(), key=lambda x: -len(subcategorized[x])):
        print(f"  {sc}: {len(subcategorized[sc])} tags")
    
    # Build chunks — small chunks for precise retrieval
    MAX_PER_CHUNK = 80
    chunks = []
    for subcat, tag_list in subcategorized.items():
        tag_list.sort(key=lambda x: x[1].get("count", 0), reverse=True)
        desc = next((d for s, k, d in SUBCATEGORY_RULES if s == subcat), "miscellaneous anime art tags")
        
        for i in range(0, len(tag_list), MAX_PER_CHUNK):
            batch = tag_list[i:i+MAX_PER_CHUNK]
            tag_names = [t[0] for t in batch]
            # Rich text for embedding — description + tag list
            text = f"{desc}: {', '.join(tag_names)}"
            
            chunks.append({
                "id": f"{subcat}_{i//MAX_PER_CHUNK}",
                "subcategory": subcat,
                "tags": tag_names,
                "text": text,
                "count": len(tag_names),
            })
    
    print(f"\nCreated {len(chunks)} chunks")
    
    # Load model
    print(f"Loading embedding model: {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    
    # Create Chroma
    print("Creating Chroma database...")
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        client.delete_collection("danbooru_tags")
    except:
        pass
    
    collection = client.create_collection(
        name="danbooru_tags",
        metadata={"hnsw:space": "cosine"},
    )
    
    # Embed and store
    print("Embedding and storing...")
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        texts = [c["text"] for c in batch]
        ids = [c["id"] for c in batch]
        metadatas = [{"subcategory": c["subcategory"], "tag_count": c["count"]} for c in batch]
        
        embeddings = model.encode(texts, show_progress_bar=False).tolist()
        collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
    
    print(f"Stored {len(chunks)} chunks")
    
    # Save chunk index for reference
    chunk_index = [{"id": c["id"], "subcategory": c["subcategory"], "tags": c["tags"]} for c in chunks]
    with open(os.path.join(DATA_DIR, "chunk_index.json"), "w") as f:
        json.dump(chunk_index, f, indent=2, ensure_ascii=False)
    print("Saved chunk_index.json")
    
    # Tests
    print("\n--- Test searches ---")
    tests = [
        "messy black hair",
        "chinese robe with red trim clothing",
        "serious expression",
        "bamboo forest outdoors background",
        "white bandages on forearms",
        "standing full body",
        "red eyes",
        "school uniform clothing",
        "holding sword weapon action",
        "cinematic lighting dramatic",
    ]
    for query in tests:
        query_emb = model.encode([query]).tolist()
        results = collection.query(query_embeddings=query_emb, n_results=3)
        print(f"\n  '{query}'")
        for doc, dist, meta in zip(results["documents"][0], results["distances"][0], results["metadatas"][0]):
            preview = doc[:140]
            print(f"    [{dist:.3f}] ({meta['subcategory']}) {preview}...")

if __name__ == "__main__":
    main()
