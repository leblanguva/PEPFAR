import pandas as pd
import geopandas

# Load the intermediate data (distances and continents)
df = pd.read_csv("country_distances_and_continents.csv")

# Load the full world geodataframe to get geometry information for island check
world_gdf = geopandas.read_file("world_countries.gpkg")
world_gdf = world_gdf.to_crs("EPSG:4326") # Ensure consistent CRS

# Merge to get geometries into the results dataframe, matching on ISO_A3 or Name
# ADM0_A3 is the ISO code column in world_gdf
df = pd.merge(df, world_gdf[['ADM0_A3', 'geometry']], left_on='ISO_A3', right_on='ADM0_A3', how='left')
# Drop the redundant ADM0_A3 column if it was added
if 'ADM0_A3_y' in df.columns:
    df.drop(columns=['ADM0_A3_y'], inplace=True)
    df.rename(columns={'ADM0_A3_x': 'ADM0_A3'}, inplace=True)


# Define American continents
american_continents = ['North America', 'South America']

# --- Sophisticated Island Check ---
# A country is an island if none of its constituent polygons touch any other country's polygons
# within the American continents. This is a bit complex.
# A simpler proxy for "not an island" for this context:
# - If it's on an American continent AND
# - It shares a land border with ANY other country OR it IS the USA, Canada, or Mexico (mainland)
#
# Simpler approach based on user feedback: "if the country is in north or south america and is not an island"
# How to define "is not an island" robustly without complex topology checks or external lists?
#
# 1. Check if it's USA, Canada, or Mexico - these are definitely land-connected to the border.
# 2. For other countries in North/South America, check if they share a land border with any other country.
#    A country is an island if its boundary consists only of coastlines (touches no other polygons).
#    GeoPandas/Shapely `touches` can be used, but it's pairwise.
#
# Let's refine the island definition:
# A country in the Americas is considered "not an island" for land route purposes if:
#   a) It is the USA, Canada, or Mexico.
#   b) For other countries: if its geometry (when on N/S America) shares a border of non-zero length
#      with any other country also on N/S America. (This avoids classifying e.g. UK as land-connected via French Guyana)
#
# A more pragmatic approach for "not an island nation" on the American landmass:
# - If on North/South America.
# - And it's not one of the commonly known island nations (e.g., Caribbean islands, Greenland if separate).
# Natural Earth data has a 'SOV_A3' for sovereignty and 'ADM0_A3' for admin unit.
# Some island nations might be part of a larger sovereign state but geographically separate.
#
# The user specified: "for land route, just use if the country is in north or south america and is not an island."
# The challenge is the "is not an island" part.
#
# Let's try a simpler heuristic for "is an island" for countries in the Americas:
# A country in the Americas is an "island" if its land area is relatively small AND it doesn't share a border with US, Canada, or Mexico.
# Or, more simply, if its 'TYPE' field in Natural Earth data suggests it's an island or dependency.
# Let's check Natural Earth attributes for hints. `world_gdf.columns` showed 'TYPE'.
# print(world_gdf['TYPE'].unique()) might give clues: ['Sovereign country' 'Dependency' 'Country' 'Indeterminate' 'Disputed']
# This doesn't directly say "island".
#
# Alternative island check: if all parts of its geometry are surrounded by water.
# This means its boundary doesn't touch any other land geometry.
#
# Let's use a list of known major island nations in the Americas for simplicity, plus a check for direct border with US/Canada/Mexico.
# This is a heuristic. A perfect solution requires either a dataset that flags islands or complex topological analysis.

# Countries considered to have a clear land route or be the destination itself.
# (Mainland North/South American countries + USA/Canada/Mexico)
# We will mark as True if on the continent and NOT an island.

# For countries in North or South America:
# Assume "not an island" unless it's a known small island state.
# Most Caribbean nations, Greenland (if listed separately and considered North America).
# A country is NOT an island if it shares a land border with another country.
# We can check this by seeing if its boundary intersects with the boundary of other countries.

df['Land Route Possible'] = False
land_route_countries = []

# Identify countries directly bordering the US or Mexico (these clearly have a land route)
us_geom = world_gdf[world_gdf['ADM0_A3'] == 'USA'].geometry.iloc[0]
mex_geom = world_gdf[world_gdf['ADM0_A3'] == 'MEX'].geometry.iloc[0]
can_geom = world_gdf[world_gdf['ADM0_A3'] == 'CAN'].geometry.iloc[0]


