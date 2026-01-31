#!/usr/bin/env python3
"""
RAG-Enhanced Truck Parking Detection for Haiku

Uses retrieval-augmented generation to improve Haiku's accuracy by:
1. Providing site-specific context (camera angle, lot layout, capacity)
2. Including few-shot examples with known truck counts
3. Adding historical patterns for the specific camera

This should improve Haiku's accuracy to approach Sonnet levels at 1/10th the cost.
"""

import os
import json
import base64
import time
from pathlib import Path
from datetime import datetime

# Site knowledge base - would be populated from your database
SITE_KNOWLEDGE = {
    "MN_C30038": {
        "name": "St. Croix Travel Info Center - Camera 1",
        "total_capacity": 53,
        "truck_spaces": 50,
        "car_spaces": 3,
        "camera_angle": "elevated overhead, looking north",
        "lot_layout": "angled parking rows running east-west, trucks park nose-in",
        "landmarks": "red building with signage on east side, highway visible in background",
        "typical_occupancy": {
            "weekday_day": "20-40%",
            "weekday_night": "60-80%",
            "weekend": "30-50%"
        },
        "detection_tips": "Trucks appear as white/colored rectangles. Empty spaces show gray pavement. Snow may cover lines but spaces are still visible."
    },
    "MN_C30040": {
        "name": "St. Croix Travel Info Center - Camera 3",
        "total_capacity": 53,
        "truck_spaces": 50,
        "camera_angle": "elevated, wide angle looking northwest",
        "lot_layout": "entrance road on right, parking area on left",
        "landmarks": "curved entrance road, trees in background",
        "detection_tips": "This camera shows entrance area. Count trucks in parking rows, not on road."
    },
    "NY_TA_195": {
        "name": "I-87 NB Ardsley Service Area - Truck Park 1",
        "total_capacity": 16,
        "truck_spaces": 16,
        "camera_angle": "elevated, looking at parking rows",
        "lot_layout": "parallel parking rows for trucks, striped spaces",
        "landmarks": "snow piles at edges, trees in background",
        "detection_tips": "Count semi-truck trailers. Each trailer = 1 truck. Some may be cab-only (bobtail)."
    },
    "NY_TA_219": {
        "name": "I-87 SB Ramapo Service Area - Truck Park 2",
        "total_capacity": 20,
        "truck_spaces": 15,
        "car_spaces": 5,
        "camera_angle": "elevated overhead",
        "lot_layout": "mixed truck and car parking",
        "detection_tips": "Distinguish trucks (large rectangles 50+ ft) from cars (small rectangles). This lot has both."
    }
}

# Few-shot examples with verified counts (would come from labeled training data)
FEW_SHOT_EXAMPLES = """
EXAMPLE 1: Winter rest area, 3 trucks visible
- Three semi-trucks parked in rows (one white trailer, one red cab, one silver)
- Lot is approximately 15% occupied
- Snow on ground but parking area clear
- Analysis: truck_count=3, occupancy_percent=15

EXAMPLE 2: Service area, busy lot
- Eight semi-trucks visible in parking rows
- Mix of trailers and cab-only trucks
- Lot is approximately 65% occupied
- Cars also present but not counted as trucks
- Analysis: truck_count=8, occupancy_percent=65

EXAMPLE 3: Empty rest area
- No trucks visible in parking area
- Only 1-2 cars near building
- Lot is approximately 5% occupied
- Analysis: truck_count=0, occupancy_percent=5
"""

def build_rag_prompt(camera_id: str) -> str:
    """Build an enhanced prompt with RAG context for the specific camera."""
    
    site_info = SITE_KNOWLEDGE.get(camera_id, {})
    
    # Base prompt with site-specific context
    prompt = f"""You are analyzing a traffic camera image from a truck parking facility.

SITE INFORMATION:
- Location: {site_info.get('name', 'Unknown')}
- Total truck parking spaces: {site_info.get('truck_spaces', 'Unknown')}
- Camera angle: {site_info.get('camera_angle', 'Unknown')}
- Lot layout: {site_info.get('lot_layout', 'Unknown')}
- Key landmarks: {site_info.get('landmarks', 'Unknown')}

DETECTION GUIDANCE:
{site_info.get('detection_tips', 'Count semi-trucks/18-wheelers. Each trailer = 1 truck.')}

REFERENCE EXAMPLES:
{FEW_SHOT_EXAMPLES}

YOUR TASK:
Analyze this image and count:
1. Semi-trucks (trailers, not cars or small vehicles)
2. Estimate lot occupancy percentage

IMPORTANT COUNTING RULES:
- A semi-truck = large rectangular trailer (40-53 ft long)
- Bobtail trucks (cab only) count as trucks
- Cars, SUVs, and pickups do NOT count as trucks
- If unsure, err on the side of counting (better to overcount than miss)

Return your analysis as JSON:
{{
  "truck_count": <int>,
  "car_count": <int>,
  "occupancy_percent": <int based on {site_info.get('truck_spaces', 50)} total spaces>,
  "confidence": "<high/medium/low>",
  "notes": "<brief description of what you see>"
}}"""
    
    return prompt


