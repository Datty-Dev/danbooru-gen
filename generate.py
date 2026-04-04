#!/usr/bin/env python3
"""Danbooru tag generation tool.

Usage:
  python generate.py "description here" [--model wai|pony|netayume|flux]
  
Outputs formatted context for the agent (Arbalest) to assemble final tags.
Can also run validation on agent output.
"""
import argparse
import json
import os
import sys

from rag_pipeline import RAGPipeline

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TAGS_FILE = os.path.join(DATA_DIR, "tags.json")

SYSTEM_PROMPT = """You are a Danbooru tag expert specializing in generating accurate,
well-structured tag prompts for anime image generation models.

When a user describes a character or scene, you will be provided with
relevant Danbooru tags retrieved from the knowledge base. Use ONLY
these retrieved tags to build the prompt. Never invent tags or use
natural language phrases as tags.

Always follow this tag order:
character count → solo → trigger word → hair color → hair style →
eye color → expression → body type → clothing → accessories →
pose → viewpoint → action → background → lighting → quality tags

Adjust output format based on the target model:
- WAI Illustrious / Illustrious XL: comma-separated tags with spaces,
  end with masterpiece, best quality, include NEGATIVE: section
- Pony Diffusion: prefix with score_9, score_8_up, score_7_up,
  source_anime, use underscores, include NEGATIVE: section
- NetaYume / Lumina2: natural language sentences, no negative prompt,
  guidance scale 4.0
- Flux: natural language sentences, no quality tags, no negative
  prompt, guidance scale 3.5

If no model is specified, default to WAI Illustrious format.
If a trigger word is provided, place it immediately after solo.
Always include 1boy or 1girl. Always include solo for single characters.
Always output NEGATIVE: for tag-based models unless told otherwise.
Aim for 20-40 tags. Avoid redundancy."""

MODEL_FORMATS = {
    "wai": {
        "name": "WAI Illustrious SDXL",
        "format": "tags",
        "negative": True,
        "guidance": "6.0-7.0",
        "separator": ", ",
        "use_underscores": False,
        "quality_tags": ["masterpiece", "best quality"],
        "prefix": [],
    },
    "illustrious": {
        "name": "Illustrious XL",
        "format": "tags",
        "negative": True,
        "guidance": "6.0-7.0",
        "separator": ", ",
        "use_underscores": False,
        "quality_tags": ["masterpiece", "best quality"],
        "prefix": [],
    },
    "pony": {
        "name": "Pony Diffusion",
        "format": "tags",
        "negative": True,
        "guidance": "6.0-7.0",
        "separator": ", ",
        "use_underscores": True,
        "quality_tags": [],
        "prefix": ["score_9", "score_8_up", "score_7_up", "source_anime"],
    },
    "netayume": {
        "name": "NetaYume / Lumina2",
        "format": "natural_language",
        "negative": False,
        "guidance": "4.0",
        "skip_rag": True,
    },
    "flux": {
        "name": "Flux",
        "format": "natural_language",
        "negative": False,
        "guidance": "3.5",
        "skip_rag": True,
    },
}

DEFAULT_NEGATIVE = [
    "worst quality", "low quality", "bad anatomy", "bad hands",
    "missing fingers", "extra fingers", "blurry", "watermark",
    "signature", "text", "jpeg artifacts", "chromatic aberration",
    "out of focus", "ugly", "deformed",
]



# Always-allowed tags that bypass WDv3 validation
# These are prompting conventions, not Danbooru tags
ALLOWED_PROMPT_TAGS = {
    "masterpiece", "best quality", "highres", "absurdres", "incredibly absurdres",
    "lowres", "normal quality", "worst quality", "low quality",
    "score_9", "score_8_up", "score_7_up", "score_6_up", "source_anime",
    "cinematic lighting", "dramatic lighting", "volumetric lighting",
    "high quality", "detailed", "detailed face", "detailed eyes",
    "nsfw", "sfw",
}

def format_rag_context(rag_result: dict) -> str:
    """Format RAG results into a context block for the agent."""
    lines = ["RETRIEVED TAGS (use ONLY these to build the prompt):\n"]
    
    for subcat, tags in rag_result["tags"].items():
        if tags:
            lines.append(f"[{subcat}] {', '.join(tags)}")
    
    return "\n".join(lines)


