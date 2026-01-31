#!/usr/bin/env python3
"""
Overture Maps Truck Parking Extractor
Extracts rest areas, truck stops, and parking facilities from Overture Maps Places theme.

Requirements:
    pip install duckdb

Usage:
    python overture_truck_parking.py

Output:
    overture_truck_parking.csv
    overture_truck_parking.geojson (if spatial extension works)
"""

import os
import sys

try:
    import duckdb
except ImportError:
    print("Error: duckdb not installed")
    print("Install with: pip install duckdb")
    sys.exit(1)

# Overture Maps release (latest as of Jan 2026)
RELEASE = "2026-01-21.0"
S3_BASE = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=places/type=place/*"

# Categories we want (from Overture taxonomy)
TARGET_CATEGORIES = [
    'rest_areas',
    'rest_stop', 
    'truck_stop',
    'truck_gas_station',
    'parking',
    'gas_station',  # Some are truck stops
    'toll_stations'  # May have parking
]

# US bounding box (continental)
US_BBOX = {
    'min_lon': -125.0,
    'max_lon': -66.5,
    'min_lat': 24.5,
    'max_lat': 49.5
}


def extract_truck_parking():
    """Extract truck parking facilities from Overture Maps."""
    
    print("Connecting to Overture Maps data on S3...")
    print(f"Release: {RELEASE}")
    print(f"Target categories: {TARGET_CATEGORIES}")
    print()
    
    con = duckdb.connect()
    
    # Install and load required extensions
    print("Loading DuckDB extensions...")
    con.execute("INSTALL httpfs;")
    con.execute("LOAD httpfs;")
    con.execute("SET s3_region='us-west-2';")
    
    # Try to load spatial extension for GeoJSON export
    has_spatial = False
    try:
        con.execute("INSTALL spatial;")
        con.execute("LOAD spatial;")
        has_spatial = True
        print("Spatial extension loaded (GeoJSON export available)")
    except:
        print("Spatial extension not available (CSV only)")
    
    print()
    print("Querying Overture Maps Places theme...")
    print("This may take a few minutes for the full US...")
    print()
    
    # Build category filter
    category_filter = " OR ".join([f"categories.primary = '{cat}'" for cat in TARGET_CATEGORIES])
    
    # Query for US truck parking facilities
    query = f"""
    SELECT 
        id,
        names.primary as name,
        categories.primary as category,
        categories.alternate as alt_categories,
        addresses[1].freeform as address,
        addresses[1].locality as city,
        addresses[1].region as state,
        addresses[1].postcode as zip,
        phones[1] as phone,
        websites[1] as website,
        ST_Y(geometry) as latitude,
        ST_X(geometry) as longitude,
        sources[1].dataset as source_dataset,
        sources[1].record_id as source_id
    FROM read_parquet('{S3_BASE}', filename=true, hive_partitioning=true)
    WHERE 
        bbox.xmin >= {US_BBOX['min_lon']}
        AND bbox.xmax <= {US_BBOX['max_lon']}
        AND bbox.ymin >= {US_BBOX['min_lat']}
        AND bbox.ymax <= {US_BBOX['max_lat']}
        AND ({category_filter})
    ORDER BY state, category, name
    """
    
    try:
        result = con.execute(query)
        df = result.fetchdf()
        
        print(f"Found {len(df)} facilities")
        print()
        
        # Summary by category
        print("Breakdown by category:")
        for cat in df['category'].value_counts().items():
            print(f"  {cat[0]}: {cat[1]}")
        print()
        
        # Summary by state
        print("Top 10 states by count:")
        for state in df['state'].value_counts().head(10).items():
            print(f"  {state[0]}: {state[1]}")
        print()
        
        # Save to CSV
        csv_path = 'overture_truck_parking.csv'
        df.to_csv(csv_path, index=False)
        print(f"Saved: {csv_path}")
        
        # Save to GeoJSON if spatial available
        if has_spatial:
            geojson_query = f"""
            COPY (
                SELECT 
                    id,
                    names.primary as name,
                    categories.primary as category,
                    addresses[1].locality as city,
                    addresses[1].region as state,
                    geometry
                FROM read_parquet('{S3_BASE}', filename=true, hive_partitioning=true)
                WHERE 
                    bbox.xmin >= {US_BBOX['min_lon']}
                    AND bbox.xmax <= {US_BBOX['max_lon']}
                    AND bbox.ymin >= {US_BBOX['min_lat']}
                    AND bbox.ymax <= {US_BBOX['max_lat']}
                    AND ({category_filter})
            ) TO 'overture_truck_parking.geojson' 
            WITH (FORMAT GDAL, DRIVER 'GeoJSON');
            """
            try:
                con.execute(geojson_query)
                print("Saved: overture_truck_parking.geojson")
            except Exception as e:
                print(f"GeoJSON export failed: {e}")
        
        return df
        
    except Exception as e:
        print(f"Query failed: {e}")
        print()
        print("If you're seeing S3 errors, try running the query manually in DuckDB CLI")
        return None
    
    finally:
        con.close()


def main():
    print("=" * 60)
    print("Overture Maps Truck Parking Extractor")
    print("=" * 60)
    print()
    
    df = extract_truck_parking()
    
    if df is not None and len(df) > 0:
        print()
        print("Sample records:")
        print(df[['name', 'category', 'city', 'state', 'latitude', 'longitude']].head(10).to_string())


if __name__ == '__main__':
    main()
