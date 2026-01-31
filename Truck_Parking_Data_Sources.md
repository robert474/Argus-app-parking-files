# Truck Parking Data Sources for Argus AI

## Executive Summary

This document catalogs public data sources for truck parking facilities across the US. These sources complement your Truck Parking Club partnership (commercial truck stops) with public infrastructure: state rest areas, welcome centers, weigh stations, and service plazas.

---

## Priority 1: Immediate Wins (Download Today)

### POI Factory - US Rest Areas Database
- **URL**: https://www.poi-factory.com/node/21138
- **Coverage**: 3,032 locations across all 50 states
- **Format**: CSV/GPX download (free account required)
- **Data includes**: GPS coordinates, amenities, mile markers, highway, direction
- **Update frequency**: Community-maintained (frequent updates)
- **Action**: Download CSV, import to database

### MAASTO TPIMS API (8 Midwest States)
- **States**: Indiana, Iowa, Kansas, Kentucky, Michigan, Minnesota, Ohio, Wisconsin
- **Static endpoint**: `https://data.trucking.org/tpims/d/staticTpimsFeed.json`
- **Dynamic endpoint**: `https://data.trucking.org/tpims/d/dynamicTpimsFeed.json`
- **Data includes**:
  - GPS locations, capacity, amenities (static)
  - Real-time availability, updated every 1-5 min (dynamic)
  - Camera URLs where available (`images` array in static feed)
- **Format**: JSON
- **Spec doc**: https://transportal.cee.wisc.edu/tpims/TPIMS_TruckParking_Data_Interface_V2.2.pdf
- **Action**: Set up API ingestion, poll dynamic feed for training data

### Overture Maps Foundation (EXTRACTED)
- **URL**: https://overturemaps.org/
- **Coverage**: 227,948 US facilities (gas stations, truck stops, parking, rest areas)
- **Format**: CSV and GeoJSON (already extracted - see `overture_truck_parking.csv`)
- **Data includes**: GPS, name, category, address, city, state, phone, website
- **Categories extracted**:
  - gas_station: 202,444
  - parking: 22,022
  - truck_gas_station: 3,020
  - truck_stop: 400
  - rest_stop: 33
  - rest_areas: 28
- **Source**: Meta, Microsoft, TomTom, Amazon collaboration
- **Files**: `overture_truck_parking.csv`, `overture_truck_parking.geojson`
- **Script**: `overture_truck_parking.py` (re-run to update)

### OpenStreetMap (Supplementary)
- **Coverage**: Variable (community-mapped), ~2,000-5,000 truck-relevant POIs
- **Access**: Overpass API (free)
- **Data includes**: GPS, truck capacity (capacity:hgv), amenities, operator
- **Use case**: Fill gaps, validate other sources, get truck space counts
- **Action**: Run Overpass queries (see OSM_QUERIES_README.md)

---

## Priority 2: State-Specific APIs

### Florida TPAS (Truck Parking Availability System)
- **Coverage**: 74 facilities across all Florida interstates
- **URL**: Register at https://fl511.com/developers
- **Technology**: In-ground sensors (not just cameras)
- **Data includes**: Real-time space availability, GPS, capacity
- **Action**: Register for API access

### State 511 APIs with Camera Feeds

| State | API Registration | Camera Data | Notes |
|-------|-----------------|-------------|-------|
| Wisconsin | 511wi.gov/developers | Yes | Part of TPIMS |
| New York | 511ny.org/developers | Yes | Extensive coverage |
| Georgia | 511ga.org/developers | Yes | I-75, I-85, I-20 |
| Arizona | az511.gov/developers | Yes | I-10, I-40 |
| California | cwwp2.dot.ca.gov/vm/streamlist.htm | Yes | Direct stream URLs |
| Texas | drivetexas.org | Yes | Major corridors |
| Pennsylvania | 511pa.com | Yes | I-80, I-76 turnpike |

### Caltrans Camera Feed (California)
- **URL**: https://cwwp2.dot.ca.gov/vm/streamlist.htm
- **Format**: Direct RTSP/HTTP stream URLs
- **Coverage**: All Caltrans-monitored rest areas
- **Action**: Scrape URL list, test stream accessibility

---

## Priority 3: Federal Data Sources

