import geopandas
import pandas as pd
from shapely.ops import nearest_points
from pyproj import Geod
import numpy as np

# Load pre-processed data
world_gdf = geopandas.read_file("world_countries.gpkg")
us_mexico_border_gdf = geopandas.read_file("us_mexico_border.gpkg")

# Ensure CRS is EPSG:4326 (latitude/longitude)
world_gdf = world_gdf.to_crs("EPSG:4326")
us_mexico_border_gdf = us_mexico_border_gdf.to_crs("EPSG:4326")

us_border_geom = us_mexico_border_gdf.geometry.iloc[0]

# Initialize Geod object for distance calculation (WGS84 ellipsoid)
geod = Geod(ellps="WGS84")

results = []

print(f"Calculating distances for {len(world_gdf)} countries...")

for index, country_row in world_gdf.iterrows():
    country_name = country_row['ADMIN']
    country_iso_a3 = country_row['ADM0_A3']
    country_geom = country_row['geometry']

    # print(f"Processing {country_name} ({country_iso_a3})...")

    # Calculate nearest points between the country's geometry and the US-Mexico border
    # nearest_points returns a tuple of the two nearest points (Point objects)
    # The first point is on the first geometry (country_geom), the second on the second (us_border_geom)
    try:
        p1, p2 = nearest_points(country_geom, us_border_geom)
    except Exception as e:
        print(f"Error calculating nearest points for {country_name}: {e}")
        # Add a placeholder or skip this country
        results.append({
            'Country Name': country_name,
            'ISO_A3': country_iso_a3,
            'Minimum Distance to US Southern Border (km)': np.nan,
            'Continent': country_row.get('CONTINENT', 'N/A')
        })
        continue

    # Calculate geodesic distance between these two points
    # geod.inv returns: forward azimuth, backward azimuth, distance in meters
    try:
        az12, az21, dist_meters = geod.inv(p1.x, p1.y, p2.x, p2.y)
        dist_km = dist_meters / 1000.0
    except Exception as e:
        print(f"Error calculating geodesic distance for {country_name} ({p1.wkt}, {p2.wkt}): {e}")
        dist_km = np.nan


    results.append({
        'Country Name': country_name,
        'ISO_A3': country_iso_a3,
        'Minimum Distance to US Southern Border (km)': dist_km,
        'Continent': country_row.get('CONTINENT', 'N/A') # Keep continent for next step
    })

    if (index + 1) % 20 == 0:
        print(f"Processed {index + 1}/{len(world_gdf)} countries...")

print("\nDistance calculation complete.")

# Create a DataFrame from the results
results_df = pd.DataFrame(results)

# Save results to a temporary CSV for the next step
results_df.to_csv("country_distances_and_continents.csv", index=False)
print("Intermediate results saved to country_distances_and_continents.csv")

print("\nSample of calculated distances:")
print(results_df.head())
