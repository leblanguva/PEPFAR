import pandas as pd
import requests
import numpy as np
from scipy.stats import pearsonr, spearmanr
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta

# --- Configuration ---
# UNHCR Data URLs (now pointing to JSON endpoints by removing &export=csv)
CANARY_ARRIVALS_URL = "https://data.unhcr.org/population/get/timeseries?widget_id=613983&geo_id=729&sv_id=100&population_group=5634&frequency=month&fromDate=2017-01-01"
MAINLAND_SEA_ARRIVALS_URL = "https://data.unhcr.org/population/get/timeseries?widget_id=614001&geo_id=729&sv_id=100&population_group=4797&frequency=month&fromDate=2017-01-01"
MAINLAND_LAND_ARRIVALS_URL = "https://data.unhcr.org/population/get/timeseries?widget_id=614002&geo_id=729&sv_id=100&population_group=4798&frequency=month&fromDate=2017-01-01"

# Open-Meteo API URLs
MARINE_API_URL = "https://marine-api.open-meteo.com/v1/marine"
HISTORICAL_API_URL = "https://archive-api.open-meteo.com/v1/archive"

# Geographic Coordinates
LOCATIONS = {
    "canary": {"latitude": 27.5, "longitude": -14.5, "name": "Canary Islands Route"},
    "mainland": {"latitude": 35.9, "longitude": -5.5, "name": "Western Med Route"}
}

# Time Period for Environmental Data
today = datetime.today()
first_day_current_month = today.replace(day=1)
end_of_last_month = first_day_current_month - timedelta(days=1)
START_DATE = "2017-01-01"
END_DATE = end_of_last_month.strftime("%Y-%m-%d")


# Environmental Parameters
MARINE_HOURLY_PARAMS = [
    "wave_height", "wave_direction", "wave_period",
    "swell_wave_height", "swell_wave_direction", "swell_wave_period",
    "sea_surface_temperature",
    "ocean_current_velocity", "ocean_current_direction"
]
ATMOSPHERIC_HOURLY_PARAMS = [
    "wind_speed_10m", "wind_direction_10m", "precipitation", # Corrected from precipitation_sum
    "pressure_msl", "cloud_cover"
]

# --- Helper Functions ---
# import io # No longer needed for CSV direct parsing attempt

