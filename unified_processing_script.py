import pandas as pd
import glob
import requests
import zipfile
import io
import os
import numpy as np

# --- Global File Names ---
FILE_2019_PRESENT = 'encounters_2019_present.csv'
FILE_2013_PRESENT = 'encounters_2013_present.csv'
COUNTRY_DISTANCES_CSV = 'country_distances.csv'
US_ECON_CSV = 'us_econ_monthly.csv'
GDELT_DAILY_SAMPLE_CSV = 'gdelt_violence_events_daily_20230101.csv'
TEMP_GDELT_EVENT_CSV = "temp_gdelt_event_20230101.csv"
PRIMARY_MIGRATION_CSV = 'us_border_encounters_monthly.csv'
MASTER_DATASET_WITH_FEATURES_CSV = 'master_dataset_with_features.csv' # This will be the main output of this script

# --- Part 1: Database Creation / Preprocessing ---

def download_csv_from_google_sheets(url, output_filename):
    print(f"Downloading {output_filename} from {url}...")
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        with open(output_filename, 'wb') as f: f.write(response.content)
        print(f"Successfully downloaded {output_filename}")
        return True
    except Exception as e:
        print(f"Error downloading {output_filename}: {e}")
        if os.path.exists(output_filename):
            try: os.remove(output_filename)
            except OSError: pass
        return False

def preprocess_main_migration_data():
    print("Starting main migration data preprocessing...")
    url_2019_present = "https://docs.google.com/spreadsheets/d/1QIVCWAZgYVuDx0aaD1ib4BhethPP5s5gymxreb5KVHk/export?format=csv"
    url_2013_present = "https://docs.google.com/spreadsheets/d/1n0-Lb2ZewwBxXFSuNjYpgElZbyBnXARIB0cZF6VvNac/export?format=csv"

    dl1_success = True
    if not (os.path.exists(FILE_2019_PRESENT) and os.path.getsize(FILE_2019_PRESENT) > 1000): # Check for existing non-empty file
        dl1_success = download_csv_from_google_sheets(url_2019_present, FILE_2019_PRESENT)
    else: print(f"{FILE_2019_PRESENT} already exists. Skipping download.")

    dl2_success = True
    if not (os.path.exists(FILE_2013_PRESENT) and os.path.getsize(FILE_2013_PRESENT) > 1000): # Check for existing non-empty file
        dl2_success = download_csv_from_google_sheets(url_2013_present, FILE_2013_PRESENT)
    else: print(f"{FILE_2013_PRESENT} already exists. Skipping download.")

    if not (dl1_success and dl2_success and os.path.exists(FILE_2019_PRESENT) and os.path.exists(FILE_2013_PRESENT)):
        print("Critical error: Failed to download one or both migration CSVs. Cannot proceed.")
        return pd.DataFrame()


    def parse_date_flexible(date_str):
        try: return pd.to_datetime(date_str, format='%b %Y')
        except ValueError:
            try:
                if '-' in date_str and len(date_str.split('-')[1]) == 2:
                    month, year_short = date_str.split('-')
                    year_full = int('20' + year_short)
                    return pd.to_datetime(f"{month} {year_full}", format='%b %Y')
                return pd.to_datetime(date_str, format='%b-%y')
            except ValueError: return pd.NaT

    def preprocess_single_sheet(csv_path, sheet_id, is_problematic_date_range=False):
        try: df = pd.read_csv(csv_path, header=0, low_memory=False)
        except FileNotFoundError: print(f"Error: {csv_path} not found."); return pd.DataFrame()
        nationality_col = df.columns[0]
        df = df.rename(columns={nationality_col: 'Nationality'})
        valid_rows_mask = ~df['Nationality'].astype(str).str.contains('Total|Other Countries|All Other|Unknown', case=False, na=True)
        df = df[valid_rows_mask].copy()
        df.dropna(subset=['Nationality'], inplace=True)
        df_melted = df.melt(id_vars=['Nationality'], var_name='DateStr', value_name='Encounters')
        df_melted['Encounters'] = pd.to_numeric(df_melted['Encounters'].astype(str).str.replace(',', ''), errors='coerce').fillna(0).astype(int)
        df_melted['Nationality'] = df_melted['Nationality'].str.strip().str.title()
        df_melted['Date'] = df_melted['DateStr'].apply(parse_date_flexible)
        df_melted = df_melted.dropna(subset=['Date', 'Nationality'])
        df_melted = df_melted[df_melted['Nationality'].str.len() > 0]
        if is_problematic_date_range: df_melted = df_melted[df_melted['Date'] < pd.to_datetime('2024-07-01')]
        return df_melted[['Nationality', 'Date', 'Encounters']].sort_values(by=['Nationality', 'Date'])

    df1 = preprocess_single_sheet(FILE_2019_PRESENT, '2019_present', is_problematic_date_range=True)
    df2 = preprocess_single_sheet(FILE_2013_PRESENT, '2013_present')

    if df1.empty and df2.empty: return pd.DataFrame()
    combined_df = pd.concat([df2, df1], ignore_index=True).sort_values(by=['Date'], ascending=True)
    combined_df = combined_df.drop_duplicates(subset=['Nationality', 'Date'], keep='last')
    combined_df = combined_df.sort_values(by=['Nationality', 'Date']).reset_index(drop=True)
    combined_df.to_csv(PRIMARY_MIGRATION_CSV, index=False)
    print(f"Combined migration data saved to {PRIMARY_MIGRATION_CSV} ({len(combined_df)} rows).")
    return combined_df

