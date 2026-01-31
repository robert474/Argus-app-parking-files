# OpenStreetMap Truck Parking Data Extraction

## Overview
This guide shows how to extract US rest areas, service areas, and truck parking locations from OpenStreetMap using the Overpass API.

## Quick Start

### Step 1: Open Overpass Turbo
Go to: **https://overpass-turbo.eu/**

### Step 2: Run Queries

#### Query 1: US Rest Areas (no fuel)
```
[out:json][timeout:300];
(
  node["highway"="rest_area"](24.5,-125.0,49.5,-66.5);
  way["highway"="rest_area"](24.5,-125.0,49.5,-66.5);
);
out body center;
```

#### Query 2: US Service Areas (with fuel - toll plazas, truck stops)
```
[out:json][timeout:300];
(
  node["highway"="services"](24.5,-125.0,49.5,-66.5);
  way["highway"="services"](24.5,-125.0,49.5,-66.5);
);
out body center;
```

#### Query 3: Truck Parking (HGV designated)
```
[out:json][timeout:300];
(
  node["amenity"="parking"]["hgv"~"yes|designated|only"](24.5,-125.0,49.5,-66.5);
  way["amenity"="parking"]["hgv"~"yes|designated|only"](24.5,-125.0,49.5,-66.5);
);
out body center;
```

### Step 3: Export Data
1. Click **Run** (may take 1-3 minutes for large queries)
2. Click **Export** → **download as GeoJSON**
3. Save each file (e.g., `rest_areas.geojson`, `services.geojson`, `truck_parking.geojson`)

### Step 4: Process the Data
```bash
python osm_processor.py rest_areas.geojson services.geojson truck_parking.geojson
```

This creates:
- `osm_truck_parking_combined.csv` - All locations in CSV
- `osm_truck_parking_combined.xlsx` - Excel with formatted columns

---

## State-by-State Queries (Alternative)
For faster queries, use state bounding boxes:

### Texas Example
```
[out:json][timeout:180];
(
  node["highway"="rest_area"](25.8,-106.6,36.5,-93.5);
  way["highway"="rest_area"](25.8,-106.6,36.5,-93.5);
);
out body center;
```

### Common State Bounding Boxes
| State | Bounding Box (S,W,N,E) |
|-------|------------------------|
| California | 32.5,-124.5,42.0,-114.1 |
| Texas | 25.8,-106.6,36.5,-93.5 |
| Florida | 24.4,-87.6,31.0,-80.0 |
| Ohio | 38.4,-84.8,42.0,-80.5 |
| Illinois | 36.9,-91.5,42.5,-87.0 |
| Pennsylvania | 39.7,-80.5,42.3,-74.7 |
| New York | 40.5,-79.8,45.0,-71.8 |
| Georgia | 30.3,-85.6,35.0,-80.8 |
| Michigan | 41.7,-90.4,48.3,-82.4 |
| Indiana | 37.8,-88.1,41.8,-84.8 |

---

## Relevant OSM Tags

| Tag | Description | Expected Count (US) |
|-----|-------------|---------------------|
| `highway=rest_area` | Rest stops without fuel | ~2,000-3,000 |
| `highway=services` | Service areas WITH fuel | ~500-1,000 |
| `amenity=parking` + `hgv=yes` | Truck-designated parking | ~500-2,000 |
| `capacity:hgv=*` | Truck space count | Variable |

### Useful Amenity Sub-tags
- `toilets=yes` - Restrooms available
- `drinking_water=yes` - Water fountains
- `picnic_table=yes` - Picnic facilities
- `shelter=yes` - Covered areas
- `dump_station=yes` - RV dump (some trucks use)

---

## API Endpoint (Programmatic Access)

For scripts, POST directly to:
```
https://overpass-api.de/api/interpreter
```

Example with curl:
```bash
curl -X POST -d '[out:json][timeout:300];node["highway"="rest_area"](24.5,-125.0,49.5,-66.5);out body;' \
  https://overpass-api.de/api/interpreter > rest_areas.json
```

---

## Expected Data Fields

The processor extracts these fields from OSM:

| Field | Description |
|-------|-------------|
| osm_id | OpenStreetMap node/way ID |
| osm_type | node or way |
| name | Facility name (if tagged) |
| latitude | GPS latitude |
| longitude | GPS longitude |
| highway | rest_area, services, or null |
| amenity | parking (for truck lots) |
| hgv | yes/designated/only |
| capacity_hgv | Number of truck spaces |
| toilets | yes/no |
| drinking_water | yes/no |
| operator | Operating organization |
| ref | Reference number (state ID) |

---

## Combining with Other Data Sources

After processing OSM data, merge with:
1. **POI Factory** (3,032 locations) - More complete for traditional rest areas
2. **MAASTO TPIMS API** - Real-time availability for 8 Midwest states
3. **State 511 APIs** - Camera feeds and live data

OSM is best for:
- Filling gaps in other databases
- Truck parking capacity (`capacity:hgv`)
- Additional amenity details
- Cross-validation of GPS coordinates
