import pandas as pd
import requests
import numpy as np
from scipy.stats import pearsonr, spearmanr
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import os
import itertools

from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error


# --- Configuration ---
CANARY_ARRIVALS_URL = "https://data.unhcr.org/population/get/timeseries?widget_id=613983&geo_id=729&sv_id=100&population_group=5634&frequency=month&fromDate=2017-01-01"
MAINLAND_SEA_ARRIVALS_URL = "https://data.unhcr.org/population/get/timeseries?widget_id=614001&geo_id=729&sv_id=100&population_group=4797&frequency=month&fromDate=2017-01-01"
MAINLAND_LAND_ARRIVALS_URL = "https://data.unhcr.org/population/get/timeseries?widget_id=614002&geo_id=729&sv_id=100&population_group=4798&frequency=month&fromDate=2017-01-01"
MARINE_API_URL = "https://marine-api.open-meteo.com/v1/marine"
HISTORICAL_API_URL = "https://archive-api.open-meteo.com/v1/archive"
LOCATIONS = {
    "canary": {"latitude": 27.5, "longitude": -14.5, "name": "Canary Islands Route"},
    "mainland": {"latitude": 35.9, "longitude": -5.5, "name": "Western Med Route"}
}
today = datetime.today()
first_day_current_month = today.replace(day=1)
end_of_last_month = first_day_current_month - timedelta(days=1)
START_DATE = "2017-01-01"
END_DATE = end_of_last_month.strftime("%Y-%m-%d")
MARINE_HOURLY_PARAMS = ["wave_height", "wave_direction", "wave_period", "swell_wave_height", "swell_wave_direction", "swell_wave_period", "sea_surface_temperature", "ocean_current_velocity", "ocean_current_direction"]
ATMOSPHERIC_HOURLY_PARAMS = ["wind_speed_10m", "wind_direction_10m", "precipitation", "pressure_msl", "cloud_cover"]

# --- Helper Functions (Data Extraction & Preprocessing) ---
def fetch_unhcr_data(json_url, column_name_prefix):
    try:
        response = requests.get(json_url, timeout=30); response.raise_for_status(); json_data = response.json()
        if not json_data or 'data' not in json_data or 'timeseries' not in json_data['data']: return pd.DataFrame()
        ts_content = json_data['data']['timeseries']; data_points = []
        if isinstance(ts_content, list): data_points = ts_content
        elif isinstance(ts_content, dict):
            keys = list(ts_content.keys());
            if not keys: return pd.DataFrame(); data_points = ts_content[keys[0]]
        else: return pd.DataFrame()
        if not isinstance(data_points, list) or not data_points: return pd.DataFrame()
        df = pd.DataFrame(data_points);
        if df.empty: return pd.DataFrame()
        date_created = False
        if 'unix_timestamp' in df.columns:
            try: df['date'] = pd.to_datetime(df['unix_timestamp'], unit='s'); date_created = True
            except: pass
        if not date_created and 'data_point_month' in df.columns:
            try: df['date'] = pd.to_datetime(df['data_point_month']); date_created = True
            except: pass
        if not date_created and 'month' in df.columns and 'year' in df.columns:
            try: df['date_str'] = df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01'; df['date'] = pd.to_datetime(df['date_str']); df.drop(columns=['date_str'], inplace=True); date_created = True
            except: pass
        if not date_created: return pd.DataFrame()
        df.set_index('date', inplace=True)
        ind_col = 'individuals';
        if ind_col not in df.columns: return pd.DataFrame()
        df[ind_col] = pd.to_numeric(df[ind_col], errors='coerce').fillna(0)
        arr_col_name = f"arrivals_{column_name_prefix}"; df.rename(columns={ind_col: arr_col_name}, inplace=True)
        df = df[~df.index.duplicated(keep='first')]; return df[[arr_col_name]].resample('ME').sum()
    except Exception as e: print(f"Error UNHCR {json_url}: {e}"); return pd.DataFrame()

