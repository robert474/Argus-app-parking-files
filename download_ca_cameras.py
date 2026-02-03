#!/usr/bin/env python3
"""
Download California rest area and truck parking cameras from Caltrans.
"""

import os
import time
import requests
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path("training_images")
OUTPUT_DIR.mkdir(exist_ok=True)

# California Rest Area and Truck Parking Cameras from Caltrans
# Format: camera_id -> (district, path_component)
CA_CAMERAS = {
    # Rest Areas
    "CA_Whitewater_RestArea_WB": ("d8", "i10tpas1whitewaterrestareawb"),
    "CA_Westley_RestStop_NB": ("d10", "11nbi5westleyreststop"),
    "CA_DesertOasis_RestArea": ("d8", "i40383atdesertoasisrestarea"),

    # Truck Scales/Inspection Stations
    "CA_Truckee_Scales_EB": ("d3", "hwy80attruckeescales"),
    "CA_Truckee_Scales_WB": ("d3", "hwy80attruckeescaleswb"),
    "CA_RainbowValley_TruckInsp_S": ("d8", "i1529805misorainbowvalleytruckinspectionstation"),
    "CA_RainbowValley_TruckInsp_N": ("d8", "i1529906minorainbowvalleytruckinspsta"),

    # Truck Escape Ramps (Kern County I-5)
    "CA_Kern_TruckEscape_Shoulder": ("d6", "ker5attruckescaperampshoulder"),
    "CA_Kern_TruckEscape_Median": ("d6", "ker5attruckescaperampmedian"),

    # Indian Truck Trail (I-15)
    "CA_IndianTruckTrail_S": ("d8", "i1534007milessouthofindiantrucktrailroad"),
    "CA_IndianTruckTrail": ("d8", "i15341southofindiantrucktrailroad"),
    "CA_IndianTruckTrail_N": ("d8", "i15342northofindiantrucktrailroad"),
}

def download_camera(camera_id: str, district: str, path: str) -> bool:
    """Download a Caltrans camera image."""
    url = f"https://cwwp2.dot.ca.gov/data/{district}/cctv/image/{path}/{path}.jpg"

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{camera_id}_{timestamp}.jpg"
        filepath = OUTPUT_DIR / filename

        response = requests.get(url, timeout=15)
        response.raise_for_status()

        if len(response.content) < 3000:
            print(f"  {camera_id}: Too small ({len(response.content)} bytes), may be error page")
            return False

        with open(filepath, "wb") as f:
            f.write(response.content)

        print(f"  {camera_id}: {len(response.content):,} bytes -> {filename}")
        return True

    except Exception as e:
        print(f"  {camera_id}: Error - {e}")
        return False

def main():
    print("CALIFORNIA REST AREA & TRUCK PARKING CAMERAS")
    print(f"Target: {len(CA_CAMERAS)} cameras")
    print(f"Output: {OUTPUT_DIR.absolute()}")
    print("=" * 60)

    success = 0
    for camera_id, (district, path) in CA_CAMERAS.items():
        if download_camera(camera_id, district, path):
            success += 1
        time.sleep(0.5)

    print("=" * 60)
    print(f"COMPLETE: {success}/{len(CA_CAMERAS)} images downloaded")

    # List downloaded CA images
    ca_images = list(OUTPUT_DIR.glob("CA_*.jpg"))
    print(f"\nTotal CA images: {len(ca_images)}")

if __name__ == "__main__":
    main()