def validate_tags(output_tags: list[str], wdv3_tags: set) -> dict:
    """Validate generated tags against WDv3 list."""
    valid = []
    invalid = []
    
    for tag in output_tags:
        tag_clean = tag.strip()
        # Check with spaces and underscores
        if (tag_clean in wdv3_tags 
            or tag_clean.replace(" ", "_") in wdv3_tags 
            or tag_clean.replace("_", " ") in wdv3_tags
            or tag_clean in ALLOWED_PROMPT_TAGS
            or tag_clean.lower() in ALLOWED_PROMPT_TAGS):
            valid.append(tag_clean)
        else:
            invalid.append(tag_clean)
    
    return {"valid": valid, "invalid": invalid}


def parse_tag_output(text: str) -> list[str]:
    """Parse a comma-separated tag string into a list."""
    # Remove PROMPT: / NEGATIVE: prefixes
    if "NEGATIVE:" in text:
        text = text.split("NEGATIVE:")[0]
    if "PROMPT:" in text:
        text = text.replace("PROMPT:", "")
    
    tags = [t.strip() for t in text.split(",")]
    return [t for t in tags if t]


def main():
    parser = argparse.ArgumentParser(description="Danbooru tag generation tool")
    parser.add_argument("description", help="Character/scene description")
    parser.add_argument("--model", "-m", default="wai", choices=MODEL_FORMATS.keys(),
                        help="Target model (default: wai)")
    parser.add_argument("--trigger", "-t", default=None, help="Trigger word / character name")
    parser.add_argument("--validate", "-v", default=None, 
                        help="Validate a comma-separated tag output string")
    parser.add_argument("--context-only", "-c", action="store_true",
                        help="Only output RAG context, don't format full prompt")
    
    args = parser.parse_args()
    model_config = MODEL_FORMATS[args.model]
    
    # Load validation tags
    with open(TAGS_FILE) as f:
        data = json.load(f)
    wdv3_tags = set(data.get("validation_tags", []))
    
    # Validation mode
    if args.validate:
        tags = parse_tag_output(args.validate)
        result = validate_tags(tags, wdv3_tags)
        print(f"Valid ({len(result['valid'])}): {', '.join(result['valid'])}")
        if result["invalid"]:
            print(f"\nINVALID ({len(result['invalid'])}): {', '.join(result['invalid'])}")
        else:
            print("\nAll tags valid! ✓")
        return
    
    # Natural language models — no RAG needed
    if model_config.get("skip_rag"):
        print(f"Model: {model_config['name']}")
        print(f"Format: Natural language (no RAG needed)")
        print(f"Guidance: {model_config['guidance']}")
        print(f"\nGenerate a natural language description from: {args.description}")
        if args.trigger:
            print(f"Trigger word: {args.trigger}")
        return
    
    # Run RAG
    pipeline = RAGPipeline()
    
    # Detect if multi-character
    if args.trigger and "," in args.trigger:
        # Multi-character
        chars = []
        for part in args.trigger.split(","):
            name = part.strip()
            chars.append({"name": name, "description": args.description})
        results = pipeline.retrieve_multi_character(chars)
        # Merge all results
        merged_tags = {}
        for r in results:
            for subcat, tags in r["tags"].items():
                merged_tags.setdefault(subcat, []).extend(tags)
        rag_result = {"description": args.description, "subcategories": list(merged_tags.keys()), "tags": merged_tags}
    else:
        rag_result = pipeline.retrieve(args.description)
    
    if args.context_only:
        print(format_rag_context(rag_result))
        return
    
    # Full prompt template
    print("=" * 60)
    print(f"TARGET MODEL: {model_config['name']}")
    print(f"FORMAT: {model_config['format']}")
    print(f"GUIDANCE: {model_config['guidance']}")
    if args.trigger:
        print(f"TRIGGER WORD: {args.trigger}")
    print("=" * 60)
    
    print(f"\nUSER DESCRIPTION:\n{args.description}")
    
    print(f"\n{format_rag_context(rag_result)}")
    
    # Model-specific notes
    notes = []
    if model_config["prefix"]:
        notes.append(f"Prefix prompt with: {', '.join(model_config['prefix'])}")
    if model_config["use_underscores"]:
        notes.append("Use underscores in tags (not spaces)")
    else:
        notes.append("Use spaces in tags (not underscores)")
    if model_config["quality_tags"]:
        notes.append(f"End with: {', '.join(model_config['quality_tags'])}")
    if model_config["negative"]:
        notes.append("Include NEGATIVE: section")
        notes.append(f"Default negative: {', '.join(DEFAULT_NEGATIVE)}")
        if args.model == "wai":
            notes.append("Also add 'nsfw' to negative (unless user requests NSFW)")
    
    print(f"\nMODEL RULES:")
    for note in notes:
        print(f"  - {note}")
    
    print(f"\nSYSTEM PROMPT:\n{SYSTEM_PROMPT}")


if __name__ == "__main__":
    main()