def fetch_open_meteo_data(api_url, loc, params_list, is_marine=True):
    p = {"latitude":loc["latitude"],"longitude":loc["longitude"],"start_date":START_DATE,"end_date":END_DATE,"hourly":",".join(params_list),"timezone":"GMT"}
    if is_marine: p["cell_selection"]="sea"
    else: p.update({"models":"era5","cell_selection":"sea"})
    response = None
    try:
        response = requests.get(api_url, params=p); response.raise_for_status(); data = response.json() # Corrected: data = response.json()
        if 'hourly' not in data or 'time' not in data['hourly']: return pd.DataFrame()
        df = pd.DataFrame(data['hourly']); df['time'] = pd.to_datetime(df['time']); df.set_index('time', inplace=True)
        for col in params_list:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except Exception as e: print(f"Error OpenMeteo {loc['name']}: {e}"); return pd.DataFrame()


def aggregate_env_data_monthly(df_hr, pfx):
    if df_hr.empty: return pd.DataFrame()
    s_list = []
    dir_map = {'wave_direction':'wave_height','swell_wave_direction':'swell_wave_height','wind_direction_10m':'wind_speed_10m','ocean_current_direction':'ocean_current_velocity'}
    tmp_df = df_hr.copy()
    for dir_col, mag_col in dir_map.items():
        if dir_col in tmp_df.columns and mag_col in tmp_df.columns:
            valid = tmp_df[[mag_col, dir_col]].dropna()
            if not valid.empty:
                mag, dir_r = valid[mag_col], np.deg2rad(valid[dir_col])
                base = mag_col.replace('_height','').replace('_speed','').replace('_velocity','')
                s_list.append(pd.Series(mag*np.sin(dir_r),index=valid.index).resample('ME').mean().rename(f"{pfx}_{base}_u"))
                s_list.append(pd.Series(mag*np.cos(dir_r),index=valid.index).resample('ME').mean().rename(f"{pfx}_{base}_v"))
    for col in df_hr.columns:
        if col in dir_map or col in dir_map.values() or col.endswith(("_u","_v")): continue
        new_name = f"{pfx}_{col.lower().replace('sea_surface_','sst_')}"
        agg = 'sum' if 'precipitation' in col else 'mean'
        s_list.append(df_hr[col].resample('ME').agg(agg).rename(new_name))
    return pd.concat(s_list, axis=1) if s_list else pd.DataFrame()

def perform_correlation_analysis(df, arr_col, route):
    if df.empty or arr_col not in df.columns: return None, None
    return None, df.corr(method='spearman')

def visualize_findings(df, arr_col, route_viz_name, corrs_res, full_matrix):
    if df.empty: return
    out_dir = f"visualizations/{route_viz_name.replace(' ', '_')}"; os.makedirs(out_dir, exist_ok=True)
    if arr_col in df.columns:
        df[arr_col].plot(title=f'Arrivals - {route_viz_name}', figsize=(12,6)).get_figure().savefig(f"{out_dir}/arrivals_timeseries.png"); plt.close()
        if full_matrix is not None: sns.heatmap(full_matrix, annot=False, cmap='coolwarm').get_figure().savefig(f"{out_dir}/correlation_heatmap.png"); plt.close()
        sns.boxplot(x=df.index.month, y=df[arr_col]).get_figure().savefig(f"{out_dir}/arrivals_seasonality.png"); plt.close()


# --- Forecasting Functions ---
def load_and_prepare_forecasting_data(csv_path, target_column, test_size=24):
    try: df = pd.read_csv(csv_path, index_col='date', parse_dates=True)
    except: return (None,)*5
    if df.index.freq is None: df = df.asfreq('ME')
    df[target_column] = df[target_column].ffill().bfill()
    exog_cols = [col for col in df.columns if col != target_column]
    for col in exog_cols: df[col] = df[col].ffill().bfill().fillna(df[col].mean())
    train_df, test_df = df.iloc[:-test_size], df.iloc[-test_size:]
    return train_df[target_column], train_df[exog_cols] if exog_cols else None, \
           test_df[target_column], test_df[exog_cols] if exog_cols else None, df

