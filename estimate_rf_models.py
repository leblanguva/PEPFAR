import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib

# Load the dataset with features
try:
    df = pd.read_csv('master_dataset_with_features.csv', parse_dates=['Date'])
    print(f"Loaded master_dataset_with_features.csv with shape: {df.shape}")
except FileNotFoundError:
    print("Error: master_dataset_with_features.csv not found. Please run the unified_processing_script.py first.")
    exit()

# --- Data Cleaning and Preparation for Modeling ---
print("\n--- Preparing data for modeling ---")

if 'DistanceToUSBORDER_km' in df.columns and df['DistanceToUSBORDER_km'].isnull().any():
    mean_distance = df['DistanceToUSBORDER_km'].mean()
    if pd.isna(mean_distance): # Handle case where whole column might be NaN (e.g. if no countries matched distance file)
        mean_distance = 0
    df['DistanceToUSBORDER_km'].fillna(mean_distance, inplace=True)
    print(f"Filled NaN in 'DistanceToUSBORDER_km' with value: {mean_distance:.2f}")

if 'GDELT_EventCount' in df.columns:
    df['GDELT_EventCount'] = df['GDELT_EventCount'].fillna(0).astype(float)

# Drop rows with NaNs in features critical for prediction (lags, rolling stats, econ data)
# Also ensure key static/merged features don't cause full column NaNs leading to empty df after dropna
cols_to_check_for_nan_before_drop = ['DistanceToUSBORDER_km', 'GDELT_EventCount'] + \
                                    [col for col in df.columns if 'US_' in col and 'lag' not in col]
for col in cols_to_check_for_nan_before_drop:
    if col in df.columns and df[col].isnull().all():
        print(f"Warning: Column {col} is all NaN before critical dropna. Filling with 0 to avoid empty DataFrame.")
        df[col].fillna(0, inplace=True)

# Define columns that, if NaN, make the row unusable for training/prediction
# These are typically lagged versions of the target or key exogenous variables
# Or features derived from them like rolling means/stds
critical_lag_roll_features = [col for col in df.columns if 'lag_' in col or 'roll_std' in col or 'roll_mean' in col]
# Add specific econ features if they are crucial and might have leading NaNs after lagging
critical_lag_roll_features += [col for col in df.columns if ('US_Hospitality_JobOpenings' in col or 'US_Construction_JobOpenings' in col) and 'lag' in col]

df_cleaned = df.dropna(subset=critical_lag_roll_features).copy()
df_cleaned.dropna(subset=['DistanceToUSBORDER_km', 'GDELT_EventCount'], inplace=True) # Final check on key static/exog features

print(f"Shape after dropping NaNs from critical features: {df_cleaned.shape}")

if df_cleaned.empty:
    print("DataFrame is empty after dropping NaNs. Cannot proceed with modeling.")
    exit()

df_cleaned['Nationality_Code'] = df_cleaned['Nationality'].astype('category').cat.codes
exclude_cols = ['Encounters', 'Nationality', 'Date', 'FIPS_CountryCode', 'Encounters_target_t_plus_3']
features = [col for col in df_cleaned.columns if col not in exclude_cols and col in df_cleaned] # Ensure feature exists

X = df_cleaned[features]

# --- Train-Test Split (Time-based, more adaptive) ---
df_cleaned = df_cleaned.sort_values(by='Date')
y_actual_encounters = df_cleaned['Encounters']

unique_dates_sorted = np.sort(df_cleaned['Date'].unique())

if len(unique_dates_sorted) < 5: # Need at least a few distinct time points for a split
    print("Not enough unique dates after cleaning for a meaningful time-series split. Using random split (NOT IDEAL).")
    # Ensure X and y are aligned if we go this route
    X = df_cleaned[features]
    y_for_split = df_cleaned['Encounters']
    X_train, X_test, y_train_t1, y_test_t1 = train_test_split(X, y_for_split, test_size=0.2, random_state=42)
    # For test_df, we need to reconstruct it based on X_test.index
    train_df = df_cleaned.loc[X_train.index]
    test_df = df_cleaned.loc[X_test.index]
else:
    split_point_index = int(len(unique_dates_sorted) * 0.8)
    split_date = unique_dates_sorted[split_point_index]

    train_df = df_cleaned[df_cleaned['Date'] < split_date]
    test_df = df_cleaned[df_cleaned['Date'] >= split_date]

    # If test_df is empty or too small due to split_date being too close to max_date
    if test_df.empty or len(test_df) < 0.1 * len(df_cleaned): # Ensure test set is at least 10%
        print("Adjusting split: Test set was too small or empty. Using last 20% of rows.")
        split_row_index = int(len(df_cleaned) * 0.8)
        train_df = df_cleaned.iloc[:split_row_index]
        test_df = df_cleaned.iloc[split_row_index:]

    X_train = train_df[features]
    y_train_t1 = train_df['Encounters']
    X_test = test_df[features]
    y_test_t1 = test_df['Encounters']

print(f"Training data from {train_df['Date'].min()} to {train_df['Date'].max()} (Shape: {X_train.shape})")
print(f"Testing data from {test_df['Date'].min()} to {test_df['Date'].max()} (Shape: {X_test.shape})")

if X_train.empty or X_test.empty:
    print("Training or test set is empty after adaptive split. Cannot proceed.")
    exit()

