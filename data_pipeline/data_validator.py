# src/data_validator.py
import logging
import pandas as pd


logger = logging.getLogger(__name__)


def validate_dataframe(df, required_columns, numeric_columns):
    """Validate the DataFrame and return valid data.

    required_columns: a list of column names that must exist.
    numeric_columns: a list of column names whose values should be numeric.
    """
    before = df.copy()
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        logger.error(f"Missing Columns: {",".join(missing_columns)}")
        raise ValueError(f"{len(missing_columns)} columns missing")
    logger.info("All required columns exist")
    
    for col in numeric_columns:
        invalid_rows = []
        for i, value in df[col].items():
            if pd.notna(value):
                try:
                    float(value)
                except ValueError:
                    logger.warning(f"Invalid numeric value in {col}. Index: {i}")
                    invalid_rows += [i]
        df = df.drop(invalid_rows)
        #convert to a numeric data type
        df[col] = pd.to_numeric(df[col])

    logger.debug(f"Validation: {len(before)} to {len(df)} rows.")
    return df
