import pandas as pd
import numpy as np
import joblib # For loading models

# --- Load Data and Models ---
print("--- Loading data and models for forecasting exercise ---")
test_df_t1 = None
test_df_t3 = None
rf_model_t1 = None
rf_model_t3 = None
master_df = None

try:
    test_df_t1 = pd.read_csv('test_data_with_predictions_t1.csv', parse_dates=['Date'])
    print("Loaded test_data_with_predictions_t1.csv")
except FileNotFoundError:
    print("Error: test_data_with_predictions_t1.csv not found. Past 1-month forecasts cannot be displayed.")

try:
    test_df_t3 = pd.read_csv('test_data_with_predictions_t3.csv', parse_dates=['Date'])
    print("Loaded test_data_with_predictions_t3.csv")
except FileNotFoundError:
    print("Warning: test_data_with_predictions_t3.csv not found. Past 3-month forecast display will be limited.")

try:
    rf_model_t1 = joblib.load('rf_model_t1.joblib')
    print("Loaded rf_model_t1.joblib")
except FileNotFoundError:
    print("Error: rf_model_t1.joblib not found. Cannot make new 1-month forecasts.")

try:
    rf_model_t3 = joblib.load('rf_model_t3.joblib')
    print("Loaded rf_model_t3.joblib")
except FileNotFoundError:
    print("Warning: rf_model_t3.joblib not found. Cannot make new 3-month forecasts.")

try:
    master_df = pd.read_csv('master_dataset_with_features.csv', parse_dates=['Date'])
    print(f"Loaded master_dataset_with_features.csv for potential new forecast input generation (shape: {master_df.shape})")
except FileNotFoundError:
    print("Error: master_dataset_with_features.csv not found. Cannot prepare inputs for new forecasts.")

# --- Displaying Past Forecasts (from test set saved by estimate_rf_models.py) ---
if test_df_t1 is not None and not test_df_t1.empty:
    print("\n--- Sample of 1-Month Ahead Forecasts (from previously saved test set predictions) ---")
    sample_nationalities_t1 = test_df_t1['Nationality'].unique()
    if len(sample_nationalities_t1) > 0:
        # Display for a few countries, last few available predictions
        display_countries = sample_nationalities_t1[:min(3, len(sample_nationalities_t1))]
        print(test_df_t1[test_df_t1['Nationality'].isin(display_countries)][['Date', 'Nationality', 'Encounters', 'Predicted_Encounters_t1']].tail(15))
    else:
        print("No nationalities found in test_df_t1 to display.")
else:
    print("No 1-month ahead test predictions to display.")

if test_df_t3 is not None and not test_df_t3.empty:
    print("\n--- Sample of 3-Months Ahead Forecasts (from previously saved test set predictions) ---")
    sample_nationalities_t3 = test_df_t3['Nationality'].unique()
    if len(sample_nationalities_t3) > 0:
        display_countries_t3 = sample_nationalities_t3[:min(3, len(sample_nationalities_t3))]
        print(test_df_t3[test_df_t3['Nationality'].isin(display_countries_t3)][['Date', 'Nationality', 'Encounters_target_t_plus_3', 'Predicted_Encounters_t3']].rename(columns={'Encounters_target_t_plus_3': 'Actual_Encounters_t+3'}).tail(15))
    else:
        print("No nationalities found in test_df_t3 to display.")
else:
    print("No 3-month ahead test predictions to display.")

