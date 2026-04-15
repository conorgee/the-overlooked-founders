"""
Generate Synthetic Training Applications
Creates 200+ synthetic applications across the score range (10-98)
for training the application classifier.

Uses Ollama locally — no API tokens needed.
Run: python scripts/generate_synthetic_apps.py
"""

import json
import os
import re
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"

import httpx

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:0.5b"
OUTPUT_FILE = str(root / "models" / "synthetic_applications.json")

GENERATION_PROMPT = """Generate a realistic startup programme application.
Target AI score: {target_score}/100.

Score guidelines:
- 80-100: Exceptional — specific problem, validated customer, clear revenue model, evidence of traction
- 60-79: Promising — good idea but gaps in validation or specifics
- 40-59: Potential — vague problem or untested assumptions
- 1-39: Early — generic idea, no customer understanding

Generate realistic fields. Return ONLY valid JSON:
{{"business_name": "...", "business_idea": "2-4 sentences", "stage": "idea|mvp|launched|growing"}}"""


def generate_application(target_score: int) -> dict | None:
    prompt = GENERATION_PROMPT.format(target_score=target_score)

    try:
        response = httpx.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.9, "num_predict": 300},
            },
            timeout=60.0,
        )
        response.raise_for_status()
        raw = response.json().get("message", {}).get("content", "")

        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            return None

        parsed = json.loads(match.group())
        parsed["ai_score"] = target_score
        parsed["is_synthetic"] = True

        if not parsed.get("business_idea") or len(parsed["business_idea"]) < 10:
            return None

        return parsed
    except Exception:
        return None


def main():
    print("Generating synthetic applications...")
    applications = []

    for target_score in range(10, 100, 2):
        app = generate_application(target_score)
        if app:
            applications.append(app)
            print(f"  Score {target_score:3d}: {app.get('business_name', 'N/A')[:40]}")
        else:
            print(f"  Score {target_score:3d}: [generation failed, retrying]")
            app = generate_application(target_score)
            if app:
                applications.append(app)
                print(f"  Score {target_score:3d}: {app.get('business_name', 'N/A')[:40]} (retry)")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(applications, f, indent=2)

    print(f"\nGenerated {len(applications)} synthetic applications")
    print(f"Saved to {OUTPUT_FILE}")

    bands = {"80-100": 0, "60-79": 0, "40-59": 0, "1-39": 0}
    for app in applications:
        s = app["ai_score"]
        if s >= 80: bands["80-100"] += 1
        elif s >= 60: bands["60-79"] += 1
        elif s >= 40: bands["40-59"] += 1
        else: bands["1-39"] += 1

    print(f"\nScore distribution:")
    for band, count in bands.items():
        bar = "\u2588" * count
        print(f"  {band:>6s}: {count:3d} {bar}")


if __name__ == "__main__":
    main()
