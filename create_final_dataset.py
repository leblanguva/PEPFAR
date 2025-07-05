import pandas as pd

# Load the data processed in the previous step
# This file should contain: Country Name, ISO_A3, Minimum Distance (km), Continent, Land Route Possible
try:
    df = pd.read_csv("country_final_data.csv")
except FileNotFoundError:
    print("Error: 'country_final_data.csv' not found. Please ensure previous steps ran successfully.")
    exit()
except Exception as e:
    print(f"Error reading 'country_final_data.csv': {e}")
    exit()

# Select and order the final columns for the CSV output
# Expected columns: 'Country Name', 'ISO_A3', 'Minimum Distance to US Southern Border (km)', 'Land Route Possible'
final_columns = [
    'Country Name',
    'ISO_A3',
    'Minimum Distance to US Southern Border (km)',
    'Land Route Possible'
]

# Ensure all required final columns are present
missing_final_cols = [col for col in final_columns if col not in df.columns]
if missing_final_cols:
    print(f"Error: The intermediate data is missing the following required columns: {missing_final_cols}")
    print(f"Available columns: {df.columns.tolist()}")
    # Attempt to map if names are slightly different, or raise error
    # Example: if 'ISO_A3' is missing but 'ADM0_A3' is there from an earlier stage and wasn't renamed.
    # For now, assume exact names are expected from previous step.
    exit()

final_df = df[final_columns]

# Round the distance to a reasonable number of decimal places, e.g., 2
if 'Minimum Distance to US Southern Border (km)' in final_df.columns:
    final_df.loc[:, 'Minimum Distance to US Southern Border (km)'] = final_df['Minimum Distance to US Southern Border (km)'].round(2)

# Sort the dataset alphabetically by Country Name
final_df = final_df.sort_values(by='Country Name').reset_index(drop=True)

# Save the final dataset to CSV
output_filename = "country_distances_to_us_border.csv"
try:
    final_df.to_csv(output_filename, index=False, encoding='utf-8')
    print(f"Final dataset created successfully: {output_filename}")
except Exception as e:
    print(f"Error saving final dataset to CSV: {e}")
    exit()

print("\nFirst 10 rows of the final dataset:")
print(final_df.head(10))

print("\nLast 10 rows of the final dataset:")
print(final_df.tail(10))

print(f"\nTotal countries in dataset: {len(final_df)}")
