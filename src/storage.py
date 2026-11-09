import logging

logger = logging.getLogger(__name__)


class DatasetStorage:
    def __init__(self):
        self._store = {}
        self._counter = 0

    def save(self, df, filename):
        self._counter += 1
        dataset_id = self._counter

        self._store[dataset_id] = {
            "filename": filename,
            "data": df.copy()
        }

        logger.debug(f"Stored dataset: id={dataset_id}, rows={len(df)}")
        
        return dataset_id

    def get(self, dataset_id):
        item = self._store.get(dataset_id)
        if item is None:
            logger.debug(f"Dataset not found: id={dataset_id}")
            return None
        logger.debug(f"Retrieved dataset: id={dataset_id}")

        return item["data"].copy()

    def get_metadata(self, dataset_id):
        item = self._store.get(dataset_id)
        if item is None:
            logger.debug(f"Dataset not dounf: id={dataset_id}")
            return None

        df = item["data"]
        metadata = {
            "id": dataset_id,
            "filename": item["filename"],
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": list(df.columns)
        }

        logger.debug(f"Retrived metadata for dataset: if= {dataset_id}")
        return metadata

    def update(self, dataset_id, df):
        if dataset_id not in self._store:
            logger.debug(f"Cannot update missing dataset: id={dataset_id}")
            return False

        self._store.get(dataset_id)["data"] = df.copy()

        logger.debug(f"Updated dataset: id={dataset_id}")
        return True

    def clear(self):
        """Clear all data and reset the ID counter."""
        self._store.clear()
        self._counter = 0
        logger.debug("Cleared all stored datasets")