def fetch_unhcr_data(json_url, column_name_prefix):
    """Fetches and preprocesses UNHCR arrivals data from JSON endpoint."""
    try:
        print(f"Attempting to fetch JSON from: {json_url}")
        response = requests.get(json_url, timeout=30)
        response.raise_for_status()

        json_data = response.json()

        if not json_data or 'data' not in json_data or 'timeseries' not in json_data['data']:
            print(f"Warning: JSON data from {json_url} is missing expected structure ('data' or 'timeseries'). Full response: {json_data}")
            return pd.DataFrame()

        # The actual data seems to be nested further, often under a key that might vary or be complex.
        # Let's inspect the structure of json_data['data']['timeseries']
        timeseries_content = json_data['data']['timeseries']
        # print(f"Type of timeseries_content: {type(timeseries_content)}") # Debugging line
        # if isinstance(timeseries_content, dict): # Original assumption
        #    print(f"Keys in timeseries_content: {list(timeseries_content.keys())}") # Debugging line

        if isinstance(timeseries_content, list):
            data_points_list = timeseries_content
        elif isinstance(timeseries_content, dict):
            # If it's a dict, we need to find the actual list of data points.
            # Common pattern: the list is the value of the first (or only) key.
            timeseries_keys = list(timeseries_content.keys())
            if not timeseries_keys:
                print(f"Warning: No keys found under json_data['data']['timeseries'] (which is a dict) for {json_url}.")
                return pd.DataFrame()
            data_points_list_key = timeseries_keys[0]
            data_points_list = timeseries_content[data_points_list_key]
        else:
            print(f"Warning: json_data['data']['timeseries'] is neither a list nor a dict for {json_url}. Type: {type(timeseries_content)}")
            return pd.DataFrame()

        if not isinstance(data_points_list, list):
            print(f"Warning: Expected data_points_list to be a list, but got {type(data_points_list)} for {json_url}.")
            return pd.DataFrame()

        if not data_points_list: # Handles if data_points_list was an empty list initially
            print(f"Warning: Data points list is empty for {json_url}.")
            return pd.DataFrame()

        df = pd.DataFrame(data_points_list)

        # --- DEBUG PRINTS ---
        print(f"Inside fetch_unhcr_data for {column_name_prefix}:")
        print(f"  Initial df.shape: {df.shape}")
        if not df.empty:
            print(f"  df.head():\n{df.head()}")
            print(f"  df.tail():\n{df.tail()}")
        # --- END DEBUG PRINTS ---

        if df.empty:
            print(f"Warning: UNHCR JSON data from {json_url} parsed to an empty DataFrame.")
            return pd.DataFrame()

        # Date column handling - prioritize unix_timestamp
        date_col_created = False
        if 'unix_timestamp' in df.columns:
            try:
                df['date'] = pd.to_datetime(df['unix_timestamp'], unit='s')
                date_col_created = True
            except Exception as e_ts:
                print(f"Error converting unix_timestamp: {e_ts}")

        if not date_col_created and 'data_point_month' in df.columns:
            try:
                df['date'] = pd.to_datetime(df['data_point_month'])
                date_col_created = True
            except Exception as e_dpm:
                 print(f"Error converting data_point_month: {e_dpm}")

        if not date_col_created and 'month' in df.columns and 'year' in df.columns:
            try:
                # Ensure month and year are strings for concatenation, then to_datetime
                df['date_str'] = df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01'
                df['date'] = pd.to_datetime(df['date_str'])
                df.drop(columns=['date_str'], inplace=True) # Clean up temp column
                date_col_created = True
            except Exception as e_my:
                print(f"Error constructing date from month/year: {e_my}")

        if not date_col_created:
            print(f"Warning: Suitable date column could not be processed/found in UNHCR JSON from {json_url}. Columns: {df.columns.tolist()}")
            return pd.DataFrame()

        df.set_index('date', inplace=True)

        # Individuals column handling
        individuals_col_to_use = None
        if 'individuals' in df.columns:
            individuals_col_to_use = 'individuals'
        else:
            # Add more fallbacks if needed, based on observed column names
            pass

        if individuals_col_to_use is None:
            print(f"Warning: Individuals column ('individuals') not found in UNHCR JSON from {json_url}. Columns: {df.columns.tolist()}")
            return pd.DataFrame()

        df[individuals_col_to_use] = pd.to_numeric(df[individuals_col_to_use], errors='coerce').fillna(0)
        arrival_col_name = f"arrivals_{column_name_prefix}"
        df.rename(columns={individuals_col_to_use: arrival_col_name}, inplace=True)

        df = df[~df.index.duplicated(keep='first')]
        return df[[arrival_col_name]].resample('ME').sum()
    except requests.exceptions.HTTPError as e_http:
        print(f"HTTP Error processing UNHCR JSON data from {json_url}: {e_http}. Response: {response.text[:500] if response else 'No response'}")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error processing UNHCR JSON data from {json_url}: {e}")
        return pd.DataFrame()

