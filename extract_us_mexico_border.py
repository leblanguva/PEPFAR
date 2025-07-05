import geopandas
import pandas as pd
from shapely.ops import unary_union

# Load world dataset from the downloaded Natural Earth shapefile
try:
    world = geopandas.read_file("./natural_earth_countries/ne_110m_admin_0_countries.shp")
except Exception as e:
    print(f"Error reading shapefile: {e}")
    print("Please ensure 'ne_110m_admin_0_countries.shp' and its sidecar files are in './natural_earth_countries/'")
    exit()

# Ensure CRS is EPSG:4326 for consistency
world = world.to_crs("EPSG:4326")

# Print columns to identify the correct name field
print("World columns:", world.columns)

# Get USA and Mexico geometries
# Adjust 'name' if necessary based on printed columns. Common alternatives: 'ADMIN', 'SOVEREIGNT', 'NAME'
# For Natural Earth, 'ADMIN' or 'SOVEREIGNT' are likely candidates for full official names.
# Let's try 'ADMIN' first as it's common for administrative unit names.
# The specific string for "United States of America" might also vary.
# We can print unique names to check: print(world['ADMIN'].unique())
try:
    usa_geom_series = world[world['ADMIN'] == 'United States of America'].geometry
    if usa_geom_series.empty:
        # Try another common name field or a variant of the name
        print("Couldn't find 'United States of America' in 'ADMIN'. Trying 'NAME' or 'SOVEREIGNT' or checking unique values...")
        # Example: print some unique values to help identify the correct name and field
        # if 'NAME' in world.columns: print(f"Unique values in NAME: {world['NAME'].unique()[:20]}")
        # if 'SOVEREIGNT' in world.columns: print(f"Unique values in SOVEREIGNT: {world['SOVEREIGNT'].unique()[:20]}")

        # Based on common Natural Earth Data field names:
        name_field_to_try = None
        if 'NAME' in world.columns and len(world[world['NAME'] == 'United States of America']) > 0:
            name_field_to_try = 'NAME'
        elif 'SOVEREIGNT' in world.columns and len(world[world['SOVEREIGNT'] == 'United States of America']) > 0:
            name_field_to_try = 'SOVEREIGNT'
        elif 'ADMIN' in world.columns: # If ADMIN was tried but name was different, maybe just "United States"
             if len(world[world['ADMIN'] == 'United States']) > 0:
                 usa_geom_series = world[world['ADMIN'] == 'United States'].geometry
             elif 'NAME_EN' in world.columns and len(world[world['NAME_EN'] == 'United States of America']) > 0:
                 name_field_to_try = 'NAME_EN'


        if name_field_to_try:
             usa_geom_series = world[world[name_field_to_try] == 'United States of America'].geometry

        if usa_geom_series.empty: # Final check if still empty
            # Fallback to checking for 'United States' in common fields if 'United States of America' fails
            if 'ADMIN' in world.columns and len(world[world['ADMIN'] == 'United States']) > 0:
                 usa_geom_series = world[world['ADMIN'] == 'United States'].geometry
            elif 'NAME' in world.columns and len(world[world['NAME'] == 'United States']) > 0:
                 usa_geom_series = world[world['NAME'] == 'United States'].geometry
            elif 'SOVEREIGNT' in world.columns and len(world[world['SOVEREIGNT'] == 'United States']) > 0:
                 usa_geom_series = world[world['SOVEREIGNT'] == 'United States'].geometry

            if usa_geom_series.empty:
                 raise ValueError("Could not find 'United States of America' or 'United States' in common name fields (ADMIN, NAME, SOVEREIGNT, NAME_EN). Please inspect columns and unique values.")

    usa = usa_geom_series.iloc[0]

    # For Mexico, 'ADMIN' or 'NAME' should be 'Mexico'
    mexico_name_field = 'ADMIN' # Default assumption
    if 'ADMIN' not in world.columns or world[world['ADMIN'] == 'Mexico'].empty:
        if 'NAME' in world.columns and not world[world['NAME'] == 'Mexico'].empty:
            mexico_name_field = 'NAME'
        elif 'SOVEREIGNT' in world.columns and not world[world['SOVEREIGNT'] == 'Mexico'].empty:
            mexico_name_field = 'SOVEREIGNT'
        elif 'NAME_EN' in world.columns and not world[world['NAME_EN'] == 'Mexico'].empty:
            mexico_name_field = 'NAME_EN'
        else:
            raise ValueError("Could not find 'Mexico' in common name fields.")

    mexico = world[world[mexico_name_field] == 'Mexico'].geometry.iloc[0]

