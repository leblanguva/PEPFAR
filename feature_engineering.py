import pandas as pd
import numpy as np

def create_time_based_features(df):
    """Creates time-based features from the 'Date' column."""
    df = df.copy()
    df['Date'] = pd.to_datetime(df['Date'])
    df['Year'] = df['Date'].dt.year
    df['Month'] = df['Date'].dt.month
    df['Quarter'] = df['Date'].dt.quarter
    # Create a time index (number of months from the start of the dataset)
    df['TimeIndex'] = (df['Date'].dt.year - df['Date'].dt.year.min()) * 12 + df['Date'].dt.month - df['Date'].dt.month.min()
    print("Created time-based features: Year, Month, Quarter, TimeIndex.")
    return df

def create_lagged_features(df, column_name, lags):
    """Creates lagged features for a specified column."""
    df = df.copy()
    for lag in lags:
        df[f'{column_name}_lag_{lag}'] = df.groupby('Nationality')[column_name].shift(lag)
    print(f"Created lagged features for {column_name} with lags: {lags}.")
    return df

def create_rolling_features(df, column_name, windows, agg_funcs=['mean', 'std']):
    """Creates rolling window features for a specified column."""
    df = df.copy()
    for window in windows:
        for func in agg_funcs:
            if func == 'mean':
                df[f'{column_name}_roll_{func}_{window}m'] = df.groupby('Nationality')[column_name].transform(
                    lambda x: x.rolling(window=window, min_periods=1).mean() # min_periods=1 to avoid NaNs at start
                )
            elif func == 'std':
                 df[f'{column_name}_roll_{func}_{window}m'] = df.groupby('Nationality')[column_name].transform(
                    lambda x: x.rolling(window=window, min_periods=1).std()
                )
    print(f"Created rolling features for {column_name} with windows: {windows} and functions: {agg_funcs}.")
    return df

# Load the master dataset
try:
    master_df = pd.read_csv('master_dataset_final_sample.csv')
    print(f"Loaded master_dataset_final_sample.csv with shape: {master_df.shape}")
except FileNotFoundError:
    print("Error: master_dataset_final_sample.csv not found. Please run the database creation script first.")
    exit()

# Ensure Date is datetime
master_df['Date'] = pd.to_datetime(master_df['Date'])

# 1. Create Time-Based Features
master_df = create_time_based_features(master_df)

# 2. Create Lagged Migration Encounters
# Lags: 1, 2, 3, 6, 12 months
encounter_lags = [1, 2, 3, 6, 12]
master_df = create_lagged_features(master_df, 'Encounters', encounter_lags)

# 3. Create Rolling Mean & Std Dev of Encounters
# Windows: 3, 6, 12 months
encounter_windows = [3, 6, 12]
master_df = create_rolling_features(master_df, 'Encounters', encounter_windows, agg_funcs=['mean', 'std'])

# 4. Lagged GDELT Event Counts (if GDELT_EventCount column exists and is not all NaN/0)
if 'GDELT_EventCount' in master_df.columns and master_df['GDELT_EventCount'].notna().any() and master_df['GDELT_EventCount'].sum() > 0:
    gdelt_lags = [1, 2, 3]
    master_df = create_lagged_features(master_df, 'GDELT_EventCount', gdelt_lags)
else:
    print("Skipping lagged GDELT features as the column is missing, all NaN, or all zero.")

# 5. Lagged US Economic Variables (if they exist)
us_econ_cols = ['US_Hospitality_JobOpenings', 'US_Construction_JobOpenings']
econ_lags = [1, 2, 3]
for col in us_econ_cols:
    if col in master_df.columns and master_df[col].notna().any():
        # For US-level data, we don't group by Nationality when shifting
        # However, the current merge structure already broadcasts these values.
        # If they were to be lagged *before* merging, that'd be different.
        # For now, let's assume these are already correctly aligned monthly.
        # A simple shift across the whole dataset might be misleading if not careful with panel structure.
        # A better way for non-country-specific data is to lag it on its own time series first, then merge.
        # The current merge already aligns them by MonthYear, so a simple shift() is okay if data is sorted by date.
        master_df_sorted_for_econ_lag = master_df.sort_values(by=['Date']) # Ensure global sort for these lags
        for lag in econ_lags:
             master_df_sorted_for_econ_lag[f'{col}_lag_{lag}'] = master_df_sorted_for_econ_lag[col].shift(lag)

        # Merge these lagged columns back to the original master_df structure
        # This is a bit tricky due to the multi-index nature if we consider Nationality.
        # For simplicity, let's assume the US econ data is uniform for all countries in a given month.
        # The current merge process in `preprocess_gdelt_sample.py` already handles this broadcasting.
        # So, we can lag directly on the master_df *after* ensuring it's sorted globally by Date first,
        # then restore original sort.
        original_index = master_df.index
        master_df = master_df.sort_values(by=['Date'])
        for lag in econ_lags:
            master_df[f'{col}_lag_{lag}'] = master_df[col].shift(lag)
        master_df = master_df.reindex(original_index).sort_index() # Restore original order
        print(f"Created lagged features for {col} with lags: {econ_lags}.")

    else:
        print(f"Skipping lagged features for {col} as it's missing or all NaN.")


# Display some info about the new dataframe
print("\n--- DataFrame with new features ---")
master_df.info()
print(master_df.head())
print(master_df.tail())

# Save the dataframe with engineered features
master_df.to_csv('master_dataset_with_features.csv', index=False)
print("\nSaved master_dataset_with_features.csv")

# Note: More features can be added:
# - Interaction terms
# - Dummy variables for months/quarters (if needed for specific models, RF handles categories)
# - More sophisticated rolling features (e.g., min, max, median)
# - Features from other data sources (climate, food insecurity) once fully integrated.
# - Country-specific trend features or differences from overall trend.
