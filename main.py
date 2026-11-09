import io
import json
import logging
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from src import (DatasetInfo,
                MovieStorage,
                MovieUploadInfo,
                MovieDataResponse,
                MovieProcessingReport,
                HealthResponse,
                setup_logging,
                ProcessConfig,
                ProcessingReport,
                log_requests,
                MOVIE_COLUMNS)
from data_pipeline import create_cleaning_report, process_data, validate_dataframe

setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Processing API", version="1.0.0")
app.middleware("http")(log_requests)
storage = MovieStorage()

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return {"status": "ok", "version": "1.0.0"}

@app.post("/upload", response_model=MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    if Path(file.filename or "").suffix.lower() != ".csv":
        logger.warning(f"Rejected upload: unsupported file type {file.filename}")
        raise HTTPException(status_code=400, detail="Invalid file type. File must be CSV.")
    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
    except (pd.errors.EmptyDataError,pd.errors.ParserError,UnicodeDecodeError) as error:
        logger.warning(f"Cannot parse CSV {file.filename}: {error}")
        raise HTTPException(status_code=400, detail="Cannot parse the uploaded CSV")

    if set(df.columns) != set(MOVIE_COLUMNS):
        raise HTTPException(status_code=400, detail=f"A CSV must contain these columns: {MOVIE_COLUMNS}")
    if df.empty:
        raise HTTPException(status_code=400, detail="A CSV must contain at least one movie")
    df = df[MOVIE_COLUMNS]

    storage.save(df)

    logger.info(f"Uploaded {file.filename}: {len(df)} movies saved")

    return MovieUploadInfo(
        filename=file.filename,
        rows=len(df),
        columns=len(df.columns),
        column_names=list(df.columns)
    )

@app.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: int, limit: int = Query(default=100, ge=1)):
    df = storage.get(dataset_id)

    if df is None:
        logger.warning(f"Dataset not found: id={dataset_id}")
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    records = json.loads(df.head(limit).to_json(orient="records"))

    logger.info(f"Retrieved dataset: id={dataset_id}, rows={len(records)}")

    return {
        "id": dataset_id,
        "data": records,
        "total_rows": len(df)
    }

@app.post(
    "/datasets/{dataset_id}/process",
    response_model=ProcessingReport
)
def process_dataset(dataset_id: int, config: ProcessConfig):
    """Validate and process a stored dataset using MP1 functions."""
    logger.info(f"Processing dataset: id={dataset_id}")

    # 1. Retrieve a copy of the stored dataset
    df = storage.get(dataset_id)

    if df is None:
        raise HTTPException(status_code=404, detail=f"Dataset not found: id={dataset_id}")

    # 2. Convert the configuration model to a dictionary
    config_dict = config.model_dump()

    validation_config = config_dict["validation"]
    processing_config = config_dict["processing"]

    try:
        # 3. Confirm configured numeric columns exist
        missing_columns = [column for column in validation_config["numeric_columns"] if column not in df.columns]
        if missing_columns:
            raise HTTPException(status_code=400, detail=f"Numeric columns not found: {missing_columns}")

        # 4. Validate the DataFrame
        validated_df = validate_dataframe(
            df,
            validation_config["required_columns"],
            validation_config["numeric_columns"]
        )

        # 5. Record validation rows removed and copy the result
        validation_rows_removed = len(df) - len(validated_df)
        validated_copy = validated_df.copy()
        logger.info(f"Dataset validation complete: id={dataset_id}, rows_removed={validation_rows_removed}")

        # 6. Process the validated DataFrame
        processed_df = process_data(validated_df, config_dict)

        # 7. Compare before and after processing
        cleaning_report = create_cleaning_report(validated_copy, processed_df)
        logger.info(f"Dataset processing complete: id={dataset_id}, rows_removed={cleaning_report["rows_removed"]}, columns_removed={cleaning_report["columns_removed"]}")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    # 8. Update the existing dataset only after successful processing
    storage.update(dataset_id, processed_df)

    # 9. Return the response
    return {
        "id": dataset_id,
        "validation_rows_removed": validation_rows_removed,
        "cleaning_report": cleaning_report
    }