except IndexError:
    raise ValueError("Country not found. Check column names and unique values for country identification.")
except Exception as e:
    raise e


# Find the intersection (shared border)
# Buffer by a very small amount to handle potential precision issues if they are perfectly touching
# but not overlapping, then take the intersection of the buffered geometries.
# Then, intersect this with the original geometries to get the actual line.
# A simpler approach that often works is direct intersection if geometries are clean.
shared_border = usa.intersection(mexico)

# The intersection might be a collection of lines if there are multiple segments (e.g., islands)
# We are interested in the main land border.
# If it's a GeometryCollection, iterate and find the longest LineString
if shared_border.geom_type == 'GeometryCollection':
    lines = [geom for geom in shared_border.geoms if geom.geom_type == 'LineString']
    if not lines:
        raise ValueError("No LineString found in the intersection of USA and Mexico.")
    # Sort by length and take the longest, assuming it's the main border
    lines.sort(key=lambda x: x.length, reverse=True)
    us_mexico_border = lines[0]
elif shared_border.geom_type == 'LineString':
    us_mexico_border = shared_border
elif shared_border.geom_type == 'MultiLineString':
    # If it's a MultiLineString, take the longest segment or unify them if appropriate
    # For simplicity, let's take the longest one as the primary border segment
    lines = list(shared_border.geoms)
    lines.sort(key=lambda x: x.length, reverse=True)
    if not lines:
        raise ValueError("No LineString found in the MultiLineString intersection of USA and Mexico.")
    us_mexico_border = lines[0] # Or unary_union(lines) if all segments are desired and contiguous
else:
    raise ValueError(f"Unexpected geometry type for shared border: {shared_border.geom_type}")

# For the US southern border, we are specifically interested in the part of the US
# boundary that touches Mexico. The `us_mexico_border` derived above is exactly this.

# Save the border to a new GeoJSON file (optional, for inspection)
# border_gdf = geopandas.GeoDataFrame([{'geometry': us_mexico_border, 'id': 1}], crs="EPSG:4326")
# border_gdf.to_file("us_mexico_border.geojson", driver="GeoJSON")

print(f"US-Mexico border extracted successfully: {us_mexico_border.wkt[:100]}...")

# This script defines the US southern border with Mexico.
# We can now consider this step complete for the plan.
# The variable `us_mexico_border` holds the Shapely geometry.
# For the next steps, this geometry will be used.
# We'll also need all country geometries from the 'world' GeoDataFrame.

# Store the border and world data for the next script (if running in separate steps)
# For this agent, we'll just keep them in memory for the next python script execution if possible,
# or reload them. Given the agent structure, each python script is likely independent.
# So, the next script will need to re-load 'world' and re-calculate 'us_mexico_border'.
# To avoid recalculation, we could save it to a file and load it in the next step.
# Let's save it for robustness.
us_mexico_border_gdf = geopandas.GeoDataFrame(geometry=[us_mexico_border], crs="EPSG:4326")
us_mexico_border_gdf.to_file("us_mexico_border.gpkg", driver="GPKG")
print("US-Mexico border saved to us_mexico_border.gpkg")

world.to_file("world_countries.gpkg", driver="GPKG")
print("World countries saved to world_countries.gpkg")