### FHWA Jason's Law Survey Data
- **URL**: https://ops.fhwa.dot.gov/freight/infrastructure/truck_parking/
- **Coverage**: National survey of truck parking capacity
- **Data includes**: Capacity by state, shortage analysis
- **Use case**: Baseline capacity numbers, gap analysis
- **Format**: PDF reports, some Excel

### National Highway Freight Network (NHFN)
- **URL**: https://ops.fhwa.dot.gov/freight/infrastructure/nfn/
- **Use case**: Identify priority corridors for coverage
- **Format**: GIS shapefiles

---

## Data Schema for Argus Database

Recommended schema combining all sources:

```sql
CREATE TABLE truck_parking_facilities (
    id UUID PRIMARY KEY,

    -- Location
    name VARCHAR(255),
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    highway VARCHAR(50),
    direction VARCHAR(10),  -- NB, SB, EB, WB
    mile_marker DECIMAL(6, 1),
    state VARCHAR(2),
    city VARCHAR(100),

    -- Facility Type
    facility_type VARCHAR(50),  -- rest_area, welcome_center, weigh_station, service_plaza, truck_stop
    operator VARCHAR(100),  -- State DOT, Turnpike Authority, Private

    -- Capacity
    truck_spaces INTEGER,
    car_spaces INTEGER,

    -- Amenities
    has_restrooms BOOLEAN,
    has_fuel BOOLEAN,
    has_food BOOLEAN,
    has_showers BOOLEAN,
    has_wifi BOOLEAN,
    is_24_hours BOOLEAN,

    -- Camera/Availability
    has_camera BOOLEAN,
    camera_url VARCHAR(500),
    camera_type VARCHAR(20),  -- still, video, stream
    has_sensors BOOLEAN,
    tpims_site_id VARCHAR(50),  -- For API-connected sites

    -- Metadata
    data_source VARCHAR(50),  -- poi_factory, tpims, osm, state_dot, truck_parking_club
    source_id VARCHAR(100),  -- Original ID from source
    last_verified TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Real-time availability (for TPIMS/TPAS connected sites)
CREATE TABLE parking_availability (
    facility_id UUID REFERENCES truck_parking_facilities(id),
    timestamp TIMESTAMP NOT NULL,
    spaces_available INTEGER,
    spaces_occupied INTEGER,
    occupancy_pct DECIMAL(5, 2),
    trend VARCHAR(10),  -- filling, emptying, stable
    source VARCHAR(20),  -- tpims, tpas, cv_model
    confidence DECIMAL(3, 2),  -- For CV predictions
    PRIMARY KEY (facility_id, timestamp)
);
```

---

## Integration Strategy

### Phase 1: Build POI Database
1. Download POI Factory CSV → import as base layer
2. Run OSM queries → merge unique locations
3. Pull TPIMS static feed → add Midwest facilities with camera URLs
4. Result: Comprehensive GPS database of all public facilities

### Phase 2: Add Real-Time Feeds
1. Set up TPIMS dynamic feed polling (every 5 min)
2. Register for Florida TPAS API
3. Register for state 511 APIs
4. Store availability data for CV model training

### Phase 3: Camera Integration
1. Extract camera URLs from TPIMS `images` array
2. Scrape Caltrans stream list
3. Test accessibility from Argus infrastructure
4. Prioritize working feeds for CV model

### Phase 4: CV Expansion
1. Train CV model on TPIMS-labeled data (sensor ground truth)
2. Deploy CV to camera-only locations
3. Expand coverage beyond TPIMS states
4. Differentiate from competitors (crowdsourced data)

---

## Competitive Advantage

| Competitor | Data Source | Update Frequency |
|------------|-------------|------------------|
| Trucker Path | Crowdsourced | User-reported |
| TruckPark | Commercial partnerships | Periodic |
| Park My Truck | Commercial + some public | Mixed |
| **Argus AI** | TPIMS sensors + DOT cameras + CV | **Real-time** |

By combining:
- **Truck Parking Club** (commercial truck stops)
- **TPIMS/TPAS APIs** (8+ states with sensors)
- **State DOT cameras** (additional states via CV)
- **CV model** (expand to any camera)

Argus can offer the most accurate real-time availability for both commercial AND public facilities.

---

## Next Steps

- [ ] Download POI Factory CSV
- [ ] Run OSM Overpass queries
- [ ] Test TPIMS API endpoints
- [ ] Register for FL511 developer access
- [ ] Inventory state 511 camera APIs
- [ ] Design database schema (see above)
- [ ] Build API ingestion pipeline
