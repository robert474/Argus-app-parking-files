#!/usr/bin/env python3
"""
Truck Parking CV Training Pipeline

CONCEPT:
1. Use Opus (highest accuracy) to label 200+ images with detailed analysis
2. Store labels in a knowledge base per camera site
3. Use this knowledge base to enhance Haiku prompts during production
4. Result: Haiku accuracy approaches Opus at 1/30th the cost

PIPELINE:
Phase 1: TRAINING (one-time, using Opus)
- Collect 200 images across different cameras, times, occupancy levels
- Use Opus to analyze each with detailed counting
- Store: camera_id, timestamp, truck_count, occupancy, weather, notes
- Build per-site statistics (avg occupancy by time, typical patterns)

Phase 2: PRODUCTION (ongoing, using Haiku)
- For each scan, retrieve relevant context from training data
- Include: site capacity, similar historical images, detection tips
- Haiku produces counts informed by Opus's "expertise"

COST ANALYSIS:
- Training: 200 images × $0.015/image (Opus) = $3.00 one-time
- Production: 1M images × $0.0001/image (Haiku) = $100/month
- vs Sonnet: 1M images × $0.004/image = $4,000/month
"""

import os
import json
import base64
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Training configuration
TRAINING_CONFIG = {
    "model": "claude-opus-4-20250514",  # Best accuracy for labeling
    "images_per_site": 20,  # Collect 20 images per camera over time
    "target_sites": 10,  # Start with 10 representative cameras
    "total_training_images": 200
}

# Production configuration  
PRODUCTION_CONFIG = {
    "model": "claude-3-5-haiku-20241022",  # Fast and cheap for scanning
    "context_examples": 3,  # Include 3 similar examples from training
}


def get_opus_training_prompt() -> str:
    """Detailed prompt for Opus to generate high-quality training labels."""
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


def get_haiku_production_prompt(site_knowledge: Dict, similar_examples: List[Dict]) -> str:
    """Build production prompt for Haiku with training context."""
    
    # Format similar examples
    examples_text = ""
    for i, ex in enumerate(similar_examples[:3], 1):
        examples_text += f"""
Example {i} (similar conditions):
- Truck count: {ex.get('truck_count', '?')}
- Occupancy: {ex.get('occupancy_percent', '?')}%
- Notes: {ex.get('detailed_notes', 'N/A')[:100]}
"""
    
    return f"""Analyze this truck parking camera image.

SITE INFO (from training data):
- Location: {site_knowledge.get('name', 'Unknown')}
- Typical capacity: {site_knowledge.get('avg_capacity', '?')} trucks
- Average occupancy: {site_knowledge.get('avg_occupancy', '?')}%
- Detection tips: {site_knowledge.get('detection_tips', 'Count semi-truck trailers')}

REFERENCE EXAMPLES FROM THIS CAMERA:
{examples_text}

COUNT TRUCKS CAREFULLY:
- Semi-trucks (trailers) only, not cars
- If similar to examples above, expect similar counts

Return JSON:
{{
  "truck_count": <int>,
  "occupancy_percent": <int>,
  "confidence": "<high/medium/low>"
}}"""


