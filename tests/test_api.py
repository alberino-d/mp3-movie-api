import pytest

from src import MovieStorage
import main


def test_upload_csv(client, sample_csv_bytes):
    response = client.post(
        "/upload",
        files={
            "file": (
                "sample_movies.csv",
                sample_csv_bytes,
                "text/csv"
            )
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["rows"] == 20
    assert data["columns"] == 4
    assert data["column_names"] == main.MOVIE_COLUMNS


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
                b"title,rating\nMovie A,8.0\n",
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


def test_retrieve_with_limit(client, uploaded_movies):
    response = client.get("/movies?limit=2")

    assert response.status_code == 200

    data = response.json()

    assert len(data["data"]) == 2
    assert data["total_rows"] == 20


def test_invalid_limit_zero(client, uploaded_movies):
    response = client.get("/movies?limit=0")

    assert response.status_code == 422


def test_process_empty_movies(client, processing_body):
    response = client.post(
        "/movies/process",
        json=processing_body
    )

    assert response.status_code == 400


def test_missing_required_column(client, uploaded_movies):
    original_response = client.get("/movies")
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

    response = client.post("/movies/process", json=config)

    assert response.status_code == 400

    after_response = client.get("/movies")

    assert after_response.status_code == 200
    assert after_response.json()["data"] == original_data


def test_unsupported_outlier_method(client, uploaded_movies):
    original_response = client.get("/movies")
    original_data = original_response.json()["data"]

    config = {
        "validation": {
            "required_columns": ["title", "release_year", "rating", "genre"],
            "numeric_columns": ["release_year", "rating"]
        },
        "processing": {
            "remove_duplicates": True,
            "missing": {
                "enabled": True,
                "axis": "rows"
            },
            "outliers": {
                "enabled": True,
                "columns": ["rating"],
                "method": "unsupported_method",
                "threshold": 1.5
            }
        }
    }

    response = client.post("/movies/process", json=config)

    assert response.status_code == 400

    after_response = client.get("/movies")

    assert after_response.status_code == 200
    assert after_response.json()["data"] == original_data


def test_malformed_request_body(client, uploaded_movies):
    response = client.post(
        "/movies/process",
        json={"validation": "not an object"}
    )

    assert response.status_code == 422


def test_request_ids(client, uploaded_movies):
    # 200 response
    success = client.get("/movies")

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

    # 422 response
    invalid_limit = client.get("/movies?limit=0")

    responses = [success, bad_upload, invalid_limit]

    request_ids = []

    for response in responses:
        request_id = response.headers.get("X-Request-ID")

        assert request_id is not None
        assert len(request_id) == 8
        assert request_id.strip() != ""

        request_ids.append(request_id)

    # Each request should have a different ID.
    assert len(set(request_ids)) == len(request_ids)









def test_movies_persist(client, test_storage, uploaded_movies):
    reopened = MovieStorage(test_storage.db_path)

    movies = reopened.select_columns(main.MOVIE_COLUMNS, 100)
    total_movies = reopened.count_movies()
    assert total_movies == 20
    assert len(movies) == 20
    assert list(movies[0].keys()) == ["id", *main.MOVIE_COLUMNS]

    expected_titles = [
        "Movie A", "Movie B", "Movie B", "Movie C", "Movie D",
        "Movie D", "Movie E", "Movie F", "Movie G", "Movie H",
        "Movie I", "Movie J", "Movie K", "Movie L", "Movie M",
        "Movie N", "Movie O", "Movie P", "Movie Q", "Movie R"
    ]
    assert [movie["title"] for movie in movies] == expected_titles

    database_ids = [
        row["id"] for row in reopened.select_columns(["title"], 100)
    ]

    response = client.get("/movies", params={"limit": 100})
    assert response.status_code == 200

    api_ids = [movie["id"] for movie in response.json()["data"]]
    assert database_ids == list(range(1, 21))
    assert api_ids == database_ids


def test_cache_and_processing(client, uploaded_movies, processing_body):
    first = client.get("/movies", params={"limit": 100})
    second = client.get("/movies", params={"limit": 1})
    assert first.status_code == 200
    assert second.status_code == 200
    assert main.cache.get(100) == first.json()
    assert main.cache.get(1) == second.json()


    third = client.get("/movies", params={"limit": 100})
    assert third.status_code == 200
    assert third.json() == first.json()


    process_response = client.post("/movies/process", json=processing_body)
    assert process_response.status_code == 200

    process_data = process_response.json()
    assert process_data["validation_rows_removed"] == 0

    cleaning_report = process_data["cleaning_report"]
    assert cleaning_report["rows_before"] == 20
    assert cleaning_report["rows_after"] == 16
    assert cleaning_report["rows_removed"] == 4

    assert main.cache.get(100) is None
    assert main.cache.get(1) is None


    fourth = client.get("/movies", params={"limit": 100})
    assert fourth.status_code == 200
    result = fourth.json()
    assert result["total_rows"] == 16

    expected_titles = [f"Movie {chr(i)}" for i in range(65, 81)]
    assert [movie["title"] for movie in result["data"]] == expected_titles

    ids = [movie["id"] for movie in result["data"]]
    assert ids == list(range(1, 17))

    assert main.cache.get(100) == result


def test_cache_hit_skips_database(client, uploaded_movies, monkeypatch):
    first = client.get("/movies", params={"limit": 100})
    assert first.status_code == 200
    original_data = first.json()


    def fail_if_called(*args, **kwargs):
        pytest.fail("Database query should not execute on a cache hit")

    monkeypatch.setattr(main.storage, "select_columns", fail_if_called)
    monkeypatch.setattr(main.storage, "count_movies", fail_if_called)


    second = client.get("/movies", params={"limit": 100})
    assert second.status_code == 200
    assert second.json() == original_data


def test_invalid_upload_preserves_stored_data(client, uploaded_movies, sample_csv_bytes):
    original = client.get("/movies", params={"limit": 100})
    assert original.status_code == 200

    invalid_columns = b"name,year,score\nMovie A,2020,8.0\n"

    response = client.post(
        "/upload",
        files={"file": ("invalid.csv", invalid_columns, "text/csv")}
    )
    assert response.status_code == 400

    empty_rows = b"title,release_year,rating,genre\n"

    response = client.post(
        "/upload",
        files={"file": ("empty.csv", empty_rows, "text/csv")}
    )
    assert response.status_code == 400

    current = client.get("/movies", params={"limit": 100})
    assert current.status_code == 200
    assert current.json() == original.json()


def test_missing_values_saved_and_removed(client, sample_csv_bytes):
    csv_data = (
        b"title,release_year,rating,genre\n"
        b"Movie A,2020,8.0,Drama\n"
        b"Movie B,2021,,Comedy\n"
        b"Movie C,2022,9.0,Action\n"
    )

    response = client.post(
        "/upload",
        files={"file": ("missing.csv", csv_data, "text/csv")}
    )
    assert response.status_code == 200

    movies = client.get("/movies", params={"limit": 100})
    assert movies.status_code == 200
    assert movies.json()["total_rows"] == 3
    assert movies.json()["data"][1]["rating"] is None

    config = {
        "validation": {
            "required_columns": [],
            "numeric_columns": []
        },
        "processing": {
            "remove_duplicates": False,
            "missing": {"enabled": True, "axis": "rows"},
            "outliers": {
                "enabled": False,
                "columns": ["rating"],
                "method": "iqr",
                "threshold": 1.5
            }
        }
    }

    process_response = client.post("/movies/process", json=config)
    assert process_response.status_code == 200

    result = client.get("/movies", params={"limit": 100})
    assert result.status_code == 200
    assert result.json()["total_rows"] == 2
    assert [movie["title"] for movie in result.json()["data"]] == [
        "Movie A", "Movie C"
    ]


def test_upload_replaces_movies_and_invalidates_cache(client, uploaded_movies):
    first = client.get("/movies", params={"limit": 100})
    assert first.status_code == 200
    assert first.json()["total_rows"] == 20
    assert main.cache.get(100) == first.json()

    replacement_csv = (
        b"title,release_year,rating,genre\n"
        b"Replacement A,2025,9.0,Drama\n"
        b"Replacement B,2026,8.5,Comedy\n"
    )

    response = client.post(
        "/upload",
        files={"file": ("replacement.csv", replacement_csv, "text/csv")}
    )
    assert response.status_code == 200

    assert main.cache.get(100) is None

    second = client.get("/movies", params={"limit": 100})
    assert second.status_code == 200
    assert second.json()["total_rows"] == 2

    assert [movie["title"] for movie in second.json()["data"]] == [
        "Replacement A", "Replacement B"
    ]


def test_search_with_no_matches(client, uploaded_movies):
    response = client.get(
        "/movies/search",
        params={"columns": "title", "min_rating": 10}
    )

    assert response.status_code == 200
    assert response.json() == []


def test_search_unsupported_column(client, uploaded_movies):
    response = client.get(
        "/movies/search",
        params={"columns": "unknown"}
    )

    assert response.status_code == 400


def test_storage_invalid_columns(test_storage):
    with pytest.raises(ValueError):
        test_storage.select_columns([], 100)

    with pytest.raises(ValueError):
        test_storage.select_columns(["unknown"], 100)

    with pytest.raises(ValueError):
        test_storage.query_movies([], 0, 100)

    with pytest.raises(ValueError):
        test_storage.query_movies(["unknown"], 0, 100)


def test_failed_processing_preserves_database_and_cache(
    client, uploaded_movies, processing_body
):
    original = client.get("/movies", params={"limit": 100})
    assert original.status_code == 200

    original_data = original.json()
    assert main.cache.get(100) == original_data

    invalid_config = processing_body.copy()
    invalid_config["processing"] = processing_body["processing"].copy()
    invalid_config["processing"]["outliers"] = {
        "enabled": True,
        "columns": ["rating"],
        "method": "unsupported",
        "threshold": 1.5
    }

    response = client.post("/movies/process", json=invalid_config)
    assert response.status_code == 400

    assert main.cache.get(100) == original_data

    current = client.get("/movies", params={"limit": 100})
    assert current.status_code == 200
    assert current.json() == original_data


def test_empty_processed_collection(client):
    csv_data = (
        b"title,release_year,rating,genre\n"
        b"Movie A,2020,8.0,\n"
        b"Movie B,2021,7.5,\n"
    )

    response = client.post(
        "/upload",
        files={"file": ("missing_genres.csv", csv_data, "text/csv")}
    )
    assert response.status_code == 200

    config = {
        "validation": {
            "required_columns": [],
            "numeric_columns": []
        },
        "processing": {
            "remove_duplicates": False,
            "missing": {"enabled": True, "axis": "rows"},
            "outliers": {
                "enabled": False,
                "columns": ["rating"],
                "method": "iqr",
                "threshold": 1.5
            }
        }
    }

    process_response = client.post("/movies/process", json=config)
    assert process_response.status_code == 200

    result = client.get("/movies", params={"limit": 100})
    assert result.status_code == 200
    assert result.json()["data"] == []
    assert result.json()["total_rows"] == 0