def fetch_open_meteo_data(api_url, location_coords, hourly_params, is_marine=True):
    """Fetches Open-Meteo data (Marine or Historical)."""
    params = {
        "latitude": location_coords["latitude"],
        "longitude": location_coords["longitude"],
        "start_date": START_DATE,
        "end_date": END_DATE,
        "hourly": ",".join(hourly_params),
        "timezone": "GMT"
    }
    if is_marine:
        params["cell_selection"] = "sea"
    else:
        params["models"] = "era5"
        params["cell_selection"] = "sea"

    response = None # Define to ensure it's available in except block
    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()

        if 'hourly' not in data or 'time' not in data['hourly']:
            print(f"Unexpected data structure from Open-Meteo for {location_coords['name']}. API Response: {data}")
            return pd.DataFrame()

        df = pd.DataFrame(data['hourly'])
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        for col in hourly_params:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            else:
                print(f"Warning: Expected hourly column '{col}' not found in data for {location_coords['name']}")
        return df
    except requests.exceptions.RequestException as e:
        error_message = f"HTTP Error fetching Open-Meteo data for {location_coords['name']}: {e}"
        if response is not None:
            error_message += f"\nURL attempted: {response.url}"
            error_message += f"\nResponse status: {response.status_code}"
            error_message += f"\nResponse text: {response.text}"
        else:
            # Construct the URL manually if response object is not available
            param_str = "&".join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{api_url}?{param_str}"
            error_message += f"\nURL attempted: {full_url}"
        print(error_message)
        return pd.DataFrame()
    except Exception as e: # Catch other errors like JSONDecodeError
        error_message = f"An unexpected error occurred while fetching/processing Open-Meteo data for {location_coords['name']}: {e}"
        if response is not None:
             error_message += f"\nResponse text that may have caused error: {response.text[:500]}..." # Show snippet
        print(error_message)
        return pd.DataFrame()

def aggregate_env_data_monthly(df_hourly, location_name_prefix):
    """Aggregates hourly environmental data to monthly."""
    if df_hourly.empty:
        return pd.DataFrame()

    aggregated_series_list = []

    directional_vars_map = {
        'wave_direction': 'wave_height',
        'swell_wave_direction': 'swell_wave_height',
        'wind_direction_10m': 'wind_speed_10m',
        'ocean_current_direction': 'ocean_current_velocity'
    }

    temp_hourly_df = df_hourly.copy()

    for dir_col, mag_col in directional_vars_map.items():
        if dir_col in temp_hourly_df.columns and mag_col in temp_hourly_df.columns:
            valid_data = temp_hourly_df[[mag_col, dir_col]].dropna()
            if not valid_data.empty:
                magnitude = valid_data[mag_col]
                direction_rad = np.deg2rad(valid_data[dir_col])

                base_name_mag = mag_col.replace('_height','').replace('_speed','').replace('_velocity','')
                u_comp_col_name = f"{location_name_prefix}_{base_name_mag}_u"
                v_comp_col_name = f"{location_name_prefix}_{base_name_mag}_v"

                u_vals = pd.Series(magnitude * np.sin(direction_rad), index=valid_data.index)
                v_vals = pd.Series(magnitude * np.cos(direction_rad), index=valid_data.index)

                aggregated_series_list.append(u_vals.resample('ME').mean().rename(u_comp_col_name))
                aggregated_series_list.append(v_vals.resample('ME').mean().rename(v_comp_col_name))
            else:
                print(f"Warning: No valid data for U/V calculation of {dir_col}/{mag_col} for {location_name_prefix} after dropna.")
        else:
            print(f"Warning: Missing {dir_col} or {mag_col} for U/V calculation for {location_name_prefix}.")

    for col in df_hourly.columns:
        if col in directional_vars_map or col in directional_vars_map.values() or col.endswith("_u") or col.endswith("_v"):
            continue

        new_col_name = f"{location_name_prefix}_{col.lower().replace('sea_surface_','sst_')}"
        if 'precipitation' in col:
            aggregated_series_list.append(df_hourly[col].resample('ME').sum().rename(new_col_name))
        else:
            aggregated_series_list.append(df_hourly[col].resample('ME').mean().rename(new_col_name))

    if not aggregated_series_list:
        return pd.DataFrame()

    final_monthly_df = pd.concat(aggregated_series_list, axis=1)
    return final_monthly_df

