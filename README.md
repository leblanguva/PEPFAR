# US Southern Border Migration Forecasting Project

## 1. Project Goal
The primary goal of this project is to develop a forecasting model for migration encounters at the US Southern Border. The model aims to provide 1-month and 3-month ahead forecasts using a Random Forest Regressor, incorporating various potential drivers of migration.

## 2. Data Sources
The project utilizes several data sources, though some are currently implemented as placeholders or samples:

*   **Primary Migration Data:**
    *   U.S.-Mexico Border Patrol Migrant Encounters By Country (Oct 2019 - Jan 2025 target, actual up to ~June 2024 used): From Google Sheet `1QIVCWAZgYVuDx0aaD1ib4BhethPP5s5gymxreb5KVHk`
    *   Since 2014 U.S.-Mexico Border Patrol Migrant Encounters By Country (Oct 2013 - Dec 2021): From Google Sheet `1n0-Lb2ZewwBxXFSuNjYpgElZbyBnXARIB0cZF6VvNac`
*   **Event Data (Political Violence, Unrest):**
    *   GDELT Project (Global Database of Events, Language, and Tone): Sample data for `2023-01-01` from the GDELT 1.0 Event Database was used to extract counts of relevant events (protest, coercion, assault, fight, mass violence). Full integration across the time series is pending.
*   **Geographical Data (Placeholder):**
    *   Country distances to the US Southern Border: Placeholder data was generated. Actual data would involve calculating distances from country centroids to border entry points.
*   **US Economic Data (Placeholder):**
    *   Job vacancies in US hospitality and construction sectors: Placeholder data was generated. Actual data would come from sources like BLS JOLTS or FRED.
*   **Other Potential Data (Conceptual - Not yet integrated):**
    *   Climate conditions (drought, floods) and agricultural conditions (e.g., from FAO, FEWS NET, NOAA).
    *   Food insecurity information (e.g., from WFP, IPC).
    *   Economic conditions in origin countries (GDP, unemployment - e.g., from World Bank, IMF).
    *   US Immigration Policy changes.

## 3. Methodology

### 3.1. Data Preprocessing & Database Creation
1.  **Migration Data:** The two Google Sheets containing border encounter data were downloaded, cleaned (handling headers, standardizing country names, converting to long format, parsing dates), and merged into a single monthly time series dataset (`us_border_encounters_monthly.csv`). Future placeholder dates in one sheet were handled by truncating to the last known actual data month.
2.  **GDELT Event Data:** A sample GDELT 1.0 Event data file (`20230101.export.CSV`) was downloaded and processed. Relevant CAMEO root event codes (related to protest, coercion, violence) were counted per country per day. This daily sample was then aggregated to monthly and merged into the main dataset using FIPS country codes.
3.  **Placeholder Data:** Placeholder CSV files for country distances (including FIPS codes) and US economic indicators (monthly job openings) were generated.
4.  **Master Dataset Assembly:** The processed migration data was merged with the GDELT sample and placeholder datasets to create `master_dataset_with_features.csv`.

### 3.2. Feature Engineering
Various features were engineered to aid the forecasting model:
*   **Time-Based Features:** `Year`, `Month`, `Quarter`, `TimeIndex` (months since start).
*   **Lagged Encounters:** 1, 2, 3, 6, and 12-month lagged values of `Encounters`.
*   **Rolling Window Encounters:** 3, 6, and 12-month rolling mean and standard deviation of `Encounters`.
*   **Lagged GDELT Event Counts:** 1, 2, and 3-month lagged values of (sample) `GDELT_EventCount`.
*   **Lagged US Economic Variables:** 1, 2, and 3-month lagged values of (placeholder) US job openings data.
*   **Categorical Encoding:** `Nationality` was converted to `Nationality_Code`.

### 3.3. Modeling
*   **Model:** `RandomForestRegressor` from `scikit-learn`.
*   **Forecast Horizons:**
    *   1-Month Ahead Forecast.
    *   3-Months Ahead Forecast (using a direct forecasting approach where the target is `Encounters` shifted by -3 months).
*   **Train-Test Split:** Data was split chronologically. After NaN removal, an adaptive split was used, generally aiming for an 80/20 train/test split on the available, cleaned data.
*   **Evaluation Metrics:** Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), and R-squared (R²).

### 3.4. Forecasting Exercise
*   The trained models were used to make predictions on the test set.
*   Samples of these past predictions (1-month and 3-month ahead) were displayed.
*   A conceptual demonstration of generating new forecasts for future periods (beyond the test set) using the latest available features was included.

## 4. File Structure
*   `unified_processing_script.py`: Main script for data downloading, preprocessing, feature engineering. Outputs `master_dataset_with_features.csv`.
*   `estimate_rf_models.py`: Script for training models, evaluation, and saving models (`.joblib`) and test predictions (`.csv`).
*   `perform_forecasting.py`: Script to load models and demonstrate forecasting.
*   `us_border_encounters_monthly.csv`: (Intermediate) Combined and cleaned monthly migration data.
*   `master_dataset_with_features.csv`: Final dataset used for model training.
*   `rf_model_t1.joblib`: Saved 1-month ahead Random Forest model.
*   `rf_model_t3.joblib`: Saved 3-month ahead Random Forest model.
*   `test_data_with_predictions_t1.csv`: Test data with 1-month ahead predictions.
*   `test_data_with_predictions_t3.csv`: Test data with 3-month ahead predictions.
*   `.gitignore`: Specifies files to be ignored by git (e.g., large data files, Python cache).
*   `README.md`: This documentation file.

## 5. Current Status & Limitations
*   **Data Scope:** The current models are trained on a dataset where GDELT data is only a single-day sample, and US economic indicators & country distances are placeholders. This significantly limits the current predictive power related to these external factors.
*   **NaN Handling:** Rows with NaN values (resulting from lags, rolling windows, and incomplete placeholder data) were dropped. This led to a substantially smaller dataset for model training than the full migration time series.
*   **Model Performance:** While the R-squared for the 1-month model was high (0.81) and respectable for the 3-month model (0.69), these results should be interpreted with caution due to the data limitations mentioned above. Performance is likely driven heavily by autoregressive features (lagged encounters).
*   **Hyperparameter Tuning:** No systematic hyperparameter tuning was performed for the Random Forest models. Default/illustrative parameters were used.
*   **Time Series Validation:** A simple time-based split was used. More rigorous time-series cross-validation techniques (e.g., `TimeSeriesSplit` with multiple splits) are recommended for robust evaluation.

## 6. Future Work & Improvements
*   **Full Data Integration:**
    *   Implement a pipeline to download and process GDELT event data for the entire relevant historical period.
    *   Integrate actual data for climate/agricultural conditions, food insecurity, US economic conditions, and other identified drivers.
*   **Data Harmonization:** Ensure robust mapping and alignment of country names and codes across all datasets.
*   **Advanced Feature Engineering:**
    *   Develop strategies for handling future values of exogenous variables for true out-of-sample forecasting.
    *   Explore interaction terms between different feature sets.
*   **Modeling Enhancements:**
    *   Conduct comprehensive hyperparameter tuning for Random Forest models.
    *   Implement robust time-series cross-validation.
    *   Explore other modeling techniques (e.g., SARIMA, Prophet, Gradient Boosting Machines, LSTMs or other neural networks).
*   **Operationalization:** Develop a system for regular data updates, model re-training, and forecast generation.
*   **Error Analysis:** Perform a deeper analysis of forecast errors by country, time period, etc., to identify areas for model improvement.