# --- Generating New Forecasts (Conceptual Outline) ---
print("\n--- Generating New Forecasts (Conceptual) ---")
if master_df is not None and (rf_model_t1 is not None or rf_model_t3 is not None):
    print("To generate new forecasts (e.g., for the next available month after existing data):")
    print("1. Identify the last known date in 'master_dataset_with_features.csv'.")
    last_date_in_data = master_df['Date'].max()
    print(f"   Last date in data: {last_date_in_data.strftime('%Y-%m-%d')}")

    print("2. For each country, construct feature vectors for future time steps (e.g., t+1, t+3). This involves:")
    print("   - Appending rows for future dates.")
    print("   - Calculating time-based features for these new dates.")
    print("   - Using known actuals to calculate necessary lags and rolling window features.")
    print("   - Obtaining future values for exogenous variables (US econ, GDELT - this is the hardest part for real forecasts).")
    print("     (For this exercise, we'd typically use the last known values or simple projections if actual future values aren't available).")

    # Example: Forecasting for the month after the last date in master_df
    # This is a simplified illustration and assumes feature generation is handled.

    # To make this runnable with current structure, we'd need to take the very last
    # complete feature rows from master_df (after NaN cleaning similar to estimate_rf_models)
    # and use those to predict the "next" step.

    # Re-apply cleaning to get the latest usable feature rows from the full dataset
    temp_df_cleaned = master_df.copy()
    if 'DistanceToUSBORDER_km' in temp_df_cleaned.columns and temp_df_cleaned['DistanceToUSBORDER_km'].isnull().any():
        mean_dist = temp_df_cleaned['DistanceToUSBORDER_km'].mean()
        temp_df_cleaned['DistanceToUSBORDER_km'].fillna(mean_dist if not pd.isna(mean_dist) else 0, inplace=True)
    if 'GDELT_EventCount' in temp_df_cleaned.columns:
        temp_df_cleaned['GDELT_EventCount'] = temp_df_cleaned['GDELT_EventCount'].fillna(0)

    critical_features_for_dropna = [col for col in temp_df_cleaned.columns if 'lag_' in col or 'roll_std_' in col or 'roll_mean_' in col or ('US_' in col and 'lag' in col)]
    temp_df_cleaned.dropna(subset=critical_features_for_dropna, inplace=True)
    temp_df_cleaned.dropna(subset=['DistanceToUSBORDER_km', 'GDELT_EventCount'], inplace=True)


    if not temp_df_cleaned.empty:
        temp_df_cleaned['Nationality_Code'] = temp_df_cleaned['Nationality'].astype('category').cat.codes
        features_for_forecast = [f for f in rf_model_t1.feature_names_in_ if f in temp_df_cleaned.columns] # Use features model was trained on

        # Get the latest available full feature set for each country
        latest_features_df = temp_df_cleaned.loc[temp_df_cleaned.groupby('Nationality')['Date'].idxmax()]

        if not latest_features_df.empty and all(f in latest_features_df.columns for f in features_for_forecast):
            if rf_model_t1:
                new_preds_t1 = rf_model_t1.predict(latest_features_df[features_for_forecast])
                forecast_output_t1 = latest_features_df[['Nationality', 'Date']].copy()
                forecast_output_t1['Forecast_Date_t+1'] = forecast_output_t1['Date'] + pd.DateOffset(months=1)
                forecast_output_t1['Forecasted_Encounters_t+1'] = new_preds_t1
                print("\nSample of NEW 1-Month Ahead Forecasts (based on latest data in master_dataset_with_features):")
                print(forecast_output_t1[['Nationality', 'Forecast_Date_t+1', 'Forecasted_Encounters_t+1']].head())

            if rf_model_t3: # Assuming features for t+3 are the same as for t+1 direct model
                new_preds_t3 = rf_model_t3.predict(latest_features_df[features_for_forecast])
                forecast_output_t3 = latest_features_df[['Nationality', 'Date']].copy()
                forecast_output_t3['Forecast_Date_t+3'] = forecast_output_t3['Date'] + pd.DateOffset(months=3)
                forecast_output_t3['Forecasted_Encounters_t+3'] = new_preds_t3
                print("\nSample of NEW 3-Months Ahead Forecasts (based on latest data, direct model):")
                print(forecast_output_t3[['Nationality', 'Forecast_Date_t+3', 'Forecasted_Encounters_t+3']].head())
        else:
            print("Could not prepare features for new forecasts from master_df (likely due to NaNs or missing columns).")
    else:
        print("No usable data rows found in master_df after cleaning for new forecasts.")

else:
    print("Master dataset or models not loaded. Cannot generate new forecasts.")

print("\n--- Forecasting Exercise Step Complete ---")
print("Displayed past test-set predictions and outlined conceptual new forecasts.")
print("Full GDELT, climate, food insecurity, and actual US economic data integration is pending for a more robust model.")