# --- Main Execution ---
if __name__ == "__main__":
    print(f"--- Starting Data Extraction & Preprocessing ---")
    print(f"Environmental data will be fetched for dates: {START_DATE} to {END_DATE}")

    # 1. Fetch UNHCR Arrivals Data
    print("\nFetching UNHCR arrivals data...")
    df_canary_arrivals = fetch_unhcr_data(CANARY_ARRIVALS_URL, "canary")
    df_mainland_sea_arrivals = fetch_unhcr_data(MAINLAND_SEA_ARRIVALS_URL, "mainland_sea")
    df_mainland_land_arrivals = fetch_unhcr_data(MAINLAND_LAND_ARRIVALS_URL, "mainland_land")

    if not df_canary_arrivals.empty:
        print(f"Canary arrivals data fetched: {df_canary_arrivals.shape[0]} months")
    if not df_mainland_sea_arrivals.empty:
        print(f"Mainland sea arrivals data fetched: {df_mainland_sea_arrivals.shape[0]} months")
    if not df_mainland_land_arrivals.empty:
        print(f"Mainland land arrivals data fetched: {df_mainland_land_arrivals.shape[0]} months")

    # 2. Fetch and Process Environmental Data
    env_data_canary = pd.DataFrame()
    env_data_mainland = pd.DataFrame()

    for loc_key, loc_config in LOCATIONS.items():
        print(f"\nFetching environmental data for {loc_config['name']}...")
        df_marine_hourly = fetch_open_meteo_data(MARINE_API_URL, loc_config, MARINE_HOURLY_PARAMS, is_marine=True)
        df_atmos_hourly = fetch_open_meteo_data(HISTORICAL_API_URL, loc_config, ATMOSPHERIC_HOURLY_PARAMS, is_marine=False)

        if df_marine_hourly.empty and df_atmos_hourly.empty:
            print(f"No environmental data fetched for {loc_config['name']}. Skipping.")
            continue

        df_env_hourly_combined = pd.DataFrame()
        if not df_marine_hourly.empty:
            df_env_hourly_combined = df_marine_hourly
        if not df_atmos_hourly.empty:
            if df_env_hourly_combined.empty:
                df_env_hourly_combined = df_atmos_hourly
            else:
                df_env_hourly_combined = df_env_hourly_combined.join(df_atmos_hourly, how='outer')

        print(f"Aggregating monthly environmental data for {loc_config['name']}...")
        df_env_monthly = aggregate_env_data_monthly(df_env_hourly_combined, loc_key)

        if not df_env_monthly.empty:
            print(f"Monthly environmental data processed for {loc_config['name']}: {df_env_monthly.shape[0]} months, {df_env_monthly.shape[1]} variables.")
            if loc_key == "canary":
                env_data_canary = df_env_monthly
            elif loc_key == "mainland":
                env_data_mainland = df_env_monthly
        else:
            print(f"Failed to process monthly environmental data for {loc_config['name']}.")

    # 3. Merge Arrivals with Environmental Data
    print("\nMerging arrivals and environmental data...")
    df_canary_analysis = pd.DataFrame()
    df_mainland_analysis = pd.DataFrame()

    if not df_canary_arrivals.empty and not env_data_canary.empty:
        df_canary_analysis = df_canary_arrivals.join(env_data_canary, how='inner')
        print(f"Canary analysis dataset created: {df_canary_analysis.shape[0]} months, columns: {df_canary_analysis.columns.tolist()}")
    else:
        print("Could not create Canary analysis dataset due to missing arrivals or environmental data.")

    if not df_mainland_sea_arrivals.empty and not env_data_mainland.empty:
        df_mainland_analysis = df_mainland_sea_arrivals.join(env_data_mainland, how='inner')
        print(f"Mainland sea analysis dataset created: {df_mainland_analysis.shape[0]} months, columns: {df_mainland_analysis.columns.tolist()}")
    else:
        print("Could not create Mainland sea analysis dataset due to missing arrivals or environmental data.")

    print("\n--- Data Extraction & Preprocessing Complete ---")

    if not df_canary_analysis.empty:
        print("\nCanary Analysis DataFrame Head:")
        print(df_canary_analysis.head())
        df_canary_analysis.to_csv("canary_analysis_data.csv")
        print("\nSaved canary_analysis_data.csv")

    if not df_mainland_analysis.empty:
        print("\nMainland Sea Analysis DataFrame Head:")
        print(df_mainland_analysis.head())
        df_mainland_analysis.to_csv("mainland_sea_analysis_data.csv")
        print("Saved mainland_sea_analysis_data.csv")

    if not df_mainland_land_arrivals.empty:
        df_mainland_land_arrivals.to_csv("mainland_land_arrivals.csv")
        print("Saved mainland_land_arrivals.csv")

