#!/usr/bin/env python3
"""
CV Model Testing for Truck Parking Availability
Tests Claude and Gemini models on traffic camera images.

Requirements:
    pip install anthropic google-generativeai pillow

Usage:
    export ANTHROPIC_API_KEY=your_key
    export GOOGLE_API_KEY=your_key
    python cv_parking_test.py
"""

import os
import sys
import json
import base64
import time
from pathlib import Path
from datetime import datetime

# Check for API keys
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_API_KEY')
GOOGLE_KEY = os.environ.get('GOOGLE_API_KEY')

PARKING_PROMPT = """Analyze this traffic camera image from a rest area or highway parking location.

Please provide:
1. **Truck Count**: How many semi-trucks/18-wheelers can you see parked or present?
2. **Car Count**: How many cars/small vehicles are visible?
3. **Parking Lot Visibility**: Can you see a parking lot? (yes/no)
4. **Estimated Occupancy**: If a parking lot is visible, estimate the percentage occupied (0-100%)
5. **Available Spaces**: Estimate the number of empty truck parking spaces visible
6. **Image Quality**: Rate the image quality for CV analysis (good/fair/poor)
7. **Weather/Visibility Issues**: Any fog, snow, darkness affecting visibility?
8. **Confidence**: How confident are you in your counts? (high/medium/low)

Return your analysis as JSON:
{
  "truck_count": <int>,
  "car_count": <int>,
  "parking_lot_visible": <bool>,
  "occupancy_percent": <int or null>,
  "available_truck_spaces": <int or null>,
  "image_quality": "<string>",
  "visibility_issues": "<string or null>",
  "confidence": "<string>",
  "notes": "<string>"
}"""


def encode_image(image_path):
    """Encode image to base64."""
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def test_claude(image_path, model="claude-sonnet-4-20250514"):
    """Test image with Claude model."""
    if not ANTHROPIC_KEY:
        return {"error": "ANTHROPIC_API_KEY not set"}
    
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        
        image_data = encode_image(image_path)
        
        # Determine media type
        ext = Path(image_path).suffix.lower()
        media_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"
        
        start_time = time.time()
        response = client.messages.create(
            model=model,
            max_tokens=1024,
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
                        "text": PARKING_PROMPT
                    }
                ]
            }]
        )
        elapsed = time.time() - start_time
        
        # Extract JSON from response
        text = response.content[0].text
        # Try to parse JSON from response
        try:
            # Find JSON in response
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                result = json.loads(text[start:end])
            else:
                result = {"raw_response": text}
        except json.JSONDecodeError:
            result = {"raw_response": text}
        
        return {
            "model": model,
            "response_time_sec": round(elapsed, 2),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "result": result
        }
        
    except Exception as e:
        return {"error": str(e)}


def test_gemini(image_path, model="gemini-2.0-flash"):
    """Test image with Gemini model."""
    if not GOOGLE_KEY:
        return {"error": "GOOGLE_API_KEY not set"}
    
    try:
        import google.generativeai as genai
        from PIL import Image
        
        genai.configure(api_key=GOOGLE_KEY)
        
        # Load image
        img = Image.open(image_path)
        
        start_time = time.time()
        model_obj = genai.GenerativeModel(model)
        response = model_obj.generate_content([PARKING_PROMPT, img])
        elapsed = time.time() - start_time
        
        # Extract JSON from response
        text = response.text
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
            "model": model,
            "response_time_sec": round(elapsed, 2),
            "result": result
        }
        
    except Exception as e:
        return {"error": str(e)}


def main():
    print("=" * 70)
    print("CV Model Testing for Truck Parking Availability")
    print("=" * 70)
    print()
    
    # Check API keys
    print("API Keys:")
    print(f"  ANTHROPIC_API_KEY: {'Set' if ANTHROPIC_KEY else 'NOT SET'}")
    print(f"  GOOGLE_API_KEY: {'Set' if GOOGLE_KEY else 'NOT SET'}")
    print()
    
    # Get test images
    test_dir = Path("test_cameras")
    if not test_dir.exists():
        print("Error: test_cameras directory not found")
        print("Run the camera download script first")
        sys.exit(1)
    
    images = list(test_dir.glob("*.jpg")) + list(test_dir.glob("*.png"))
    # Filter out manifest.json
    images = [img for img in images if img.suffix in ['.jpg', '.png']]
    print(f"Found {len(images)} test images")
    print()
    
    # Models to test
    claude_models = [
        "claude-sonnet-4-20250514",
        "claude-3-5-haiku-20241022",
    ]
    
    gemini_models = [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]
    
    results = []
    
    # Test each image with each model
    for img_path in images:  # Test all images
        print(f"\n{'='*70}")
        print(f"Testing: {img_path.name}")
        print("=" * 70)
        
        img_results = {
            "image": img_path.name,
            "timestamp": datetime.now().isoformat(),
            "models": {}
        }
        
        # Test Claude models
        if ANTHROPIC_KEY:
            for model in claude_models:
                print(f"\n  Testing {model}...")
                result = test_claude(str(img_path), model)
                img_results["models"][model] = result
                if "error" not in result:
                    print(f"    Response time: {result['response_time_sec']}s")
                    print(f"    Tokens: {result.get('input_tokens', '?')} in, {result.get('output_tokens', '?')} out")
                    if isinstance(result.get('result'), dict):
                        r = result['result']
                        print(f"    Trucks: {r.get('truck_count', '?')}, Occupancy: {r.get('occupancy_percent', '?')}%")
                else:
                    print(f"    Error: {result['error']}")
        
        # Test Gemini models
        if GOOGLE_KEY:
            for model in gemini_models:
                print(f"\n  Testing {model}...")
                result = test_gemini(str(img_path), model)
                img_results["models"][model] = result
                if "error" not in result:
                    print(f"    Response time: {result['response_time_sec']}s")
                    if isinstance(result.get('result'), dict):
                        r = result['result']
                        print(f"    Trucks: {r.get('truck_count', '?')}, Occupancy: {r.get('occupancy_percent', '?')}%")
                else:
                    print(f"    Error: {result['error']}")
        
        results.append(img_results)
    
    # Save results
    output_file = f"cv_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n\nResults saved to: {output_file}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if not ANTHROPIC_KEY and not GOOGLE_KEY:
        print("\nNo API keys set. To run tests:")
        print("  export ANTHROPIC_API_KEY=your_anthropic_key")
        print("  export GOOGLE_API_KEY=your_google_key")
        print("  python cv_parking_test.py")


if __name__ == "__main__":
    main()
