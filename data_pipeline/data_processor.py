# data_processor.py
import logging
import pandas as pd

logger = logging.getLogger(__name__)

def remove_duplicates(df):
    """Remove duplicate rows."""
    before = len(df)

    result = df.drop_duplicates()

    logger.debug(f"Removed {before - len(result)} rows. From {before} to {len(result)} rows.")

    return result


def handle_missing(df, axis="rows"):
    """Drop rows or columns containing missing values."""
    result = df

    if axis == "rows":
        before = len(result)
        result = result.dropna()
        logger.debug(f"Removed {before - len(result)} rows. From {before} to {len(result)} rows.")
        return result
    elif axis == "columns":
        before = result.shape[1]
        result = result.dropna(axis=1)
        logger.debug(f"Removed {before - result.shape[1]} columns. From {before} to {result.shape[1]} columns.")
        return result
    else:
        logger.error(f"Unsupported axis type: {axis}")
        raise ValueError(f"Unsupported axis type: {axis}")


def remove_outliers(df, columns, method, threshold):
    """Remove outliers from the specified numeric columns."""
    result = df

    if method not in ["iqr", "zscore"]:
        logger.error(f"Unsupported outlier method: {method}")
        raise ValueError(f"Unsupported outlier method: {method}")

    for column in columns:
        if column not in result.columns:
            logger.warning(f"Column not found: {column}")
            continue

        if not pd.api.types.is_numeric_dtype(result[column]):
            logger.warning(f"Column is not numeric: {column}")
            continue

        before = len(result)

        if method == "iqr":
            q1 = result[column].quantile(0.25)
            q3 = result[column].quantile(0.75)
            iqr = q3 - q1

            lower = q1 - threshold * iqr
            upper = q3 + threshold * iqr

            result = result[(result[column] >= lower) & (result[column] <= upper)]

        elif method == "zscore":
            mean = result[column].mean()
            std = result[column].std()

            if std == 0:
                continue

            z_scores = (result[column] - mean) / std
            result = result[z_scores.abs() <= threshold]

        rows_removed = before - len(result)

        logger.debug(f"{column}: Method={method}, Threshold={threshold}, Removed={rows_removed}")

    return result


def process_data(df, config):
    """Apply the processing steps enabled in the configuration."""
    processing = config["processing"]
    result = df

    if processing["remove_duplicates"]:
        result = remove_duplicates(result)

    if processing["missing"]["enabled"]:
        result = handle_missing(
            result,
            processing["missing"]["axis"]
        )

    if processing["outliers"]["enabled"]:
        result = remove_outliers(
            result,
            processing["outliers"]["columns"],
            processing["outliers"]["method"],
            processing["outliers"]["threshold"]
        )

    return result


def create_cleaning_report(df_before, df_after):
    """Return a dictionary summarizing the cleaning results."""
    rows_before = len(df_before)
    rows_after = len(df_after)

    columns_before = df_before.shape[1]
    columns_after = df_after.shape[1]

    report = {
        "rows_before": rows_before,
        "rows_after": rows_after,
        "rows_removed": rows_before - rows_after,
        "columns_before": columns_before,
        "columns_after": columns_after,
        "columns_removed": columns_before - columns_after
    }

    return report