for index, row in df.iterrows():
    on_american_continent = row['Continent'] in american_continents
    is_usa_mex_can = row['ISO_A3'] in ['USA', 'MEX', 'CAN']

    if not on_american_continent:
        df.loc[index, 'Land Route Possible'] = False
        continue

    if is_usa_mex_can: # USA, Mexico, Canada always have a land route.
        df.loc[index, 'Land Route Possible'] = True
        land_route_countries.append(row['Country Name'])
        continue

    # For other countries on American continents:
    # A country has a land route if it's part of the contiguous landmass of the Americas.
    # This means it's not an island disconnected from the mainland.

    country_geom = row['geometry']
    if country_geom is None or country_geom.is_empty: # Should not happen with good data
        df.loc[index, 'Land Route Possible'] = False
        continue

    # Heuristic: If a country in the Americas is not one of a few known large islands (like Greenland),
    # and it's not tiny (typical of small Caribbean islands), assume it's connected.
    # A more robust method: check if it shares a border of non-zero length with ANY other country.
    # If it does, it's not an isolated island.
    # The Natural Earth dataset might have issues with perfect topology for `touches` vs `intersects` for borders.
    # A common way to check for land connection is to see if it's part of the main continental landmass.
    # This can be done by creating a unary_union of all countries on the American continents and checking if this country is part of it.
    # However, this can be slow.

    # Simplified approach:
    # All countries in "North America" or "South America" are considered to have a land route,
    # EXCEPT for specific island nations/territories.
    # This relies on the accuracy of the 'CONTINENT' field and a list of exceptions.

    # List of ISO_A3 codes for American island nations/territories that DON'T have a direct land route to US border
    # This list is not exhaustive and might need adjustment based on dataset specifics (e.g. how dependencies are handled)
    # Includes Caribbean islands, Greenland, Falklands, etc.
    # Note: Puerto Rico (PRI), US Virgin Islands (VIR) are US territories but geographically islands.
    # Cuba (CUB), Haiti (HTI), Dominican Rep (DOM), Jamaica (JAM), Bahamas (BHS), etc.
    # Greenland (GRL), Falkland Is. (FLK)
    # Many smaller Caribbean islands: ATG (Antigua and Barbuda), BRB (Barbados), DMA (Dominica), GRD (Grenada),
    # KNA (Saint Kitts and Nevis), LCA (Saint Lucia), VCT (Saint Vincent and the Grenadines), TTO (Trinidad and Tobago)

    # For this exercise, a country on an American continent is assumed to have a land route
    # UNLESS its geometry type suggests it's an island (e.g. all its exterior rings are coasts)
    # OR its 'SOVEREIGNT' differs from its 'ADMIN' in a way that indicates an overseas territory (e.g. Greenland/Denmark)
    # and it's geographically isolated.

    # The user's original request was simpler: "if the country is in north or south america and is not an island."
    # Let's use a direct approach: if on the continent, assume land route unless it's a known major island group not connected.
    # The previous check `has_land_border_with_american_country` was too strict or failed due to geometry nuances.

    # New approach:
    # 1. If USA, Canada, Mexico -> True
    # 2. If on American Continent:
    #    Check if it's NOT one of the major island nations.
    #    A simple proxy for "not an island" for mainland countries: if their area is large.
    #    Or, if their geometry's envelope is large and not thin.
    #    This is still heuristic. The most reliable is a pre-compiled list or more detailed topological analysis.

    # Let's consider any country on the American continents as having a land route,
    # unless it's an obvious island. The `world_gdf` contains various countries.
    # If 'CONTINENT' is 'North America' or 'South America', assume True, then manually list exceptions.

    # Exception list (ISO_A3 codes of island nations/territories in the Americas without land bridge)
    # This is a practical simplification.
    island_exceptions_iso_a3 = [
        'ATG', 'AIA', 'BES', 'BHS', 'BMU', 'BRB', 'CUB', 'CUW', 'CYM', 'DMA', 'DOM',
        'FLK', 'GRD', 'GRL', 'GLP', 'HTI', 'JAM', 'KNA', 'LCA', 'MAF', 'MSR',
        'MTQ', 'PRI', 'SGS', 'SXM', 'TCA', 'TTO', 'VCT', 'VGB', 'VIR',
        # Aruba (ABW) might be tricky depending on how it's listed.
        # Countries like The Bahamas (BHS) are archipelagos.
    ]
    # Also, countries listed as "Oceania" but geographically near Americas (e.g. some Pacific islands)
    # should not be land routes. The `on_american_continent` check handles this.

    if row['ISO_A3'] not in island_exceptions_iso_a3:
        df.loc[index, 'Land Route Possible'] = True
        land_route_countries.append(row['Country Name'])
    else:
        df.loc[index, 'Land Route Possible'] = False # It's an island exception

    # Special case: USA, CAN, MEX should always be true, already handled.
    # If a country is an exception but IS USA/CAN/MEX (e.g. if USA had outlying islands listed as separate rows with USA ISO),
    # the `is_usa_mex_can` check would have caught it.

# Ensure USA, Canada, Mexico are True (redundant if not in island_exceptions_iso_a3, but safe)
df.loc[df['ISO_A3'].isin(['USA', 'MEX', 'CAN']), 'Land Route Possible'] = True
# Add their names to the land_route_countries list if not already by the loop
for name in ['United States of America', 'Canada', 'Mexico']:
    if name not in land_route_countries and name in df['Country Name'].values:
        land_route_countries.append(name)
land_route_countries = sorted(list(set(land_route_countries))) #


print(f"\nCountries determined to have a land route to US border: {len(land_route_countries)}")
# print(sorted(land_route_countries)) # For debugging

# Drop the temporary geometry column from df
df.drop(columns=['geometry', 'ADM0_A3'], inplace=True, errors='ignore')


df.to_csv("country_final_data.csv", index=False)
print("\nLand route determination complete. Final data ready (before cleaning for CSV output).")
print("Saved to country_final_data.csv")

print("\nSample of data with land route flag:")
print(df[['Country Name', 'Continent', 'Land Route Possible']].head())
print("\nCountries in Americas marked as NO land route (potential islands):")
print(df[(df['Continent'].isin(american_continents)) & (df['Land Route Possible'] == False)][['Country Name', 'Continent', 'Minimum Distance to US Southern Border (km)']])