# --- Model Training: 1-Month Ahead Forecast ---
print("\n--- Training 1-Month Ahead Random Forest Model ---")
rf_model_t1 = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1, max_depth=20, min_samples_split=5, min_samples_leaf=3)
rf_model_t1.fit(X_train, y_train_t1)
joblib.dump(rf_model_t1, 'rf_model_t1.joblib')
print("Saved 1-Month Ahead Model as rf_model_t1.joblib")

y_pred_t1 = rf_model_t1.predict(X_test)
test_df_t1_preds = test_df.copy() # Use the test_df from the 1-month split
test_df_t1_preds['Predicted_Encounters_t1'] = y_pred_t1

mae_t1 = mean_absolute_error(y_test_t1, y_pred_t1)
rmse_t1 = np.sqrt(mean_squared_error(y_test_t1, y_pred_t1))
r2_t1 = r2_score(y_test_t1, y_pred_t1)
print(f"\n1-Month Ahead Model Evaluation: MAE: {mae_t1:.2f}; RMSE: {rmse_t1:.2f}; R-squared: {r2_t1:.2f}")
test_df_t1_preds.to_csv('test_data_with_predictions_t1.csv', index=False)
print("Saved test data with 1-month ahead predictions to test_data_with_predictions_t1.csv")


# --- Model Training: 3-Months Ahead Forecast (Direct Method) ---
print("\n--- Training 3-Months Ahead Random Forest Model (Direct) ---")
df_cleaned['Encounters_target_t_plus_3'] = df_cleaned.groupby('Nationality_Code')['Encounters'].shift(-3)
df_model_t3 = df_cleaned.dropna(subset=['Encounters_target_t_plus_3'] + features).copy() # Also ensure features are not NaN for these rows

if df_model_t3.empty or len(df_model_t3['Date'].unique()) < 2:
    print("Not enough data for 3-month ahead target. Skipping 3-month model.")
else:
    df_model_t3 = df_model_t3.sort_values(by='Date')
    unique_dates_t3 = np.sort(df_model_t3['Date'].unique())

    if len(unique_dates_t3) < 5:
         print("Not enough unique dates for 3-month model time-split. Using random split (NOT IDEAL).")
         X_t3_all = df_model_t3[features]
         y_t3_all = df_model_t3['Encounters_target_t_plus_3']
         X_train_t3, X_test_t3, y_train_t3, y_test_t3 = train_test_split(X_t3_all, y_t3_all, test_size=0.2, random_state=42)
         train_df_t3 = df_model_t3.loc[X_train_t3.index] # Reconstruct for date printing
         test_df_t3 = df_model_t3.loc[X_test_t3.index]
    else:
        split_point_index_t3 = int(len(unique_dates_t3) * 0.8)
        split_date_t3 = unique_dates_t3[split_point_index_t3]
        train_df_t3 = df_model_t3[df_model_t3['Date'] < split_date_t3]
        test_df_t3 = df_model_t3[df_model_t3['Date'] >= split_date_t3]

        if test_df_t3.empty or len(test_df_t3) < 0.1 * len(df_model_t3):
            print("Adjusting split for t+3: Test set too small. Using last 20% of t+3 data.")
            split_row_index_t3 = int(len(df_model_t3) * 0.8)
            train_df_t3 = df_model_t3.iloc[:split_row_index_t3]
            test_df_t3 = df_model_t3.iloc[split_row_index_t3:]

    X_train_t3 = train_df_t3[features]
    y_train_t3 = train_df_t3['Encounters_target_t_plus_3']
    X_test_t3 = test_df_t3[features]
    y_test_t3 = test_df_t3['Encounters_target_t_plus_3']

    print(f"T+3 Training: {train_df_t3['Date'].min()} to {train_df_t3['Date'].max()} (Shape: {X_train_t3.shape})")
    print(f"T+3 Testing: {test_df_t3['Date'].min()} to {test_df_t3['Date'].max()} (Shape: {X_test_t3.shape})")

    if X_train_t3.empty or X_test_t3.empty:
        print("Training or test set for 3-month ahead model is empty. Skipping.")
    else:
        rf_model_t3 = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1, max_depth=20, min_samples_split=5, min_samples_leaf=3)
        rf_model_t3.fit(X_train_t3, y_train_t3)
        joblib.dump(rf_model_t3, 'rf_model_t3.joblib')
        print("Saved 3-Months Ahead Model as rf_model_t3.joblib")

        y_pred_t3 = rf_model_t3.predict(X_test_t3)
        test_df_t3_preds = test_df_t3.copy()
        test_df_t3_preds['Predicted_Encounters_t3'] = y_pred_t3
        test_df_t3_preds.to_csv('test_data_with_predictions_t3.csv', index=False)
        print("Saved test data with 3-month ahead predictions to test_data_with_predictions_t3.csv")

        mae_t3 = mean_absolute_error(y_test_t3, y_pred_t3)
        rmse_t3 = np.sqrt(mean_squared_error(y_test_t3, y_pred_t3))
        r2_t3 = r2_score(y_test_t3, y_pred_t3)
        print(f"\n3-Months Ahead Model Evaluation: MAE: {mae_t3:.2f}; RMSE: {rmse_t3:.2f}; R-squared: {r2_t3:.2f}")

print("\n--- Model Estimation Step Complete ---")
