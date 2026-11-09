import logging
import sqlite3

import pandas as pd

from .database import get_connection, initialize_database

logger = logging.getLogger(__name__)
MOVIE_COLUMNS = ["title", "release_year", "rating", "genre"]


class MovieStorage:
    def __init__(self, db_path="data/movies.db"):
        self.db_path = db_path
        initialize_database(self.db_path)

    def save(self, df):
        """Replace all movie rows in one transaction."""
        connection = get_connection(self.db_path)
        try:
            rows = df[MOVIE_COLUMNS].astype(object).where(
                pd.notna(df[MOVIE_COLUMNS]), None
                ).values.tolist()

            sql_statement = "DELETE FROM movies"
            connection.execute(sql_statement)

            sql_statement = "INSERT INTO movies (title, release_year, rating, genre) VALUES (?, ?, ?, ?)"
            connection.executemany(sql_statement, rows)

            connection.commit()
            logger.debug(f"Saved {len(rows)} movies")
        except sqlite3.Error:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get(self):
        """Return the four movie columns as a DataFrame, ordered by id."""
        connection = get_connection(self.db_path)
        try:
            sql_statement = """
            SELECT title, release_year, rating, genre
            FROM movies
            ORDER BY id"""
            rows = connection.execute(sql_statement).fetchall()
            return pd.DataFrame(rows, columns=MOVIE_COLUMNS)
        finally:
            connection.close()

    def select_columns(self, columns, limit=5):
        """Return id plus the requested movie columns, ordered by id."""
        if not columns:
            logger.error("Select at least one column")
            raise ValueError("Select at least one column")

        for column in columns:
            if column not in MOVIE_COLUMNS:
                logger.error(f"Unsupported column: {column}")
                raise ValueError(f"Unsupported column: {column}")

        selected_columns = ", ".join(["id"] + columns)
        connection = get_connection(self.db_path)
        try:
            sql_statement = f"""
            SELECT {selected_columns}
            FROM movies
            ORDER BY id
            LIMIT ?"""
            rows = connection.execute(sql_statement, (limit,)).fetchall()
            movies = [dict(row) for row in rows]

            logger.debug(f"Selected {len(movies)} movies")
            return movies
        finally:
            connection.close()

    def count_movies(self):
        """Return the number of stored movies using SQL COUNT(*)."""
        connection = get_connection(self.db_path)
        try:
            sql_statement = "SELECT COUNT (*) AS total FROM movies"
            row = connection.execute(sql_statement).fetchone()
            return row["total"]
        finally:
            connection.close()

    def query_movies(self, columns, min_rating, limit):
        """Return selected fields from matching movies using SQL."""
        if not columns:
            logger.error("Select at least one column")
            raise ValueError("Select at least one column")

        for column in columns:
            if column not in MOVIE_COLUMNS:
                logger.error(f"Unsupported column: {column}")
                raise ValueError(f"Unsupported column: {column}")

        selected_columns = ", ".join(["id"] + columns)
        connection = get_connection(self.db_path)

        try:
            sql_statement = f"""
            SELECT {selected_columns}
            FROM movies
            WHERE rating >= ?
            ORDER BY rating DESC, id ASC
            LIMIT ?"""
            rows = connection.execute(sql_statement, (min_rating, limit)).fetchall()
            movies = [dict(row) for row in rows]
            
            logger.debug(f"Selected columns {columns}: {len(movies)} movies")
            return movies
        finally:
            connection.close()
