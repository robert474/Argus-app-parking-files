# Truck Parking Data - Developer Handoff

## Quick Start

### Immediate Data (Ready to Import)

| File | Records | Description |
|------|---------|-------------|
| `RestAreasCombined_USA (1).csv` | ~3,032 | POI Factory rest areas (all 50 states) |
| `overture_truck_parking.csv` | 227,948 | Overture Maps gas stations, truck stops, parking |
| `tpims_wi_static.json` | 14 | Wisconsin rest areas with GPS, capacity, cameras |
| `tpims_wi_dynamic.json` | 14 | Wisconsin real-time availability (sample) |

### Working APIs (No Authentication Required)

```bash
# Wisconsin TPIMS - Static (locations, capacity, camera URLs)
curl https://511wi.gov/api/TPIMS_Static

# Wisconsin TPIMS - Dynamic (real-time availability, updates every 1-5 min)
curl https://511wi.gov/api/TPIMS_Dynamic
```

---

## Data Source Details

### 1. POI Factory (3,032 rest areas)
- **File**: `RestAreasCombined_USA (1).csv`
- **Fields**: Name, Latitude, Longitude, Highway, Direction, Mile Marker, Amenities
- **Use**: Base layer for all public rest areas

### 2. Overture Maps (227,948 facilities)
- **Files**: `overture_truck_parking.csv`, `overture_truck_parking.geojson`
- **Categories**:
  - gas_station: 202,444
  - parking: 22,022
  - truck_gas_station: 3,020
  - truck_stop: 400
  - rest_stop: 33
  - rest_areas: 28
- **Script**: Run `python3 overture_truck_parking.py` to update

### 3. Wisconsin TPIMS (14 rest areas)
- **Static Feed**: GPS, capacity, amenities, camera URLs
- **Dynamic Feed**: Real-time spaces available, trend (FILLING/CLEARING/STEADY)
- **Poll Frequency**: Every 5 minutes recommended
- **Includes Minnesota**: St. Croix Travel Info Center with 3 camera URLs

---

## APIs Requiring Registration (Free)

### Ohio OHGO
- **Register**: https://publicapi.ohgo.com/
- **Endpoint**: `GET /api/v1/truck-parking?key={API_KEY}`
- **Coverage**: 16 rest areas on I-70, I-75
- **Rate Limit**: 25 requests/second

### New York 511
- **Register**: https://511ny.org/developers/resources
- **Endpoint**: `GET /api/gettruckparking?key={API_KEY}&format=json`
- **Coverage**: Rest areas across NY
- **Rate Limit**: 10 requests/minute

### Florida TPAS
- **Register**: https://fl511.com/developers
- **Coverage**: 74 interstate facilities with in-ground sensors
- **Technology**: Sensor-based (most accurate availability data)

---

## Camera Sources

### Wisconsin/Minnesota (from TPIMS Static)
```json
{
  "siteId": "MN00094IS0025580W0STCROIX",
  "name": "St. Croix Travel Info. Center",
  "images": [
    "https://video.dot.state.mn.us/video/image/metro/C30038",
    "https://video.dot.state.mn.us/video/image/metro/C30039",
    "https://video.dot.state.mn.us/video/image/metro/C30040"
  ]
}
```

### California (Caltrans)
- **URL**: https://cwwp2.dot.ca.gov/vm/streamlist.htm
- **Format**: RTSP stream URLs
- **Action**: Scrape page for stream URLs

---

## Recommended Implementation Order

### Phase 1: Import Static Data
1. Import `RestAreasCombined_USA (1).csv` → `rest_areas` table
2. Import `overture_truck_parking.csv` → `truck_facilities` table
3. Import `tpims_wi_static.json` → `tpims_locations` table

### Phase 2: Real-Time Feeds
1. Set up cron job to poll `https://511wi.gov/api/TPIMS_Dynamic` every 5 min
2. Store availability history for CV training data
3. Register for Ohio, NY, FL APIs and add polling

### Phase 3: Camera Integration
1. Extract camera URLs from Wisconsin static feed
2. Test accessibility from Argus infrastructure
3. Scrape Caltrans camera list
4. Prioritize cameras at high-traffic locations for CV

### Phase 4: Expand Coverage
1. Register for remaining state 511 APIs (MN, IN, IA, KS, KY, MI)
2. Integrate Truck Parking Club data when available
3. Run OSM queries for additional coverage (see `OSM_QUERIES_README.md`)

---

## Sample Code

### Fetch Wisconsin Real-Time Data (Python)
```python
import requests
import json

# Get real-time availability
response = requests.get('https://511wi.gov/api/TPIMS_Dynamic')
data = response.json()

for site in data:
    print(f"{site['siteId']}: {site['reportedAvailable']} spaces ({site['trend']})")
```

### Fetch Wisconsin Static Data (Python)
```python
import requests

# Get locations with camera URLs
response = requests.get('https://511wi.gov/api/TPIMS_Static')
data = response.json()

for site in data:
    print(f"{site['name']}")
    print(f"  Location: {site['location']['latitude']}, {site['location']['longitude']}")
    print(f"  Capacity: {site['capacity']}")
    if site.get('images') and site['images'][0]:
        print(f"  Cameras: {site['images']}")
```

---

## File Inventory

```
Rest Area APIs/
├── DEVELOPER_HANDOFF.md          # This file
├── Truck_Parking_Data_Sources.md # Full documentation
├── Truck_Parking_Data_Sources.xlsx # Spreadsheet with all sources
├── OSM_QUERIES_README.md         # OpenStreetMap extraction guide
├── osm_processor.py              # Process OSM exports
├── osm_sample_output.xlsx        # Sample OSM output format
├── overture_truck_parking.py     # Overture Maps extraction script
├── overture_truck_parking.csv    # Extracted Overture data (227K records)
├── overture_truck_parking.geojson # Extracted Overture data (GeoJSON)
├── RestAreasCombined_USA (1).csv # POI Factory rest areas (3K records)
├── tpims_wi_static.json          # Wisconsin locations + cameras
└── tpims_wi_dynamic.json         # Wisconsin real-time sample
```

---

## Contact/Support

- **TPIMS Documentation**: https://transportal.cee.wisc.edu/tpims/
- **Trucks Park Here**: https://trucksparkhere.com/
- **Ohio OHGO Support**: https://publicapi.ohgo.com/docs/terms-of-use
- **Wisconsin 511 Developers**: https://511wi.gov/developers/resources
