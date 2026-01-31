#!/usr/bin/env python3
"""
Download training images from rest area and truck parking cameras.
Downloads multiple batches to capture different occupancy levels.
"""

import os
import time
import requests
from pathlib import Path
from datetime import datetime

# Output directory
OUTPUT_DIR = Path("training_images")
OUTPUT_DIR.mkdir(exist_ok=True)

# Camera sources
CAMERAS = {
    # Minnesota DOT - St. Croix Travel Info Center (3 cameras)
    "MN_C30038": "https://video.dot.state.mn.us/video/image/metro/C30038",
    "MN_C30039": "https://video.dot.state.mn.us/video/image/metro/C30039",
    "MN_C30040": "https://video.dot.state.mn.us/video/image/metro/C30040",

    # NY Thruway - Truck Parking cameras (expanded list)
    "NY_TA_195": "https://nyssnapshot.com/TA_195.png",  # I-87 NB Ardsley Truck Pk 1
    "NY_TA_196": "https://nyssnapshot.com/TA_196.png",  # I-87 NB Ardsley Truck Pk 2
    "NY_TA_209": "https://nyssnapshot.com/TA_209.png",  # I-87 NB Plattekill Truck Pk 1
    "NY_TA_210": "https://nyssnapshot.com/TA_210.png",  # I-87 NB Plattekill Truck Pk 2
    "NY_TA_218": "https://nyssnapshot.com/TA_218.png",  # I-87 SB Ramapo Truck Pk 1
    "NY_TA_219": "https://nyssnapshot.com/TA_219.png",  # I-87 SB Ramapo Truck Pk 2
    "NY_TA_233": "https://nyssnapshot.com/TA_233.png",  # I-87 NB Malden Truck Pk 1
    "NY_TA_234": "https://nyssnapshot.com/TA_234.png",  # I-87 NB Malden Truck Pk 2
    "NY_TA_240": "https://nyssnapshot.com/TA_240.png",  # I-87 SB Ulster Truck Pk 1
    "NY_TA_241": "https://nyssnapshot.com/TA_241.png",  # I-87 SB Ulster Truck Pk 2
    "NY_TA_254": "https://nyssnapshot.com/TA_254.png",  # I-87 SB Modena Truck Pk 1
    "NY_TA_255": "https://nyssnapshot.com/TA_255.png",  # I-87 SB Modena Truck Pk 2
    # I-90 Thruway truck parking
    "NY_TA_276": "https://nyssnapshot.com/TA_276.png",  # I-90 Indian Castle Truck Pk
    "NY_TA_277": "https://nyssnapshot.com/TA_277.png",  # I-90 Indian Castle Truck Pk 2
    "NY_TA_284": "https://nyssnapshot.com/TA_284.png",  # I-90 Chittenango Truck Pk
    "NY_TA_285": "https://nyssnapshot.com/TA_285.png",  # I-90 Chittenango Truck Pk 2
    "NY_TA_303": "https://nyssnapshot.com/TA_303.png",  # I-90 Junius Ponds Truck Pk
    "NY_TA_304": "https://nyssnapshot.com/TA_304.png",  # I-90 Junius Ponds Truck Pk 2
    "NY_TA_313": "https://nyssnapshot.com/TA_313.png",  # I-90 Clifton Springs Truck Pk
    "NY_TA_314": "https://nyssnapshot.com/TA_314.png",  # I-90 Clifton Springs Truck Pk 2
}

def download_image(camera_id: str, url: str, batch: int) -> bool:
    """Download a single camera image."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = ".png" if "nyssnapshot" in url else ".jpg"
        filename = f"{camera_id}_batch{batch}_{timestamp}{ext}"
        filepath = OUTPUT_DIR / filename

        response = requests.get(url, timeout=15)
        response.raise_for_status()

        # Check if we got actual image data
        if len(response.content) < 5000:
            print(f"  {camera_id}: Too small ({len(response.content)} bytes), skipping")
            return False

        with open(filepath, "wb") as f:
            f.write(response.content)

        print(f"  {camera_id}: {len(response.content):,} bytes -> {filename}")
        return True

    except Exception as e:
        print(f"  {camera_id}: Error - {e}")
        return False

def download_batch(batch_num: int):
    """Download one batch of all cameras."""
    print(f"\n{'='*60}")
    print(f"BATCH {batch_num} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    success = 0
    for camera_id, url in CAMERAS.items():
        if download_image(camera_id, url, batch_num):
            success += 1
        time.sleep(0.5)  # Rate limiting

    print(f"\nBatch {batch_num}: {success}/{len(CAMERAS)} images downloaded")
    return success

def main():
    print("TRAINING IMAGE COLLECTION")
    print(f"Target: {len(CAMERAS)} cameras")
    print(f"Output: {OUTPUT_DIR.absolute()}")

    # Download 2 batches now (different snapshots in time)
    total = 0
    for batch in range(1, 3):
        total += download_batch(batch)
        if batch < 2:
            print("\nWaiting 30 seconds before next batch...")
            time.sleep(30)

    print(f"\n{'='*60}")
    print(f"COMPLETE: {total} images downloaded")
    print(f"{'='*60}")

    # List all downloaded images
    images = list(OUTPUT_DIR.glob("*.*"))
    print(f"\nTotal images in {OUTPUT_DIR}: {len(images)}")

if __name__ == "__main__":
    main()