class TrainingPipeline:
    """Manages the training data collection and storage."""
    
    def __init__(self, data_dir: str = "training_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.labels_file = self.data_dir / "labels.json"
        self.site_stats_file = self.data_dir / "site_stats.json"
        self.labels = self._load_labels()
        
    def _load_labels(self) -> Dict:
        if self.labels_file.exists():
            with open(self.labels_file) as f:
                return json.load(f)
        return {"images": [], "sites": {}}
    
    def _save_labels(self):
        with open(self.labels_file, "w") as f:
            json.dump(self.labels, f, indent=2)
    
    def label_image_with_opus(self, image_path: str, camera_id: str) -> Optional[Dict]:
        """Use Opus to create a high-quality label for an image."""
        
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            print("Error: ANTHROPIC_API_KEY not set")
            return None
        
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            
            # Encode image
            with open(image_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")
            
            ext = Path(image_path).suffix.lower()
            media_type = "image/png" if ext == ".png" else "image/jpeg"
            
            print(f"  Labeling with Opus: {image_path}")
            start_time = time.time()
            
            response = client.messages.create(
                model=TRAINING_CONFIG["model"],
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
                            "text": get_opus_training_prompt()
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
                label = json.loads(text[start:end])
            except:
                label = {"raw_response": text, "parse_error": True}
            
            # Add metadata
            label["camera_id"] = camera_id
            label["image_path"] = str(image_path)
            label["labeled_at"] = datetime.now().isoformat()
            label["labeling_time_sec"] = round(elapsed, 2)
            label["input_tokens"] = response.usage.input_tokens
            label["output_tokens"] = response.usage.output_tokens
            
            # Store
            self.labels["images"].append(label)
            self._save_labels()
            
            print(f"    Trucks: {label.get('truck_count', '?')}, Time: {elapsed:.1f}s")
            
            return label
            
        except Exception as e:
            print(f"    Error: {e}")
            return None
    
    def compute_site_statistics(self):
        """Compute per-site statistics from training labels."""
        
        site_stats = {}
        
        for label in self.labels["images"]:
            camera_id = label.get("camera_id")
            if not camera_id:
                continue
            
            if camera_id not in site_stats:
                site_stats[camera_id] = {
                    "samples": [],
                    "name": camera_id,
                }
            
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
                stats["avg_occupancy"] = sum(occupancies) / len(occupancies) if occupancies else 0
                stats["sample_count"] = len(samples)
                
                # Detection tips based on observations
                all_notes = " ".join([s.get("detailed_notes", "") for s in samples])
                if "snow" in all_notes.lower():
                    stats["detection_tips"] = "Winter conditions common. Look for truck shapes despite snow."
                else:
                    stats["detection_tips"] = "Standard detection. Count trailer rectangles."
        
        self.labels["sites"] = site_stats
        self._save_labels()
        
        # Also save separate stats file
        with open(self.site_stats_file, "w") as f:
            json.dump(site_stats, f, indent=2)
        
        return site_stats
    
    def get_similar_examples(self, camera_id: str, n: int = 3) -> List[Dict]:
        """Get similar labeled examples for a camera."""
        
        site_data = self.labels.get("sites", {}).get(camera_id, {})
        samples = site_data.get("samples", [])
        
        # Return most recent n samples
        return samples[-n:] if samples else []
    
    def get_site_knowledge(self, camera_id: str) -> Dict:
        """Get aggregated knowledge about a site."""
        
        site_data = self.labels.get("sites", {}).get(camera_id, {})
        
        return {
            "name": site_data.get("name", camera_id),
            "avg_capacity": site_data.get("max_truck_count", "Unknown"),
            "avg_occupancy": round(site_data.get("avg_occupancy", 0)),
            "detection_tips": site_data.get("detection_tips", "Count semi-truck trailers"),
            "sample_count": site_data.get("sample_count", 0),
        }


def run_training_collection():
    """Collect training labels using Opus."""
    
    pipeline = TrainingPipeline()
    
    # Get test images
    test_dir = Path("test_cameras")
    images = list(test_dir.glob("*.jpg")) + list(test_dir.glob("*.png"))
    
    print("=" * 80)
    print("TRAINING DATA COLLECTION WITH OPUS")
    print("=" * 80)
    print(f"\nFound {len(images)} images to label")
    print()
    
    for img_path in images:
        # Extract camera ID from filename
        camera_id = img_path.stem.split("_")[0] + "_" + img_path.stem.split("_")[1]
        if "truckpark" in img_path.stem:
            camera_id = "_".join(img_path.stem.split("_")[:3])
        
        pipeline.label_image_with_opus(str(img_path), camera_id)
        time.sleep(1)  # Rate limiting
    
    # Compute statistics
    print("\nComputing site statistics...")
    stats = pipeline.compute_site_statistics()
    
    print("\n" + "=" * 80)
    print("TRAINING COMPLETE")
    print("=" * 80)
    print(f"\nLabeled {len(pipeline.labels['images'])} images")
    print(f"Sites: {list(stats.keys())}")
    
    for site, data in stats.items():
        print(f"\n{site}:")
        print(f"  Samples: {data.get('sample_count', 0)}")
        print(f"  Avg trucks: {data.get('avg_truck_count', 0):.1f}")
        print(f"  Max trucks: {data.get('max_truck_count', 0)}")


def test_production_with_training():
    """Test Haiku with training context."""
    
    pipeline = TrainingPipeline()
    
    if not pipeline.labels.get("images"):
        print("No training data found. Run training first.")
        return
    
    print("=" * 80)
    print("TESTING HAIKU WITH TRAINING CONTEXT")
    print("=" * 80)
    
    # Test on a few images
    test_images = [
        ("test_cameras/MN_C30038.jpg", "MN_C30038"),
        ("test_cameras/NY_TA_195_truckpark.png", "NY_TA_195"),
    ]
    
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return
    
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    
    for img_path, camera_id in test_images:
        if not Path(img_path).exists():
            continue
        
        print(f"\nTesting: {camera_id}")
        
        # Get training context
        site_knowledge = pipeline.get_site_knowledge(camera_id)
        similar_examples = pipeline.get_similar_examples(camera_id)
        
        print(f"  Site knowledge: {site_knowledge}")
        print(f"  Similar examples: {len(similar_examples)}")
        
        # Build prompt
        prompt = get_haiku_production_prompt(site_knowledge, similar_examples)
        
        # Encode image
        with open(img_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        ext = Path(img_path).suffix.lower()
        media_type = "image/png" if ext == ".png" else "image/jpeg"
        
        # Call Haiku
        response = client.messages.create(
            model=PRODUCTION_CONFIG["model"],
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        
        print(f"  Haiku response: {response.content[0].text[:200]}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "train":
        run_training_collection()
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        test_production_with_training()
    else:
        print("Usage:")
        print("  python cv_training_pipeline.py train  - Collect training labels with Opus")
        print("  python cv_training_pipeline.py test   - Test Haiku with training context")
