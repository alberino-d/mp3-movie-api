def test_upload_csv(client, sample_csv_bytes):
    response = client.post(
        "/upload",
        files={
            "file": (
                "sample_data.csv",
                sample_csv_bytes,
                "text/csv"
            )
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["rows"] == 6
    assert data["columns"] == 2
    assert isinstance(data["id"], int)
    assert data["id"] > 0


def test_process_and_retrieve(
    client, uploaded_dataset_id, processing_body
):
    # Process the uploaded dataset
    response = client.post(
        f"/datasets/{uploaded_dataset_id}/process",
        json=processing_body
    )

    assert response.status_code == 200

    report = response.json()

    assert report["validation_rows_removed"] == 1
    assert report["cleaning_report"]["rows_removed"] == 2

    # Retrieve the processed dataset
    response = client.get(
        f"/datasets/{uploaded_dataset_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_rows"] == 3

    records = data["data"]

    assert len(records) == 3

    expected_records = [
        {"student_id": 1, "score": 80},
        {"student_id": 2, "score": 90},
        {"student_id": 5, "score": 85}
    ]

    assert records == expected_records


def test_retrieve_missing_dataset(client):
    response = client.get("/datasets/999999")
    assert response.status_code == 404


def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unsupported_file_extension(client):
    response = client.post(
        "/upload",
        files={
            "file": (
                "sample_data.txt",
                b"student_id,score\n1,80\n",
                "text/plain"
            )
        }
    )

    assert response.status_code == 400


def test_empty_csv_upload(client):
    response = client.post(
        "/upload",
        files={
            "file": (
                "empty.csv",
                b"",
                "text/csv"
            )
        }
    )

    assert response.status_code == 400


def test_retrieve_with_limit(client, uploaded_dataset_id):
    response = client.get(
        f"/datasets/{uploaded_dataset_id}?limit=2"
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["data"]) == 2
    assert data["total_rows"] == 6


def test_invalid_limit_zero(client, uploaded_dataset_id):
    response = client.get(
        f"/datasets/{uploaded_dataset_id}?limit=0"
    )

    assert response.status_code == 422


def test_process_missing_dataset(client, processing_body):
    response = client.post(
        "/datasets/999999/process",
        json=processing_body
    )

    assert response.status_code == 404


def test_missing_required_column(client, uploaded_dataset_id):
    # Save the original dataset so we can verify it remains unchanged.
    original_response = client.get(
        f"/datasets/{uploaded_dataset_id}"
    )
    original_data = original_response.json()["data"]

    config = {
        "validation": {
            "required_columns": ["nonexistent_column"],
            "numeric_columns": []
        },
        "processing": {
            "remove_duplicates": True,
            "missing": {
                "enabled": True,
                "axis": "rows"
            },
            "outliers": {
                "enabled": False,
                "columns": [],
                "method": "iqr",
                "threshold": 1.5
            }
        }
    }

    response = client.post(
        f"/datasets/{uploaded_dataset_id}/process",
        json=config
    )

    assert response.status_code == 400

    # Verify that the stored dataset has not changed.
    after_response = client.get(
        f"/datasets/{uploaded_dataset_id}"
    )

    assert after_response.status_code == 200
    assert after_response.json()["data"] == original_data


def test_unsupported_outlier_method(client, uploaded_dataset_id):
    original_response = client.get(
        f"/datasets/{uploaded_dataset_id}"
    )
    original_data = original_response.json()["data"]

    config = {
        "validation": {
            "required_columns": ["student_id", "score"],
            "numeric_columns": ["score"]
        },
        "processing": {
            "remove_duplicates": True,
            "missing": {
                "enabled": True,
                "axis": "rows"
            },
            "outliers": {
                "enabled": True,
                "columns": ["score"],
                "method": "unsupported_method",
                "threshold": 1.5
            }
        }
    }

    response = client.post(
        f"/datasets/{uploaded_dataset_id}/process",
        json=config
    )

    assert response.status_code == 400

    # Verify that the stored dataset has not changed.
    after_response = client.get(
        f"/datasets/{uploaded_dataset_id}"
    )

    assert after_response.status_code == 200
    assert after_response.json()["data"] == original_data


def test_malformed_request_body(client, uploaded_dataset_id):
    response = client.post(
        f"/datasets/{uploaded_dataset_id}/process",
        json={"validation": "not an object"}
    )

    assert response.status_code == 422


def test_request_ids(client, uploaded_dataset_id):
    # 200 response
    success = client.get(
        f"/datasets/{uploaded_dataset_id}"
    )

    # 400 response
    bad_upload = client.post(
        "/upload",
        files={
            "file": (
                "bad.txt",
                b"some content",
                "text/plain"
            )
        }
    )

    # 404 response
    missing = client.get("/datasets/999999")

    # 422 response
    invalid_limit = client.get(
        f"/datasets/{uploaded_dataset_id}?limit=0"
    )

    responses = [success, bad_upload, missing, invalid_limit]

    request_ids = []

    for response in responses:
        request_id = response.headers.get("X-Request-ID")

        assert request_id is not None
        assert len(request_id) == 8
        assert request_id.strip() != ""

        request_ids.append(request_id)

    # Each request should have a different ID.
    assert len(set(request_ids)) == len(request_ids)
