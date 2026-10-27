from pathlib import Path
import duckdb


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "warehouse.duckdb"
SQL_PATH = BASE_DIR / "src" / "queries.sql"


def run_queries():
    connection = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        sql_text = SQL_PATH.read_text(encoding="utf-8")

        queries = [
            query.strip()
            for query in sql_text.split(";")
            if query.strip()
        ]

        for index, query in enumerate(queries, start=1):
            print(f"\nQUERY {index} RESULTS")
            print("=" * 50)

            result = connection.execute(query)
            columns = [description[0] for description in result.description]
            rows = result.fetchall()

            print(" | ".join(columns))

            if not rows:
                print("No results returned.")
            else:
                for row in rows:
                    print(" | ".join(str(value) for value in row))

    finally:
        connection.close()


if __name__ == "__main__":
    run_queries()