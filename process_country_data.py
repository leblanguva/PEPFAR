import geopandas
import pandas as pd

# Load the world countries dataset saved from the previous step
world_countries_gdf = geopandas.read_file("world_countries.gpkg")

# Ensure it's in EPSG:4326
world_countries_gdf = world_countries_gdf.to_crs("EPSG:4326")

# Relevant columns for the final dataset:
# - Country Name: 'ADMIN' (confirmed from previous step)
# - ISO A3 Code: 'ADM0_A3' (common in Natural Earth - let's verify)
# - Geometry: 'geometry' column (inherent in GeoDataFrame)
# - Continent: 'CONTINENT' (common in Natural Earth - let's verify)

print("Available columns in world_countries_gdf:", world_countries_gdf.columns)

# Verify expected columns exist, print unique values if needed for debugging
required_cols = ['ADMIN', 'ADM0_A3', 'CONTINENT', 'geometry']
missing_cols = [col for col in required_cols if col not in world_countries_gdf.columns]

if missing_cols:
    print(f"Missing expected columns: {missing_cols}")
    # Attempt to find alternatives or raise error
    if 'ADM0_A3' not in world_countries_gdf.columns and 'ISO_A3' in world_countries_gdf.columns:
        world_countries_gdf.rename(columns={'ISO_A3': 'ADM0_A3'}, inplace=True)
        print("Renamed 'ISO_A3' to 'ADM0_A3'")
    elif 'ADM0_A3' not in world_countries_gdf.columns and 'SOV_A3' in world_countries_gdf.columns:
        # SOV_A3 is for sovereign state, ADM0_A3 is for admin unit. ADM0_A3 is preferred.
        # If ADM0_A3 is missing, SOV_A3 might be an alternative but check for differences.
        # For now, let's assume ADM0_A3 should be there or an equivalent.
        # If critical and not found, this would be a point to raise an error or seek clarification.
        pass # Keep going, will fail later if ADM0_A3 is strictly needed and not found/renamed

    if 'CONTINENT' not in world_countries_gdf.columns and 'REGION_WB' in world_countries_gdf.columns:
         # REGION_WB gives broader regions, CONTINENT is more specific.
         # If CONTINENT is missing, this might affect land route logic.
        pass


# Select and rename columns for clarity if needed, though direct use is also fine.
# For this step, the main goal is to ensure we have the geometries and identifying info.
# The actual DataFrame for the final CSV will be constructed later.

# Print some info about the loaded data
print(f"\nLoaded {len(world_countries_gdf)} countries.")
print("Sample data (first 5 rows):")
print(world_countries_gdf[['ADMIN', 'ADM0_A3', 'CONTINENT']].head())

# At this point, `world_countries_gdf` contains the geometric representation (polygons/multipolygons)
# for each country, along with their names and ISO codes.
# The determination of landmass connection with the Americas will be part of the "Determine land route possibility" step.
# This step is primarily about loading and having the country representations ready.

print("\nCountry representation step complete. Data is loaded and basic column checks performed.")
