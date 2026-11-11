# Movie Data Processing API

## Overview

The Movie Data Processing API is a FastAPI application that allows users to upload, store, retrieve, search, and process movie datasets. The `main.py` module defines the API endpoints and coordinates interactions between the application's components. The `src/storage.py` module uses SQLite to store movie records, replacing existing records whenever a new CSV file is uploaded. The `data_pipeline` module provides data validation and processing functions, including duplicate removal, missing-value handling, and outlier detection. The `src/cache.py` module uses an in-memory Redis-compatible cache through `fakeredis` to temporarily store movie retrieval responses and improve performance. When a dataset is uploaded or processed, the cache is invalidated to ensure that subsequent requests return the most up-to-date data. Together, these modules provide a structured workflow for managing and processing movie data through REST API endpoints.

## Running the Application

Start the API from the project root:

```bash
uvicorn main:app --reload
```

The API will be available at:

`http://127.0.0.1:8000`

Interactive API documentation is available at:

`http://127.0.0.1:8000/docs`

## Running Tests

Run the test suite from the project root:

```bash
pytest -v
```

## Sample Processing Request

Send a POST request to `/movies/process` with the following JSON configuration:

```json
{
  "validation": {
    "required_columns": ["title", "release_year", "rating", "genre"],
    "numeric_columns": ["release_year", "rating"]
  },
  "processing": {
    "remove_duplicates": true,
    "missing": {
      "enabled": true,
      "axis": "rows"
    },
    "outliers": {
      "enabled": true,
      "columns": ["rating"],
      "method": "iqr",
      "threshold": 1.5
    }
  }
}
```

The request validates the required movie columns, removes duplicate records, drops rows containing missing values, and removes rating outliers using the interquartile range (IQR) method.

**Expected Result:** For the included 20-row sample dataset, validation removes 0 rows and processing removes 4 rows: 2 duplicate records and 2 rating outliers. The final dataset contains 16 movie records.

The response includes the validation and cleaning results:

```json
{
  "validation_rows_removed": 0,
  "cleaning_report": {
    "rows_before": 20,
    "rows_after": 16,
    "rows_removed": 4,
    "columns_before": 4,
    "columns_after": 4,
    "columns_removed": 0
  }
}
```