def download_and_unzip_gdelt_event_data(date_str, target_filename):
    base_url = "http://data.gdeltproject.org/events/"
    zip_filename = f"{date_str}.export.CSV.zip"
    file_url = base_url + zip_filename
    print(f"Downloading GDELT Event Data: {file_url}...")
    try:
        r = requests.get(file_url, stream=True, timeout=60)
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            csv_name_in_zip = f"{date_str}.export.CSV"
            if csv_name_in_zip in z.namelist():
                with z.open(csv_name_in_zip) as zf, open(target_filename, 'wb') as f_out: f_out.write(zf.read())
                print(f"Successfully downloaded and unzipped to {target_filename}")
                return target_filename
            else: return None
    except Exception as e: print(f"Error GDELT download/unzip: {e}"); return None

def process_gdelt_event_file(filepath):
    try:
        print(f"Processing GDELT Event file: {filepath}")
        column_names_v1 = [
            "GLOBALEVENTID", "Day", "MonthYear", "Year", "FractionDate", "Actor1Code", "Actor1Name",
            "Actor1CountryCode", "Actor1KnownGroupCode", "Actor1EthnicCode", "Actor1Religion1Code",
            "Actor1Religion2Code", "Actor1Type1Code", "Actor1Type2Code", "Actor1Type3Code", "Actor2Code",
            "Actor2Name", "Actor2CountryCode", "Actor2KnownGroupCode", "Actor2EthnicCode", "Actor2Religion1Code",
            "Actor2Religion2Code", "Actor2Type1Code", "Actor2Type2Code", "Actor2Type3Code", "IsRootEvent",
            "EventCode", "EventBaseCode", "EventRootCode", "QuadClass", "GoldsteinScale", "NumMentions",
            "NumSources", "NumArticles", "AvgTone", "Actor1Geo_Type", "Actor1Geo_Fullname",
            "Actor1Geo_CountryCode", "Actor1Geo_ADM1Code", "Actor1Geo_Lat", "Actor1Geo_Long",
            "Actor1Geo_FeatureID", "Actor2Geo_Type", "Actor2Geo_Fullname", "Actor2Geo_CountryCode",
            "Actor2Geo_ADM1Code", "Actor2Geo_Lat", "Actor2Geo_Long", "Actor2Geo_FeatureID", "ActionGeo_Type",
            "ActionGeo_Fullname", "ActionGeo_CountryCode", "ActionGeo_ADM1Code", "ActionGeo_Lat",
            "ActionGeo_Long", "ActionGeo_FeatureID", "DATEADDED", "SOURCEURL"
        ]
        event_df = pd.read_csv(filepath, sep='\t', header=None, names=column_names_v1, encoding='latin1', on_bad_lines='warn', low_memory=False)
        relevant_event_root_codes = ['14', '17', '18', '19', '20']
        event_df['EventRootCode'] = event_df['EventRootCode'].astype(str)
        df_filtered = event_df[event_df['EventRootCode'].isin(relevant_event_root_codes)].copy()
        if df_filtered.empty: return pd.DataFrame()
        df_agg = df_filtered.groupby(['Day', 'ActionGeo_CountryCode']).size().reset_index(name='EventCount')
        df_agg.rename(columns={'Day': 'DateStr', 'ActionGeo_CountryCode': 'FIPS_CountryCode'}, inplace=True)
        df_agg['Date'] = pd.to_datetime(df_agg['DateStr'], format='%Y%m%d')
        return df_agg[['Date', 'FIPS_CountryCode', 'EventCount']]
    except Exception as e:
        print(f"Error processing GDELT Event file {filepath}: {e}")
        return pd.DataFrame()