def create_lagged_features(df_full, target_col_name, exog_cols_original, lag_orders, prefix=""):
    df_lagged = df_full.copy()
    for lag in lag_orders: df_lagged[f'{prefix}{target_col_name}_lag_{lag}'] = df_lagged[target_col_name].shift(lag)
    for col in exog_cols_original:
        if col in df_lagged.columns:
            for lag in lag_orders: df_lagged[f'{prefix}{col}_lag_{lag}'] = df_lagged[col].shift(lag)
    return df_lagged

def fit_sarima_baseline_gridsearch(target_train_series, m=12, exog_train=None):
    print(f"\n--- Fitting SARIMA via Grid Search (m={m}) ---")
    p_range, d_range, q_range = range(0,3), range(0,2), range(0,3)
    P_range, D_range, Q_range = range(0,2), range(0,2), range(0,2)
    s = m; best_aic = np.inf; best_order = None; best_seasonal_order = None; best_model = None
    pdq_comb = list(itertools.product(p_range,d_range,q_range))
    PDQ_comb = list(itertools.product(P_range,D_range,Q_range))
    print(f"Grid search: {len(pdq_comb)*len(PDQ_comb)} SARIMA combinations.")
    for order_p in pdq_comb:
        for seasonal_p in PDQ_comb:
            if order_p==(0,0,0) and seasonal_p==(0,0,0) and s==0: continue # Avoid trivial non-seasonal model
            curr_s_order = (seasonal_p[0],seasonal_p[1],seasonal_p[2],s)
            try:
                model = SARIMAX(target_train_series,exog=exog_train,order=order_p,seasonal_order=curr_s_order,
                                enforce_stationarity=False,enforce_invertibility=False,simple_differencing=False) # Changed from True for wider search
                res = model.fit(disp=False,maxiter=200) # Added maxiter
                if res.aic < best_aic: best_aic=res.aic; best_order=order_p; best_seasonal_order=curr_s_order; best_model=res
            except: continue
    if best_model is None: print("SARIMA grid search failed."); return None,None
    print(f"Best SARIMA: AIC={best_aic:.2f}, Order={best_order}, Seasonal={best_seasonal_order}")
    preds_train = best_model.get_prediction(exog=exog_train).predicted_mean
    resids_train = target_train_series - preds_train
    print(f"SARIMA residuals mean: {resids_train.mean():.4f}")
    return best_model, resids_train

def fit_rf_for_residuals(residuals_series, exog_features_df):
    if exog_features_df.empty or residuals_series.empty: return None
    print(f"RF training - Features: {exog_features_df.shape}, Residuals: {residuals_series.shape}")
    rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1, max_depth=10, min_samples_split=5, min_samples_leaf=3)
    try:
        rf.fit(exog_features_df, residuals_series)
        print("RF for residuals fitted.")
        importances = rf.feature_importances_
        feat_imp_df = pd.DataFrame({'feature': exog_features_df.columns, 'importance': importances}).sort_values(by='importance', ascending=False)
        print("\nTop 10 RF Feature Importances (for residuals):"); print(feat_imp_df.head(10))
        return rf
    except Exception as e: print(f"Error training RF for residuals: {e}"); return None

