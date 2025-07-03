import pandas as pd
import glob
import requests
import zipfile
import io
import os

# Define file names globally for cleanup
FILE_2019_PRESENT = 'encounters_2019_present.csv'
FILE_2013_PRESENT = 'encounters_2013_present.csv'
COUNTRY_DISTANCES_CSV = 'country_distances.csv'
US_ECON_CSV = 'us_econ_monthly.csv'
GDELT_DAILY_SAMPLE_CSV = 'gdelt_violence_events_daily_20230101.csv'
MASTER_DATASET_CSV = 'master_dataset_final_sample.csv'
PRIMARY_MIGRATION_CSV = 'us_border_encounters_monthly.csv'


def download_csv_from_google_sheets(url, output_filename):
    """Downloads a CSV from a Google Sheets export URL."""
    print(f"Downloading {output_filename} from {url}...")
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        with open(output_filename, 'wb') as f:
            f.write(response.content)
        print(f"Successfully downloaded {output_filename}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {output_filename}: {e}")
        if os.path.exists(output_filename):
            os.remove(output_filename)
        return False

def preprocess_main_migration_data():
    print("Starting main migration data preprocessing...")
    url_2019_present = "https://docs.google.com/spreadsheets/d/1QIVCWAZgYVuDx0aaD1ib4BhethPP5s5gymxreb5KVHk/export?format=csv"
    url_2013_present = "https://docs.google.com/spreadsheets/d/1n0-Lb2ZewwBxXFSuNjYpgElZbyBnXARIB0cZF6VvNac/export?format=csv"

    if not (os.path.exists(FILE_2019_PRESENT) and os.path.getsize(FILE_2019_PRESENT) > 1000):
        if not download_csv_from_google_sheets(url_2019_present, FILE_2019_PRESENT):
            return pd.DataFrame()
    else:
        print(f"{FILE_2019_PRESENT} already exists. Skipping download.")

    if not (os.path.exists(FILE_2013_PRESENT) and os.path.getsize(FILE_2013_PRESENT) > 1000):
        if not download_csv_from_google_sheets(url_2013_present, FILE_2013_PRESENT):
            return pd.DataFrame()
    else:
        print(f"{FILE_2013_PRESENT} already exists. Skipping download.")

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
        except FileNotFoundError: return pd.DataFrame()
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
        print(f"Sheet {sheet_id} ({csv_path}) - Processed rows: {len(df_melted)}")
        return df_melted[['Nationality', 'Date', 'Encounters']].sort_values(by=['Nationality', 'Date'])

    df1 = preprocess_single_sheet(FILE_2019_PRESENT, '2019_present', is_problematic_date_range=True)
    df2 = preprocess_single_sheet(FILE_2013_PRESENT, '2013_present')

    if df1.empty and df2.empty: return pd.DataFrame()
    combined_df = pd.concat([df2, df1], ignore_index=True).sort_values(by=['Date'], ascending=True)
    combined_df = combined_df.drop_duplicates(subset=['Nationality', 'Date'], keep='last')
    combined_df = combined_df.sort_values(by=['Nationality', 'Date']).reset_index(drop=True)
    combined_df.to_csv(PRIMARY_MIGRATION_CSV, index=False)
    print(f"Combined migration data saved to {PRIMARY_MIGRATION_CSV} with {len(combined_df)} rows.")
    if not combined_df.empty:
        print(f"Date range: {combined_df['Date'].min()} to {combined_df['Date'].max()}")
        print(f"Unique countries: {combined_df['Nationality'].nunique()}")
    return combined_df

def download_and_unzip_gdelt_event_data(date_str, target_filename="temp_gdelt_event.csv"):
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
                with z.open(csv_name_in_zip) as zf, open(target_filename, 'wb') as f_out:
                    f_out.write(zf.read())
                print(f"Successfully downloaded and unzipped to {target_filename}")
                return target_filename
            else: return None
    except Exception as e:
        print(f"An error occurred during download/unzip of GDELT Event Data: {e}")
        return None

def process_gdelt_event_file(filepath):
    try:
        print(f"Processing GDELT Event file: {filepath}")
        # GDELT 1.0 Event data has 58 columns
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
            'DistanceToUSBORDER_km': [100, 1500, 1800, 1600, 2000, 4000, 3000, 3500, 2000, 4500, 2500, 5000, 12000, 10000]}
    df = pd.DataFrame(data)
    df['Nationality'] = df['Nationality'].str.title()
    df.to_csv(COUNTRY_DISTANCES_CSV, index=False)
    print(f"Saved {COUNTRY_DISTANCES_CSV}")
    return df

