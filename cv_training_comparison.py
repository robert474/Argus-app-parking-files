#!/usr/bin/env python3
"""
Compare Haiku baseline vs Haiku+training context vs Opus ground truth.
"""

import os
import json
import base64
import time
from pathlib import Path
from datetime import datetime

# Load training data
def load_training_data():
    with open("training_data/labels.json") as f:
        return json.load(f)

def get_opus_ground_truth():
    """Extract Opus counts as ground truth."""
    data = load_training_data()
    ground_truth = {}
    for img in data["images"]:
        camera_id = img.get("camera_id")
        ground_truth[camera_id] = {
            "truck_count": img.get("truck_count", 0),
            "occupancy_percent": img.get("occupancy_percent", 0),
            "image_path": img.get("image_path")
        }
    return ground_truth

def get_training_context(camera_id):
    """Get training context for a camera."""
    data = load_training_data()
    site = data.get("sites", {}).get(camera_id, {})

    return {
        "avg_capacity": site.get("max_truck_count", "Unknown"),
        "avg_occupancy": site.get("avg_occupancy", 0),
        "detection_tips": site.get("detection_tips", "Count semi-truck trailers"),
        "sample_notes": site.get("samples", [{}])[0].get("detailed_notes", "")[:200] if site.get("samples") else ""
    }

def build_baseline_prompt():
    """Simple baseline prompt without training context."""
    return """Analyze this traffic camera image from a rest area or truck parking location.

Count the semi-trucks/18-wheelers visible and estimate lot occupancy.

Return as JSON:
{
  "truck_count": <int>,
  "occupancy_percent": <int>,
  "confidence": "<high/medium/low>"
}"""

def build_training_prompt(camera_id):
    """Build prompt enhanced with Opus training context."""
    ctx = get_training_context(camera_id)

    return f"""Analyze this traffic camera image from a truck parking facility.

SITE KNOWLEDGE (from expert analysis):
- Typical truck capacity: {ctx['avg_capacity']} trucks visible
- Average occupancy: {ctx['avg_occupancy']}%
- Detection tips: {ctx['detection_tips']}
- Expert notes: {ctx['sample_notes']}

COUNT TRUCKS CAREFULLY:
- Semi-trucks (trailers) only, not cars
- Each trailer = 1 truck
- If similar to training data, expect similar counts

Return JSON:
{{
  "truck_count": <int>,
  "occupancy_percent": <int>,
  "confidence": "<high/medium/low>"
}}"""

def call_haiku(image_path, prompt):
    """Call Haiku with given prompt."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return {"error": "No API key"}

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    ext = Path(image_path).suffix.lower()
    media_type = "image/png" if ext == ".png" else "image/jpeg"

    start = time.time()
    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                {"type": "text", "text": prompt}
            ]
        }]
    )
    elapsed = time.time() - start

    text = response.content[0].text
    try:
        start_idx = text.find('{')
        end_idx = text.rfind('}') + 1
        result = json.loads(text[start_idx:end_idx])
    except:
        result = {"raw": text}

    return {
        "result": result,
        "time": round(elapsed, 2),
        "tokens": response.usage.input_tokens
    }

def main():
    print("=" * 80)
    print("HAIKU BASELINE vs HAIKU+TRAINING vs OPUS GROUND TRUTH")
    print("=" * 80)

    ground_truth = get_opus_ground_truth()
    results = []

    for camera_id, truth in ground_truth.items():
        img_path = truth["image_path"]
        if not Path(img_path).exists():
            continue

        print(f"\n{camera_id}:")
        print(f"  Opus ground truth: {truth['truck_count']} trucks")

        # Baseline Haiku
        baseline = call_haiku(img_path, build_baseline_prompt())
        baseline_trucks = baseline.get("result", {}).get("truck_count", "?")
        print(f"  Haiku baseline:    {baseline_trucks} trucks")

        # Haiku with training context
        training = call_haiku(img_path, build_training_prompt(camera_id))
        training_trucks = training.get("result", {}).get("truck_count", "?")
        print(f"  Haiku+training:    {training_trucks} trucks")

        # Calculate errors
        opus_count = truth['truck_count']
        baseline_error = abs(baseline_trucks - opus_count) if isinstance(baseline_trucks, int) else "?"
        training_error = abs(training_trucks - opus_count) if isinstance(training_trucks, int) else "?"

        results.append({
            "camera": camera_id,
            "opus": opus_count,
            "baseline": baseline_trucks,
            "training": training_trucks,
            "baseline_error": baseline_error,
            "training_error": training_error,
            "baseline_tokens": baseline.get("tokens", 0),
            "training_tokens": training.get("tokens", 0)
        })

        time.sleep(0.5)  # Rate limiting

    # Summary
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    print(f"\n{'Camera':<12} {'Opus':<6} {'Baseline':<10} {'Training':<10} {'Base Err':<10} {'Train Err':<10}")
    print("-" * 80)

    total_baseline_err = 0
    total_training_err = 0
    count = 0

    for r in results:
        print(f"{r['camera']:<12} {r['opus']:<6} {r['baseline']:<10} {r['training']:<10} {r['baseline_error']:<10} {r['training_error']:<10}")
        if isinstance(r['baseline_error'], int) and isinstance(r['training_error'], int):
            total_baseline_err += r['baseline_error']
            total_training_err += r['training_error']
            count += 1

    print("-" * 80)
    if count > 0:
        avg_baseline = total_baseline_err / count
        avg_training = total_training_err / count
        print(f"{'AVERAGE':<12} {'':<6} {'':<10} {'':<10} {avg_baseline:<10.1f} {avg_training:<10.1f}")

        improvement = ((avg_baseline - avg_training) / avg_baseline * 100) if avg_baseline > 0 else 0
        print(f"\nAccuracy improvement with training: {improvement:.1f}%")

    # Token cost comparison
    total_base_tokens = sum(r['baseline_tokens'] for r in results)
    total_train_tokens = sum(r['training_tokens'] for r in results)
    print(f"\nToken usage - Baseline: {total_base_tokens:,} | Training: {total_train_tokens:,}")
    print(f"Token increase: {((total_train_tokens - total_base_tokens) / total_base_tokens * 100):.1f}%")

    # Save results
    with open(f"training_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\nResults saved!")

if __name__ == "__main__":
    main()
