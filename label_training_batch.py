#!/usr/bin/env python3
"""
Label training images with Opus and add to training data.
"""

import os
import json
import base64
import time
from pathlib import Path
from datetime import datetime

TRAINING_DIR = Path("training_images")
LABELS_FILE = Path("training_data/labels.json")

def get_opus_prompt():
    return """You are creating training data for a truck parking detection system.
Analyze this image with EXTREME PRECISION. Your counts will be used to train other models.

COUNTING RULES:
1. Semi-trucks: Count all tractor-trailers. Each trailer = 1 truck.
2. Bobtails: Cab-only trucks count as 0.5 (note separately)
3. Cars/SUVs: Count but keep separate from trucks
4. Uncertain: If a vehicle is partially visible, include it with a note

ANALYSIS REQUIRED:
1. Exact truck count (be very precise)
2. Exact car count
3. Total visible parking spaces (estimate)
4. Current occupancy percentage
5. Weather conditions affecting visibility
6. Time of day estimate (day/dusk/night)
7. Any detection challenges (shadows, snow, obstructions)

Return detailed JSON:
{
  "truck_count": <int - exact count>,
  "bobtail_count": <int - cab-only trucks>,
  "car_count": <int>,
  "total_spaces_visible": <int - estimated capacity in frame>,
  "spaces_occupied": <int>,
  "occupancy_percent": <int>,
  "weather": "<clear/cloudy/rain/snow/fog>",
  "visibility_quality": "<excellent/good/fair/poor>",
  "time_of_day": "<day/dusk/dawn/night>",
  "detection_challenges": ["<list any issues>"],
  "truck_positions": "<brief description of where trucks are located>",
  "confidence": "<high/medium/low>",
  "detailed_notes": "<any other observations useful for training>"
}"""

def load_labels():
    if LABELS_FILE.exists():
        with open(LABELS_FILE) as f:
            return json.load(f)
    return {"images": [], "sites": {}}

def save_labels(labels):
    with open(LABELS_FILE, "w") as f:
        json.dump(labels, f, indent=2)

def extract_camera_id(filename):
    """Extract camera ID from filename like NY_TA_195_batch1_20260131_133207.png"""
    parts = filename.replace(".png", "").replace(".jpg", "").split("_")
    if parts[0] == "NY":
        return f"NY_TA_{parts[2]}"
    elif parts[0] == "MN":
        return f"MN_{parts[1]}"
    return "_".join(parts[:2])

def label_image(image_path, client):
    """Label a single image with Opus."""

    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    ext = Path(image_path).suffix.lower()
    media_type = "image/png" if ext == ".png" else "image/jpeg"

    start_time = time.time()

    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                {"type": "text", "text": get_opus_prompt()}
            ]
        }]
    )

    elapsed = time.time() - start_time

    # Parse response
    text = response.content[0].text
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        label = json.loads(text[start:end])
    except:
        label = {"raw_response": text, "parse_error": True}

    # Add metadata
    camera_id = extract_camera_id(image_path.name)
    label["camera_id"] = camera_id
    label["image_path"] = str(image_path)
    label["labeled_at"] = datetime.now().isoformat()
    label["labeling_time_sec"] = round(elapsed, 2)
    label["input_tokens"] = response.usage.input_tokens
    label["output_tokens"] = response.usage.output_tokens

    return label

def compute_site_stats(labels):
    """Compute per-site statistics."""
    site_stats = {}

    for label in labels["images"]:
        camera_id = label.get("camera_id")
        if not camera_id:
            continue

        if camera_id not in site_stats:
            site_stats[camera_id] = {"samples": [], "name": camera_id}

        site_stats[camera_id]["samples"].append({
            "truck_count": label.get("truck_count"),
            "occupancy_percent": label.get("occupancy_percent"),
            "weather": label.get("weather"),
            "time_of_day": label.get("time_of_day"),
            "detailed_notes": label.get("detailed_notes"),
        })

    # Compute aggregates
    for camera_id, stats in site_stats.items():
        samples = stats["samples"]
        if samples:
            truck_counts = [s["truck_count"] for s in samples if s.get("truck_count") is not None]
            occupancies = [s["occupancy_percent"] for s in samples if s.get("occupancy_percent") is not None]

            stats["avg_truck_count"] = sum(truck_counts) / len(truck_counts) if truck_counts else 0
            stats["max_truck_count"] = max(truck_counts) if truck_counts else 0
            stats["min_truck_count"] = min(truck_counts) if truck_counts else 0
            stats["avg_occupancy"] = sum(occupancies) / len(occupancies) if occupancies else 0
            stats["sample_count"] = len(samples)

            # Detection tips
            all_notes = " ".join([s.get("detailed_notes", "") for s in samples])
            if "snow" in all_notes.lower():
                stats["detection_tips"] = "Winter conditions common. Look for truck shapes despite snow."
            else:
                stats["detection_tips"] = "Standard detection. Count trailer rectangles."

    return site_stats

def main():
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # Get images to label
    images = list(TRAINING_DIR.glob("*.png")) + list(TRAINING_DIR.glob("*.jpg"))

    # Load existing labels
    labels = load_labels()
    labeled_paths = {l.get("image_path") for l in labels["images"]}

    # Filter to unlabeled images
    to_label = [img for img in images if str(img) not in labeled_paths]

    print("=" * 70)
    print("OPUS TRAINING LABELING")
    print("=" * 70)
    print(f"Total images: {len(images)}")
    print(f"Already labeled: {len(labeled_paths)}")
    print(f"To label: {len(to_label)}")
    print()

    if not to_label:
        print("All images already labeled!")
        return

    for i, img_path in enumerate(to_label, 1):
        print(f"[{i}/{len(to_label)}] {img_path.name}...", end=" ", flush=True)

        try:
            label = label_image(img_path, client)
            labels["images"].append(label)
            save_labels(labels)

            trucks = label.get("truck_count", "?")
            print(f"✓ {trucks} trucks ({label.get('labeling_time_sec', '?')}s)")

        except Exception as e:
            print(f"✗ Error: {e}")

        time.sleep(1)  # Rate limiting

    # Update site statistics
    print("\nComputing site statistics...")
    labels["sites"] = compute_site_stats(labels)
    save_labels(labels)

    # Summary
    print("\n" + "=" * 70)
    print("LABELING COMPLETE")
    print("=" * 70)
    print(f"Total labeled images: {len(labels['images'])}")
    print(f"Sites: {len(labels['sites'])}")

    for site, data in labels["sites"].items():
        print(f"\n{site}:")
        print(f"  Samples: {data.get('sample_count', 0)}")
        print(f"  Avg trucks: {data.get('avg_truck_count', 0):.1f}")
        print(f"  Range: {data.get('min_truck_count', 0)}-{data.get('max_truck_count', 0)}")

if __name__ == "__main__":
    main()