def get_us_economic_data():
    print("Creating US economic data (placeholder)...")
    dates = pd.to_datetime([f'2023-{str(m).zfill(2)}-01' for m in range(1,13)])
    job_openings = [9000000 + i*10000 for i in range(12)]
    construction_openings = [800000 + i*5000 for i in range(12)]
    df = pd.DataFrame({'Date': dates,
                       'US_Hospitality_JobOpenings': job_openings,
                       'US_Construction_JobOpenings': construction_openings})
    df.to_csv(US_ECON_CSV, index=False)
    print(f"Saved {US_ECON_CSV}")
    return df

# --- Main processing flow ---
migration_df = preprocess_main_migration_data()

gdelt_event_target_csv = "temp_gdelt_event_20230101.csv"
downloaded_event_file_path = download_and_unzip_gdelt_event_data("20230101", gdelt_event_target_csv)
gdelt_processed_event_data = pd.DataFrame()

if downloaded_event_file_path and os.path.exists(downloaded_event_file_path):
    gdelt_sample_df = process_gdelt_event_file(downloaded_event_file_path)
    if not gdelt_sample_df.empty:
        gdelt_sample_df.to_csv(GDELT_DAILY_SAMPLE_CSV, index=False)
        print(f"Processed GDELT Event sample saved to {GDELT_DAILY_SAMPLE_CSV}")
        gdelt_processed_event_data = gdelt_sample_df
    else: print("No data extracted from GDELT Event sample.")
    if os.path.exists(downloaded_event_file_path): os.remove(downloaded_event_file_path)
else: print("GDELT Event sample data could not be downloaded/processed.")

country_distances_df = get_country_distances()
us_econ_df = get_us_economic_data()

if not migration_df.empty:
    master_df = migration_df.copy()
    master_df['Date'] = pd.to_datetime(master_df['Date'])

    if not country_distances_df.empty:
        master_df = pd.merge(master_df, country_distances_df, on='Nationality', how='left')
        print("Merged country distances data.")

    if not us_econ_df.empty:
        master_df['MonthYear_dt'] = master_df['Date'].dt.to_period('M')
        us_econ_df['MonthYear_dt'] = us_econ_df['Date'].dt.to_period('M')
        master_df = pd.merge(master_df, us_econ_df.drop(columns=['Date']), on='MonthYear_dt', how='left')
        master_df = master_df.drop(columns=['MonthYear_dt'], errors='ignore')
        print("Merged US economic data.")

    if not gdelt_processed_event_data.empty:
        gdelt_processed_event_data['MonthYear_dt_gdelt'] = gdelt_processed_event_data['Date'].dt.to_period('M')
        gdelt_monthly_agg = gdelt_processed_event_data.groupby(['MonthYear_dt_gdelt', 'FIPS_CountryCode'])['EventCount'].sum().reset_index()

        master_df['MonthYear_dt_gdelt'] = master_df['Date'].dt.to_period('M')
        master_df = pd.merge(master_df, gdelt_monthly_agg,
                             on=['MonthYear_dt_gdelt', 'FIPS_CountryCode'], how='left')
        master_df.rename(columns={'EventCount': 'GDELT_EventCount'}, inplace=True)
        master_df['GDELT_EventCount'] = master_df['GDELT_EventCount'].fillna(0)
        master_df.drop(columns=['MonthYear_dt_gdelt'], inplace=True, errors='ignore')
        print("Merged sample GDELT data (aggregated to monthly).")

    master_df.to_csv(MASTER_DATASET_CSV, index=False)
    print(f"Final (sample) master dataset saved to {MASTER_DATASET_CSV} with shape {master_df.shape}")
    print("\nMaster DataFrame info:"); master_df.info()
    print("\nMaster DataFrame head:"); print(master_df.head())
else:
    print("Main migration data file not found or empty. Cannot proceed.")

# Cleanup
files_to_remove = [FILE_2019_PRESENT, FILE_2013_PRESENT, COUNTRY_DISTANCES_CSV, US_ECON_CSV, GDELT_DAILY_SAMPLE_CSV]
for f_path in files_to_remove:
    if os.path.exists(f_path):
        try: os.remove(f_path); print(f"Removed temp/intermediate file: {f_path}")
        except OSError as e: print(f"Error removing file {f_path}: {e}")

print("\\nEnd of database creation step.")