def get_country_distances():
    print("Creating country distances data (placeholder)...")
    data = {'Nationality': ['Mexico', 'Guatemala', 'Honduras', 'El Salvador', 'Cuba', 'Venezuela', 'Ecuador', 'Colombia', 'Nicaragua', 'Peru', 'Haiti', 'Brazil', 'India', 'China'],
            'FIPS_CountryCode': ['MX', 'GT', 'HN', 'ES', 'CU', 'VE', 'EC', 'CO', 'NU', 'PE', 'HA', 'BR', 'IN', 'CH'],
            'DistanceToUSBORDER_km': [100,1500,1800,1600,2000,4000,3000,3500,2000,4500,2500,5000,12000,10000]}
    df = pd.DataFrame(data); df['Nationality'] = df['Nationality'].str.title()
    df.to_csv(COUNTRY_DISTANCES_CSV, index=False); print(f"Saved {COUNTRY_DISTANCES_CSV}"); return df

def get_us_economic_data():
    print("Creating US economic data (placeholder)...")
    dates = pd.to_datetime([f'2023-{str(m).zfill(2)}-01' for m in range(1,13)])
    df = pd.DataFrame({'Date': dates,
                       'US_Hospitality_JobOpenings': [9000000+i*10000 for i in range(12)],
                       'US_Construction_JobOpenings': [800000+i*5000 for i in range(12)]})
    df.to_csv(US_ECON_CSV, index=False); print(f"Saved {US_ECON_CSV}"); return df

def create_time_based_features(df):
    df = df.copy(); df['Date'] = pd.to_datetime(df['Date'])
    df['Year'] = df['Date'].dt.year; df['Month'] = df['Date'].dt.month
    df['Quarter'] = df['Date'].dt.quarter
    df['TimeIndex'] = (df['Date'].dt.year * 12 + df['Date'].dt.month) - (df['Date'].dt.year.min() * 12 + df['Date'].dt.month.min())
    print("Created time-based features."); return df

def create_lagged_features(df, column_name, lags, group_col='Nationality'):
    df = df.copy()
    if group_col and group_col not in df.columns:
        print(f"Warning: Group column '{group_col}' not found for lagging '{column_name}'. Global lag applied.")
        group_col = None
    for lag in lags:
        if group_col: df[f'{column_name}_lag_{lag}'] = df.groupby(group_col)[column_name].shift(lag)
        else: df[f'{column_name}_lag_{lag}'] = df[column_name].shift(lag)
    print(f"Created lagged features for {column_name} (lags: {lags})."); return df

def create_rolling_features(df, column_name, windows, agg_funcs=['mean', 'std']):
    df = df.copy()
    for window in windows:
        for func_name in agg_funcs:
            if column_name in df and pd.api.types.is_numeric_dtype(df[column_name]):
                gb_operation = df.groupby('Nationality')[column_name].rolling(window=window, min_periods=1)
                if func_name == 'mean': result = gb_operation.mean()
                elif func_name == 'std': result = gb_operation.std()
                else: continue
                df[f'{column_name}_roll_{func_name}_{window}m'] = result.reset_index(level=0, drop=True)
            else: print(f"Skipping rolling for {column_name} (not found or not numeric).")
    print(f"Created rolling features for {column_name}."); return df

# --- Main Execution ---
print("=== Starting Unified Processing Script ===")
migration_df = preprocess_main_migration_data()
if migration_df.empty: exit()

