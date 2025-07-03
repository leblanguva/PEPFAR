import pandas as pd

def preprocess_spreadsheet(csv_path, sheet_name, date_range_problematic=False):
    """
    Loads and preprocesses a single migration data spreadsheet.

    Args:
        csv_path (str): Path to the CSV file.
        sheet_name (str): Identifier for the sheet (e.g., '2019_present' or '2013_present').
        date_range_problematic (bool): Flag to indicate if the sheet might have future/placeholder dates.

    Returns:
        pandas.DataFrame: Processed DataFrame in long format.
    """
    try:
        df = pd.read_csv(csv_path, header=0)
    except Exception as e:
        print(f"Error reading {csv_path}: {e}")
        return pd.DataFrame()

    # Identify the first column as 'Nationality' or similar
    nationality_col = df.columns[0]
    df = df.rename(columns={nationality_col: 'Nationality'})

    # Melt the DataFrame to long format
    df_melted = df.melt(id_vars=['Nationality'], var_name='DateStr', value_name='Encounters')

    # Data Cleaning
    df_melted['Encounters'] = pd.to_numeric(df_melted['Encounters'], errors='coerce').fillna(0).astype(int)
    df_melted['Nationality'] = df_melted['Nationality'].str.strip()

    # Convert DateStr to datetime objects
    # Attempt to parse dates, handling potential variations and errors
    def parse_date(date_str):
        try:
            # Common format: Oct 2019
            return pd.to_datetime(date_str, format='%b %Y')
        except ValueError:
            try:
                # Alternative: Oct-13 (assuming current century)
                return pd.to_datetime(date_str, format='%b-%y')
            except ValueError:
                return pd.NaT # Return NaT if parsing fails

    df_melted['Date'] = df_melted['DateStr'].apply(parse_date)

    # Drop rows where date parsing failed
    df_melted = df_melted.dropna(subset=['Date'])

    # Filter out known placeholder/summary rows for Nationality
    df_melted = df_melted[~df_melted['Nationality'].isin(['Total', 'Other Countries', 'All other, including stateless and unknown'])]
    df_melted = df_melted[~df_melted['Nationality'].str.contains('total', case=False, na=False)]


    # Handle problematic date ranges if flagged (specific to the '2019_present' sheet)
    if date_range_problematic:
        # Assuming current date is roughly July 2024 for "present"
        # Filter out dates beyond a reasonable "present" to avoid placeholder future data
        # This might need adjustment based on when "present" actually is.
        # For now, let's assume data is valid up to June 2024.
        # A more robust way would be to check if 'Encounters' are mostly zero for future dates.
        current_cutoff = pd.to_datetime('2024-06-01')
        df_melted = df_melted[df_melted['Date'] <= current_cutoff]

    df_melted = df_melted[['Nationality', 'Date', 'Encounters']].sort_values(by=['Nationality', 'Date'])
    print(f"Processed {sheet_name} - {csv_path}: {df_melted.shape[0]} rows")
    return df_melted

# Process both spreadsheets
df_2019_present = preprocess_spreadsheet('encounters_2019_present.csv', '2019_present', date_range_problematic=True)
df_2013_present = preprocess_spreadsheet('encounters_2013_present.csv', '2013_present')

# Combine the dataframes
# We'll use df_2013_present as the base and update/append with df_2019_present
# This strategy ensures we keep the longer history where available and add newer data.

if not df_2013_present.empty and not df_2019_present.empty:
    # Convert Date to year-month for easier comparison and merging
    df_2013_present['YearMonth'] = df_2013_present['Date'].dt.to_period('M')
    df_2019_present['YearMonth'] = df_2019_present['Date'].dt.to_period('M')

    # Create a unique key for merging
    df_2013_present['MergeKey'] = df_2013_present['Nationality'] + '_' + df_2013_present['YearMonth'].astype(str)
    df_2019_present['MergeKey'] = df_2019_present['Nationality'] + '_' + df_2019_present['YearMonth'].astype(str)

    # Identify records in df_2019_present that are not in df_2013_present (either new dates or new countries for existing dates)
    new_records_df = df_2019_present[~df_2019_present['MergeKey'].isin(df_2013_present['MergeKey'])]

    combined_df = pd.concat([df_2013_present, new_records_df], ignore_index=True)

    # Clean up temporary columns
    combined_df = combined_df.drop(columns=['YearMonth', 'MergeKey'])

elif not df_2019_present.empty:
    combined_df = df_2019_present.drop(columns=['YearMonth', 'MergeKey'], errors='ignore')
elif not df_2013_present.empty:
    combined_df = df_2013_present.drop(columns=['YearMonth', 'MergeKey'], errors='ignore')
else:
    combined_df = pd.DataFrame()


if not combined_df.empty:
    # Final sort and save
    combined_df = combined_df.sort_values(by=['Nationality', 'Date']).reset_index(drop=True)
    combined_df.to_csv('us_border_encounters_monthly.csv', index=False)
    print("Combined migration data saved to us_border_encounters_monthly.csv")
    print(f"Total rows in combined data: {combined_df.shape[0]}")
    print(f"Date range: {combined_df['Date'].min()} to {combined_df['Date'].max()}")
    print(f"Unique countries: {combined_df['Nationality'].nunique()}")
else:
    print("No data to save after processing.")

# --- Next: GDELT Data (Sample) ---
# This will be a simplified version focusing on getting a small sample processed.
# A full GDELT processing pipeline would be more complex.

# --- Then: Other datasources ---
# (Distance, Climate, Food Insecurity, US Econ)
# These will be individual scripts or direct downloads followed by processing.
print("\\nProcessing complete for migration data.")