# --- Correlation and Visualization Functions ---

def perform_correlation_analysis(df_analysis, arrivals_col, route_name):
    """Performs correlation analysis and prints significant findings."""
    print(f"\n--- Correlation Analysis for {route_name} ---")
    if df_analysis.empty or arrivals_col not in df_analysis.columns:
        print(f"DataFrame is empty or arrivals column '{arrivals_col}' is missing for {route_name}.")
        return None

    env_cols = [col for col in df_analysis.columns if col != arrivals_col]
    if not env_cols:
        print(f"No environmental columns found for {route_name}.")
        return None

    correlations = {}
    print(f"\nCorrelations with {arrivals_col}:")
    print("----------------------------------------------------------")
    print(f"{'Environmental Factor':<35} | {'Pearson r':<10} | {'P-value (P)':<10} | {'Spearman rho':<12} | {'P-value (S)':<10}")
    print("----------------------------------------------------------")

    for col in env_cols:
        # Create a temporary DataFrame with the arrivals column and the current environmental column
        # Drop rows where EITHER column has a NaN for this specific correlation pair
        temp_df_pair = df_analysis[[arrivals_col, col]].dropna()

        if pd.api.types.is_numeric_dtype(temp_df_pair[col]) and \
           pd.api.types.is_numeric_dtype(temp_df_pair[arrivals_col]) and \
           not temp_df_pair.empty:

            if len(temp_df_pair) < 3: # Not enough data points for reliable correlation
                 print(f"{col:<35} | {'Too few non-NaN pairs after dropna':<50}")
                 correlations[col] = {'pearson_r': np.nan, 'pearson_p': np.nan, 'spearman_rho': np.nan, 'spearman_p': np.nan}
                 continue

            # Pearson
            pearson_corr, pearson_p = pearsonr(temp_df_pair[arrivals_col], temp_df_pair[col])
            # Spearman
            spearman_corr, spearman_p = spearmanr(temp_df_pair[arrivals_col], temp_df_pair[col])

            correlations[col] = {
                'pearson_r': pearson_corr, 'pearson_p': pearson_p,
                'spearman_rho': spearman_corr, 'spearman_p': spearman_p
            }
            print(f"{col:<35} | {pearson_corr:<10.3f} | {pearson_p:<10.3e} | {spearman_corr:<12.3f} | {spearman_p:<10.3e}")
        else:
            print(f"{col:<35} | {'Non-numeric or all NaNs after pairing':<50}")
            correlations[col] = {'pearson_r': np.nan, 'pearson_p': np.nan, 'spearman_rho': np.nan, 'spearman_p': np.nan}

    print("----------------------------------------------------------")

    # Create a full correlation matrix for heatmap (pandas .corr() handles pairwise NaNs by default)
    correlation_matrix_spearman = df_analysis.corr(method='spearman')
    return correlations, correlation_matrix_spearman