gdelt_processed_event_data = pd.DataFrame()
if not os.path.exists(GDELT_DAILY_SAMPLE_CSV):
    dl_path = download_and_unzip_gdelt_event_data("20230101", TEMP_GDELT_EVENT_CSV)
    if dl_path and os.path.exists(dl_path):
        gdelt_sample_df = process_gdelt_event_file(dl_path)
        if not gdelt_sample_df.empty:
            gdelt_sample_df.to_csv(GDELT_DAILY_SAMPLE_CSV, index=False)
            gdelt_processed_event_data = gdelt_sample_df
        if os.path.exists(dl_path): os.remove(dl_path)
    else: print("GDELT Event sample data could not be downloaded/processed.")
elif os.path.exists(GDELT_DAILY_SAMPLE_CSV):
    gdelt_processed_event_data = pd.read_csv(GDELT_DAILY_SAMPLE_CSV, parse_dates=['Date'])

country_distances_df = get_country_distances(); us_econ_df = get_us_economic_data()
master_df = migration_df.copy()
if not country_distances_df.empty: master_df = pd.merge(master_df, country_distances_df, on='Nationality', how='left')
if not us_econ_df.empty:
    master_df['MonthYear_dt'] = master_df['Date'].dt.to_period('M')
    us_econ_df['MonthYear_dt'] = us_econ_df['Date'].dt.to_period('M')
    master_df = pd.merge(master_df, us_econ_df.drop(columns=['Date']), on='MonthYear_dt', how='left')
    master_df.drop(columns=['MonthYear_dt'], inplace=True, errors='ignore')
if not gdelt_processed_event_data.empty:
    gdelt_processed_event_data['MonthYear_dt_gdelt'] = gdelt_processed_event_data['Date'].dt.to_period('M')
    gdelt_monthly_agg = gdelt_processed_event_data.groupby(['MonthYear_dt_gdelt', 'FIPS_CountryCode'])['EventCount'].sum().reset_index()
    master_df['MonthYear_dt_gdelt'] = master_df['Date'].dt.to_period('M')
    master_df = pd.merge(master_df, gdelt_monthly_agg, on=['MonthYear_dt_gdelt', 'FIPS_CountryCode'], how='left')
    master_df.rename(columns={'EventCount': 'GDELT_EventCount'}, inplace=True)
    master_df['GDELT_EventCount'] = master_df['GDELT_EventCount'].fillna(0)
    master_df.drop(columns=['MonthYear_dt_gdelt'], inplace=True, errors='ignore')
else: master_df['GDELT_EventCount'] = 0

master_df = create_time_based_features(master_df)
master_df = create_lagged_features(master_df, 'Encounters', [1,2,3,6,12])
master_df = create_rolling_features(master_df, 'Encounters', [3,6,12])
if 'GDELT_EventCount' in master_df.columns and master_df['GDELT_EventCount'].sum() > 0:
    master_df = create_lagged_features(master_df, 'GDELT_EventCount', [1,2,3])
else: print("Skipping GDELT lagged features.")

econ_cols_to_lag = ['US_Hospitality_JobOpenings', 'US_Construction_JobOpenings']
temp_df_for_econ_lags = master_df[['Date'] + econ_cols_to_lag].drop_duplicates(subset=['Date']).sort_values(by='Date').reset_index(drop=True)
for col in econ_cols_to_lag:
    if col in temp_df_for_econ_lags.columns:
        temp_df_for_econ_lags = create_lagged_features(temp_df_for_econ_lags, col, [1,2,3], group_col=None)
lagged_econ_cols_to_merge = [col for col in temp_df_for_econ_lags.columns if '_lag_' in col]
if lagged_econ_cols_to_merge:
     master_df = pd.merge(master_df, temp_df_for_econ_lags[['Date'] + lagged_econ_cols_to_merge], on='Date', how='left')
     print("Merged lagged US economic features.")

master_df.to_csv(MASTER_DATASET_WITH_FEATURES_CSV, index=False)
print(f"Saved final dataset with features to {MASTER_DATASET_WITH_FEATURES_CSV}")

files_to_remove = [FILE_2019_PRESENT, FILE_2013_PRESENT, COUNTRY_DISTANCES_CSV, US_ECON_CSV, GDELT_DAILY_SAMPLE_CSV, TEMP_GDELT_EVENT_CSV, PRIMARY_MIGRATION_CSV]
for f_path in files_to_remove:
    if os.path.exists(f_path):
        try: os.remove(f_path); print(f"Removed temp file: {f_path}")
        except OSError as e: print(f"Error removing {f_path}: {e}")
print("\\n=== Unified Processing Script Finished ===")
