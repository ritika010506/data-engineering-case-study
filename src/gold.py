from pathlib import Path
import duckdb


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "warehouse.duckdb"


def create_gold_tables(connection):
    """Create the Gold Star Schema tables."""

    connection.execute("""
        CREATE TABLE IF NOT EXISTS dim_entity (
            entity_key INTEGER PRIMARY KEY,
            entity_id UUID UNIQUE,
            first_name VARCHAR,
            last_name VARCHAR,
            contact_email VARCHAR,
            registration_date DATE,
            region VARCHAR
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS dim_date (
            date_key INTEGER PRIMARY KEY,
            full_date DATE UNIQUE,
            year INTEGER,
            quarter INTEGER,
            month INTEGER,
            month_name VARCHAR,
            day INTEGER,
            day_of_week VARCHAR
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS fact_transactions (
            transaction_id UUID PRIMARY KEY,
            entity_key INTEGER,
            date_key INTEGER,
            category VARCHAR,
            transaction_amount DOUBLE,
            currency VARCHAR,
            FOREIGN KEY (entity_key) REFERENCES dim_entity(entity_key),
            FOREIGN KEY (date_key) REFERENCES dim_date(date_key)
        )
    """)


def populate_dim_entity(connection):
    """Populate the entity dimension with surrogate keys."""

    connection.execute("DELETE FROM fact_transactions")
    connection.execute("DELETE FROM dim_date")
    connection.execute("DELETE FROM dim_entity")

    connection.execute("""
        INSERT INTO dim_entity
        SELECT
            ROW_NUMBER() OVER (ORDER BY entity_id) AS entity_key,
            entity_id,
            first_name,
            last_name,
            contact_email,
            registration_date,
            region
        FROM silver_entities
    """)


def populate_dim_date(connection):
    """Create a date dimension from transaction dates."""

    connection.execute("""
        INSERT INTO dim_date
        SELECT
            CAST(STRFTIME(transaction_date, '%Y%m%d') AS INTEGER)
                AS date_key,
            transaction_date AS full_date,
            YEAR(transaction_date) AS year,
            QUARTER(transaction_date) AS quarter,
            MONTH(transaction_date) AS month,
            MONTHNAME(transaction_date) AS month_name,
            DAY(transaction_date) AS day,
            DAYNAME(transaction_date) AS day_of_week
        FROM (
            SELECT DISTINCT transaction_date
            FROM silver_transactions
        ) AS unique_dates
        ORDER BY transaction_date
    """)


def populate_fact_transactions(connection):
    """Load transaction facts and connect them to dimensions."""

    connection.execute("""
        INSERT INTO fact_transactions
        SELECT
            t.transaction_id,
            e.entity_key,
            d.date_key,
            t.category,
            t.transaction_amount,
            t.currency
        FROM silver_transactions AS t
        INNER JOIN dim_entity AS e
            ON t.entity_id = e.entity_id
        INNER JOIN dim_date AS d
            ON t.transaction_date = d.full_date
    """)


def run_gold():
    """Build the complete Gold Star Schema."""

    connection = duckdb.connect(str(DB_PATH))

    try:
        create_gold_tables(connection)

        populate_dim_entity(connection)
        populate_dim_date(connection)
        populate_fact_transactions(connection)

        print("\nGOLD LAYER SUMMARY")
        print("-" * 35)

        for table in [
            "dim_entity",
            "dim_date",
            "fact_transactions"
        ]:
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            print(f"{table}: {count} rows")

    finally:
        connection.close()


if __name__ == "__main__":
    run_gold()