def visualize_findings(df_analysis, arrivals_col, route_name, correlation_results, full_corr_matrix):
    """Generates and saves visualizations for the analysis."""
    if df_analysis.empty or arrivals_col not in df_analysis.columns:
        print(f"Skipping visualization for {route_name} due to empty or invalid DataFrame.")
        return

    print(f"\n--- Generating Visualizations for {route_name} ---")

    # Ensure output directory exists
    output_dir = f"visualizations/{route_name}"
    import os
    os.makedirs(output_dir, exist_ok=True)

    # 1. Time series plot of arrivals
    plt.figure(figsize=(12, 6))
    df_analysis[arrivals_col].plot(title=f'Monthly Arrivals - {route_name}')
    plt.ylabel('Number of Arrivals')
    plt.xlabel('Date')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/{route_name}_arrivals_timeseries.png")
    plt.close()
    print(f"Saved: {route_name}_arrivals_timeseries.png")

    # 2. Correlation Heatmap (Spearman)
    if full_corr_matrix is not None and not full_corr_matrix.empty:
        plt.figure(figsize=(12, 10))
        sns.heatmap(full_corr_matrix, annot=True, cmap='coolwarm', fmt=".2f", linewidths=.5)
        plt.title(f'Spearman Correlation Matrix - {route_name}')
        plt.tight_layout()
        plt.savefig(f"{output_dir}/{route_name}_correlation_heatmap.png")
        plt.close()
        print(f"Saved: {route_name}_correlation_heatmap.png")

    # 3. Scatter plots for top N correlated variables (based on Spearman's rho magnitude)
    if correlation_results:
        sorted_corrs = sorted(correlation_results.items(), key=lambda item: abs(item[1]['spearman_rho']), reverse=True)

        top_n = min(5, len(sorted_corrs))
        print(f"\nGenerating scatter plots for top {top_n} correlated factors for {route_name}:")

        for i in range(top_n):
            env_var, corr_values = sorted_corrs[i]
            if pd.api.types.is_numeric_dtype(df_analysis[env_var]):
                plt.figure(figsize=(8, 6))
                sns.scatterplot(x=df_analysis[env_var], y=df_analysis[arrivals_col])
                # Add regression line
                sns.regplot(x=df_analysis[env_var], y=df_analysis[arrivals_col], scatter=False, color='red')
                plt.title(f'{arrivals_col} vs. {env_var}\nSpearman ρ: {corr_values["spearman_rho"]:.3f} (p={corr_values["spearman_p"]:.3e})')
                plt.xlabel(env_var)
                plt.ylabel(f'Arrivals ({route_name})')
                plt.tight_layout()
                plt.savefig(f"{output_dir}/{route_name}_scatter_{env_var}.png")
                plt.close()
                print(f"Saved: {route_name}_scatter_{env_var}.png")

    # 4. Seasonality: Box plot of arrivals by month
    plt.figure(figsize=(12, 6))
    # Ensure index is datetime
    if not isinstance(df_analysis.index, pd.DatetimeIndex):
         df_analysis.index = pd.to_datetime(df_analysis.index)

    sns.boxplot(x=df_analysis.index.month, y=df_analysis[arrivals_col])
    plt.title(f'Monthly Seasonality of Arrivals - {route_name}')
    plt.xlabel('Month')
    plt.ylabel('Number of Arrivals')
    plt.xticks(ticks=range(12), labels=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
    plt.tight_layout()
    plt.savefig(f"{output_dir}/{route_name}_arrivals_seasonality.png")
    plt.close()
    print(f"Saved: {route_name}_arrivals_seasonality.png")

    print(f"--- Visualizations for {route_name} Complete ---")


# --- Main Execution ---
if __name__ == "__main__":
    print(f"--- Starting Data Extraction & Preprocessing ---")
    print(f"Environmental data will be fetched for dates: {START_DATE} to {END_DATE}")

    # 1. Fetch UNHCR Arrivals Data
    print("\nFetching UNHCR arrivals data...")
    df_canary_arrivals = fetch_unhcr_data(CANARY_ARRIVALS_URL, "canary")
    df_mainland_sea_arrivals = fetch_unhcr_data(MAINLAND_SEA_ARRIVALS_URL, "mainland_sea")
    df_mainland_land_arrivals = fetch_unhcr_data(MAINLAND_LAND_ARRIVALS_URL, "mainland_land")

    if not df_canary_arrivals.empty:
        print(f"Canary arrivals data fetched: {df_canary_arrivals.shape[0]} months")
    if not df_mainland_sea_arrivals.empty:
        print(f"Mainland sea arrivals data fetched: {df_mainland_sea_arrivals.shape[0]} months")
    if not df_mainland_land_arrivals.empty:
        print(f"Mainland land arrivals data fetched: {df_mainland_land_arrivals.shape[0]} months")

    # 2. Fetch and Process Environmental Data
    env_data_canary = pd.DataFrame()
    env_data_mainland = pd.DataFrame()

    for loc_key, loc_config in LOCATIONS.items():
        print(f"\nFetching environmental data for {loc_config['name']}...")
        df_marine_hourly = fetch_open_meteo_data(MARINE_API_URL, loc_config, MARINE_HOURLY_PARAMS, is_marine=True)
        df_atmos_hourly = fetch_open_meteo_data(HISTORICAL_API_URL, loc_config, ATMOSPHERIC_HOURLY_PARAMS, is_marine=False)

        if df_marine_hourly.empty and df_atmos_hourly.empty:
            print(f"No environmental data fetched for {loc_config['name']}. Skipping.")
            continue

        df_env_hourly_combined = pd.DataFrame()
        if not df_marine_hourly.empty:
            df_env_hourly_combined = df_marine_hourly
        if not df_atmos_hourly.empty:
            if df_env_hourly_combined.empty:
                df_env_hourly_combined = df_atmos_hourly
            else:
                df_env_hourly_combined = df_env_hourly_combined.join(df_atmos_hourly, how='outer')

        print(f"Aggregating monthly environmental data for {loc_config['name']}...")
        df_env_monthly = aggregate_env_data_monthly(df_env_hourly_combined, loc_key)

        if not df_env_monthly.empty:
            print(f"Monthly environmental data processed for {loc_config['name']}: {df_env_monthly.shape[0]} months, {df_env_monthly.shape[1]} variables.")
            if loc_key == "canary":
                env_data_canary = df_env_monthly
            elif loc_key == "mainland":
                env_data_mainland = df_env_monthly
        else:
            print(f"Failed to process monthly environmental data for {loc_config['name']}.")

    # 3. Merge Arrivals with Environmental Data
    print("\nMerging arrivals and environmental data...")
    df_canary_analysis = pd.DataFrame()
    df_mainland_analysis = pd.DataFrame()

    if not df_canary_arrivals.empty and not env_data_canary.empty:
        df_canary_analysis = df_canary_arrivals.join(env_data_canary, how='inner')
        print(f"Canary analysis dataset created: {df_canary_analysis.shape[0]} months, columns: {df_canary_analysis.columns.tolist()}")
    else:
        print("Could not create Canary analysis dataset due to missing arrivals or environmental data.")

    if not df_mainland_sea_arrivals.empty and not env_data_mainland.empty:
        df_mainland_analysis = df_mainland_sea_arrivals.join(env_data_mainland, how='inner')
        print(f"Mainland sea analysis dataset created: {df_mainland_analysis.shape[0]} months, columns: {df_mainland_analysis.columns.tolist()}")
    else:
        print("Could not create Mainland sea analysis dataset due to missing arrivals or environmental data.")

    print("\n--- Data Extraction & Preprocessing Complete ---")

    if not df_canary_analysis.empty:
        print("\nCanary Analysis DataFrame Head:")
        print(df_canary_analysis.head())
        df_canary_analysis.to_csv("canary_analysis_data.csv")
        print("\nSaved canary_analysis_data.csv")

    if not df_mainland_analysis.empty:
        print("\nMainland Sea Analysis DataFrame Head:")
        print(df_mainland_analysis.head())
        df_mainland_analysis.to_csv("mainland_sea_analysis_data.csv")
        print("Saved mainland_sea_analysis_data.csv")

    if not df_mainland_land_arrivals.empty:
        df_mainland_land_arrivals.to_csv("mainland_land_arrivals.csv")
        print("Saved mainland_land_arrivals.csv")

    # Perform Analysis and Visualization
    if not df_canary_analysis.empty:
        canary_correlations, canary_corr_matrix = perform_correlation_analysis(df_canary_analysis, "arrivals_canary", "Canary Islands Route")
        if canary_correlations:
            visualize_findings(df_canary_analysis, "arrivals_canary", "Canary_Islands_Route", canary_correlations, canary_corr_matrix)
    else:
        print("Skipping Canary Islands analysis as data is missing.")

    if not df_mainland_analysis.empty:
        mainland_correlations, mainland_corr_matrix = perform_correlation_analysis(df_mainland_analysis, "arrivals_mainland_sea", "Mainland Sea Route")
        if mainland_correlations:
            visualize_findings(df_mainland_analysis, "arrivals_mainland_sea", "Mainland_Sea_Route", mainland_correlations, mainland_corr_matrix)
    else:
        print("Skipping Mainland Sea Route analysis as data is missing.")

    print("\n--- Analysis and Visualization Script Execution Complete ---")