def encode_image(image_path: str) -> str:
    """Encode image to base64."""
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def test_haiku_with_rag(image_path: str, camera_id: str):
    """Test Haiku with RAG-enhanced prompt."""
    
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set"}
    
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        image_data = encode_image(image_path)
        ext = Path(image_path).suffix.lower()
        media_type = "image/png" if ext == ".png" else "image/jpeg"
        
        # Get RAG-enhanced prompt
        rag_prompt = build_rag_prompt(camera_id)
        
        start_time = time.time()
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data
                        }
                    },
                    {
                        "type": "text",
                        "text": rag_prompt
                    }
                ]
            }]
        )
        elapsed = time.time() - start_time
        
        # Parse response
        text = response.content[0].text
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                result = json.loads(text[start:end])
            else:
                result = {"raw_response": text}
        except json.JSONDecodeError:
            result = {"raw_response": text}
        
        return {
            "model": "haiku-with-rag",
            "response_time_sec": round(elapsed, 2),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "result": result
        }
        
    except Exception as e:
        return {"error": str(e)}


def test_haiku_baseline(image_path: str):
    """Test Haiku with basic prompt (no RAG) for comparison."""
    
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set"}
    
    basic_prompt = """Analyze this traffic camera image from a rest area or truck parking location.

Count the semi-trucks/18-wheelers visible and estimate lot occupancy.

Return as JSON:
{
  "truck_count": <int>,
  "car_count": <int>,
  "occupancy_percent": <int>,
  "confidence": "<high/medium/low>",
  "notes": "<brief description>"
}"""
    
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        image_data = encode_image(image_path)
        ext = Path(image_path).suffix.lower()
        media_type = "image/png" if ext == ".png" else "image/jpeg"
        
        start_time = time.time()
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data
                        }
                    },
                    {
                        "type": "text",
                        "text": basic_prompt
                    }
                ]
            }]
        )
        elapsed = time.time() - start_time
        
        text = response.content[0].text
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                result = json.loads(text[start:end])
            else:
                result = {"raw_response": text}
        except json.JSONDecodeError:
            result = {"raw_response": text}
        
        return {
            "model": "haiku-baseline",
            "response_time_sec": round(elapsed, 2),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "result": result
        }
        
    except Exception as e:
        return {"error": str(e)}


def main():
    print("=" * 80)
    print("RAG-ENHANCED HAIKU vs BASELINE HAIKU COMPARISON")
    print("=" * 80)
    print()
    
    # Test images with known camera IDs
    test_cases = [
        ("test_cameras/MN_C30038.jpg", "MN_C30038"),
        ("test_cameras/MN_C30040.jpg", "MN_C30040"),
        ("test_cameras/NY_TA_195_truckpark.png", "NY_TA_195"),
        ("test_cameras/NY_TA_219_truckpark.png", "NY_TA_219"),
    ]
    
    results = []
    
    for img_path, camera_id in test_cases:
        if not Path(img_path).exists():
            print(f"Skipping {img_path} - file not found")
            continue
            
        print(f"\n{'='*80}")
        print(f"Testing: {camera_id}")
        print("=" * 80)
        
        # Test baseline Haiku
        print("\n  Haiku Baseline...")
        baseline = test_haiku_baseline(img_path)
        if "error" not in baseline:
            b_result = baseline.get('result', {})
            print(f"    Trucks: {b_result.get('truck_count', '?')}")
            print(f"    Occupancy: {b_result.get('occupancy_percent', '?')}%")
            print(f"    Tokens: {baseline.get('input_tokens', '?')} in")
        else:
            print(f"    Error: {baseline['error']}")
        
        # Test RAG-enhanced Haiku
        print("\n  Haiku with RAG...")
        rag = test_haiku_with_rag(img_path, camera_id)
        if "error" not in rag:
            r_result = rag.get('result', {})
            print(f"    Trucks: {r_result.get('truck_count', '?')}")
            print(f"    Occupancy: {r_result.get('occupancy_percent', '?')}%")
            print(f"    Tokens: {rag.get('input_tokens', '?')} in")
        else:
            print(f"    Error: {rag['error']}")
        
        results.append({
            "camera": camera_id,
            "baseline": baseline,
            "rag": rag
        })
    
    # Save results
    output_file = f"rag_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n\nResults saved to: {output_file}")
    
    # Summary
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    print(f"\n{'Camera':<20} {'Baseline Trucks':<18} {'RAG Trucks':<15} {'Baseline Tokens':<18} {'RAG Tokens':<15}")
    print("-" * 80)
    
    for r in results:
        cam = r['camera']
        b_trucks = r['baseline'].get('result', {}).get('truck_count', 'err')
        r_trucks = r['rag'].get('result', {}).get('truck_count', 'err')
        b_tokens = r['baseline'].get('input_tokens', 'err')
        r_tokens = r['rag'].get('input_tokens', 'err')
        print(f"{cam:<20} {str(b_trucks):<18} {str(r_trucks):<15} {str(b_tokens):<18} {str(r_tokens):<15}")


if __name__ == "__main__":
    main()