def generate_hybrid_forecasts(sarima_model, rf_residuals_model,
                              initial_target_train_series, # Full training series for SARIMA to know context
                              sarima_exog_test, # Original (non-lagged) exog for SARIMA for the test period
                              rf_features_test, # Lagged features for RF for the test period
                              target_test_series, # Actual values for comparison
                              max_forecast_horizon=3):
    """Generates hybrid forecasts over the test period."""
    print(f"\n--- Generating Hybrid Forecasts (Horizon: {max_forecast_horizon}) ---")

    all_predictions = {step: [] for step in range(1, max_forecast_horizon + 1)}
    actual_values_aligned = {step: [] for step in range(1, max_forecast_horizon + 1)}
    forecast_indices = {step: [] for step in range(1, max_forecast_horizon + 1)}

    # The SARIMA model is already fitted on canary_target_train.
    # We will make out-of-sample forecasts from the end of the training period.

    # One-time forecast from SARIMA for the entire test period + horizon
    # This is simpler than true rolling forecast for SARIMA for now
    n_test_periods = len(target_test_series)

    # Prepare exog for the full forecast horizon needed by SARIMA
    # SARIMA needs exog for n_test_periods + max_forecast_horizon - 1 steps
    # We only have sarima_exog_test for n_test_periods.
    # We'll append the last row of sarima_exog_test for the missing future exog values.

    num_sarima_fc_steps = n_test_periods + max_forecast_horizon - 1
    extended_sarima_exog_test = None

    if sarima_exog_test is not None:
        if len(sarima_exog_test) >= num_sarima_fc_steps:
            extended_sarima_exog_test = sarima_exog_test.iloc[:num_sarima_fc_steps]
        else:
            print(f"Extending SARIMA exog for forecast. Have {len(sarima_exog_test)}, need {num_sarima_fc_steps}")
            last_known_exog_vals = sarima_exog_test.iloc[[-1]] # Get last row as a DataFrame
            num_missing_exog_steps = num_sarima_fc_steps - len(sarima_exog_test)

            # Create future dates for the extended exog index
            future_exog_dates = pd.date_range(start=sarima_exog_test.index[-1] + pd.offsets.MonthEnd(1),
                                              periods=num_missing_exog_steps,
                                              freq='ME')

            extended_rows = pd.concat([last_known_exog_vals] * num_missing_exog_steps)
            extended_rows.index = future_exog_dates
            extended_sarima_exog_test = pd.concat([sarima_exog_test, extended_rows])
            print(f"Shape of extended_sarima_exog_test: {extended_sarima_exog_test.shape}")


    try:
        sarima_full_fcst_obj = sarima_model.get_forecast(steps=num_sarima_fc_steps, exog=extended_sarima_exog_test)
        sarima_full_forecasts = sarima_full_fcst_obj.predicted_mean
    except Exception as e:
        print(f"Error in SARIMA get_forecast for full test range: {e}")
        return None, None # Cannot proceed

    for i in range(n_test_periods): # Iterate for each possible start point in the test set
        current_forecast_origin_idx = target_test_series.index[i]

        # For RF, we need features corresponding to this forecast origin
        # rf_features_test is already aligned with target_test_series index
        current_rf_features = rf_features_test.loc[[current_forecast_origin_idx]]

        rf_residual_pred_step1 = 0.0 # Default if RF fails or no features
        if rf_residuals_model and not current_rf_features.isnull().all().all():
            try:
                # RF predicts the residual for the *next* step (1-step ahead for residual)
                rf_residual_pred_step1 = rf_residuals_model.predict(current_rf_features)[0]
            except Exception as e_rf:
                print(f"Error during RF residual prediction at {current_forecast_origin_idx}: {e_rf}")
                rf_residual_pred_step1 = np.nan # Or 0.0, depending on how to handle failure

        # Generate 1 to max_forecast_horizon forecasts from this origin
        for step_h in range(1, max_forecast_horizon + 1):
            actual_forecast_target_idx = i + step_h - 1 # Index in target_test_series

            if actual_forecast_target_idx < n_test_periods:
                sarima_fcst_for_step = sarima_full_forecasts.iloc[actual_forecast_target_idx]

                # Simplification: Use the 1-step RF residual prediction for all H steps from current origin
                # A more complex model would re-evaluate RF features for future steps if possible
                rf_resid_for_step = rf_residual_pred_step1 if step_h == 1 else rf_residual_pred_step1 # Or try to get more sophisticated

                hybrid_fcst = sarima_fcst_for_step + rf_resid_for_step

                actual_val = target_test_series.iloc[actual_forecast_target_idx]
                fcst_date = target_test_series.index[actual_forecast_target_idx]

                all_predictions[step_h].append(hybrid_fcst)
                actual_values_aligned[step_h].append(actual_val)
                forecast_indices[step_h].append(fcst_date)

    for step in range(1, max_forecast_horizon + 1):
        all_predictions[step] = pd.Series(all_predictions[step], index=forecast_indices[step])
        actual_values_aligned[step] = pd.Series(actual_values_aligned[step], index=forecast_indices[step])

    # Also return SARIMA-only forecasts for baseline comparison
    # We need to align sarima_full_forecasts with the structure of all_predictions
    sarima_only_predictions = {step: [] for step in range(1, max_forecast_horizon + 1)}
    for i in range(n_test_periods):
        for step_h in range(1, max_forecast_horizon + 1):
            actual_forecast_target_idx = i + step_h - 1
            if actual_forecast_target_idx < n_test_periods:
                 # sarima_full_forecasts is already indexed correctly from get_forecast
                sarima_val_for_step = sarima_full_forecasts.iloc[actual_forecast_target_idx]
                sarima_only_predictions[step_h].append(sarima_val_for_step)
                # We use the same indices as hybrid predictions for alignment

    for step in range(1, max_forecast_horizon + 1):
        if forecast_indices[step]: # Ensure there are indices to align with
             sarima_only_predictions[step] = pd.Series(sarima_only_predictions[step][:len(forecast_indices[step])], index=forecast_indices[step])


    return all_predictions, actual_values_aligned, sarima_only_predictions


# --- Main Execution Block ---
if __name__ == "__main__":
    run_correlation_analysis_part = True
    run_forecasting_part = True

    if run_correlation_analysis_part:
        print(f"--- Part 1: Correlation Analysis ---")
        if not (os.path.exists("canary_analysis_data.csv")):
             print("WARNING: canary_analysis_data.csv not found. Please run the full data extraction first or ensure file is present.")
             # To prevent error, we might exit or skip this part if files are critical and missing
             # For now, we'll let it try and fail if files are missing, or succeed if they exist.
        # Simplified correlation execution for brevity in this step
        df_canary_analysis = pd.read_csv("canary_analysis_data.csv", index_col='date', parse_dates=True) if os.path.exists("canary_analysis_data.csv") else pd.DataFrame()
        if not df_canary_analysis.empty:
            print("Running minimal correlation/visualization for existing canary_analysis_data.csv")
            can_corrs, can_matrix = perform_correlation_analysis(df_canary_analysis, "arrivals_canary", "Canary Islands Route")
            if can_corrs: visualize_findings(df_canary_analysis, "arrivals_canary", "Canary_Islands_Route", can_corrs, can_matrix)
        else:
            print("Skipping correlation part as canary_analysis_data.csv not found.")


    if run_forecasting_part:
        print("\n\n--- Part 2: Forecasting Model Development (Canary Islands) ---")
        canary_target_train, canary_exog_train_orig, canary_target_test, canary_exog_test_orig, df_canary_full = \
            load_and_prepare_forecasting_data("canary_analysis_data.csv", "arrivals_canary", test_size=24)

        if canary_target_train is not None and df_canary_full is not None:
            print("\nCanary Islands data loaded for forecasting.")
            original_env_cols_in_csv = [col for col in df_canary_full.columns if col != 'arrivals_canary']
            lag_orders = [1, 2, 3]
            df_canary_full_with_lags = create_lagged_features(df_canary_full, 'arrivals_canary', original_env_cols_in_csv, lag_orders)

            rf_feature_cols = [col for col in df_canary_full_with_lags.columns if col != 'arrivals_canary' and not col.startswith('arrivals_canary_lag_')]
            rf_feature_cols += [col for col in df_canary_full_with_lags.columns if col.startswith('arrivals_canary_lag_')]
            rf_feature_cols += [col for col in df_canary_full_with_lags.columns if col.startswith('canary_') and '_lag_' in col]
            rf_feature_cols = sorted(list(set(rf_feature_cols)))

            exog_rf_train_features = df_canary_full_with_lags.loc[canary_target_train.index, rf_feature_cols].copy()
            exog_rf_test_features = df_canary_full_with_lags.loc[canary_target_test.index, rf_feature_cols].copy()

            sarima_model_canary, sarima_residuals_train_canary = fit_sarima_baseline_gridsearch(canary_target_train, m=12, exog_train=canary_exog_train_orig)

            rf_model_residuals_canary = None
            if sarima_model_canary and sarima_residuals_train_canary is not None:
                print("SARIMA baseline model (grid search) fitted.")
                aligned_rf_features_train = exog_rf_train_features.loc[sarima_residuals_train_canary.index]
                df_rf_train_input = pd.concat([sarima_residuals_train_canary.rename("sarima_residuals"), aligned_rf_features_train], axis=1)
                df_rf_train_input.dropna(inplace=True)
                print(f"Shape of data for RF training (after NaN drop): {df_rf_train_input.shape}")
                if not df_rf_train_input.empty:
                    sarima_residuals_train_final = df_rf_train_input["sarima_residuals"]
                    exog_rf_train_final_features = df_rf_train_input.drop(columns=["sarima_residuals"])
                    rf_model_residuals_canary = fit_rf_for_residuals(sarima_residuals_train_final, exog_rf_train_final_features)
                else: print("Not enough data for RF training after NaN removal.")
            else: print("SARIMA model (grid search) fitting failed.")

            # Step 5 & 6: Hybrid Forecasting & Evaluation
            if sarima_model_canary and rf_model_residuals_canary and canary_target_test is not None:
                canary_hybrid_preds, canary_actuals_aligned, canary_sarima_only_preds = generate_hybrid_forecasts(
                    sarima_model_canary, rf_model_residuals_canary,
                    canary_target_train,
                    canary_exog_test_orig,
                    exog_rf_test_features,
                    canary_target_test,
                    max_forecast_horizon=3
                )

                if canary_hybrid_preds:
                    print("\n--- Hybrid & SARIMA-only Forecast Evaluation (Canary Islands) ---")
                    # Feature importances from RF were already printed in fit_rf_for_residuals

                    for step in range(1, 4):
                        if step in canary_hybrid_preds and not canary_hybrid_preds[step].empty:
                            preds_h = canary_hybrid_preds[step].dropna()
                            actuals_h = canary_actuals_aligned[step].loc[preds_h.index].dropna()

                            preds_s = canary_sarima_only_preds[step].reindex(preds_h.index).dropna() # Align and dropna
                            actuals_s = canary_actuals_aligned[step].loc[preds_s.index].dropna()


                            if not preds_h.empty and not actuals_h.empty and len(preds_h)==len(actuals_h):
                                mae_h = mean_absolute_error(actuals_h, preds_h); rmse_h = np.sqrt(mean_squared_error(actuals_h, preds_h))
                                print(f"Hybrid    Step {step} ahead: MAE={mae_h:.2f}, RMSE={rmse_h:.2f} ({len(preds_h)} samples)")

                                # Plotting (already done in generate_hybrid_forecasts for hybrid)
                                # Optional: Plot SARIMA-only vs Hybrid vs Actual
                                plt.figure(figsize=(14, 7))
                                actuals_h.plot(label='Actual Arrivals', legend=True)
                                preds_h.plot(label=f'Hybrid Forecast ({step}-step)', legend=True, linestyle='--')
                                if not preds_s.empty and len(preds_s) == len(actuals_s): # Check if SARIMA preds are valid
                                     preds_s.plot(label=f'SARIMA Forecast ({step}-step)', legend=True, linestyle=':')
                                plt.title(f'Canary Arrivals: Actual vs Forecasts ({step}-Step Ahead)')
                                plt.ylabel('Number of Arrivals')
                                out_fc_dir = "visualizations/Canary_Islands_Route/Forecasts_Comparison"
                                os.makedirs(out_fc_dir, exist_ok=True)
                                plt.savefig(f"{out_fc_dir}/comparison_forecast_step_{step}.png"); plt.close()
                                print(f"  Saved comparison plot: comparison_forecast_step_{step}.png")


                            if not preds_s.empty and not actuals_s.empty and len(preds_s)==len(actuals_s):
                                mae_s = mean_absolute_error(actuals_s, preds_s); rmse_s = np.sqrt(mean_squared_error(actuals_s, preds_s))
                                print(f"SARIMA    Step {step} ahead: MAE={mae_s:.2f}, RMSE={rmse_s:.2f} ({len(preds_s)} samples)")
                            else:
                                print(f"SARIMA    Step {step} ahead: Not enough valid SARIMA-only points for eval.")
                        else: print(f"Step {step} ahead: No hybrid predictions.")
            else: print("Skipping Hybrid Forecasting & Eval: models or test data missing.")
        else: print("\nFailed to load/prepare Canary Islands data for forecasting.")

        print("\n--- Forecasting Plan (through Evaluation) Attempted ---")

    print("\n--- Full Script Execution Finished ---")
