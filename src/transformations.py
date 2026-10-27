"""Transform validated Bronze data into clean Silver tables."""

import json
from pathlib import Path

import duckdb


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "warehouse.duckdb"
DLQ_DIR = BASE_DIR / "data" / "dlq"


def create_silver_tables(connection):
    """Create the Silver tables if they do not already exist."""

    connection.execute("""
        CREATE TABLE IF NOT EXISTS silver_entities (
            entity_id UUID,
            first_name VARCHAR,
            last_name VARCHAR,
            contact_email VARCHAR,
            registration_date DATE,
            region VARCHAR
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS silver_transactions (
            transaction_id UUID,
            entity_id UUID,
            category VARCHAR,
            transaction_amount DOUBLE,
            currency VARCHAR,
            timestamp TIMESTAMP,
            transaction_date DATE
        )
    """)


def transform_entities(connection):
    """Deduplicate entities and standardize text fields."""

    # Clear previous Silver data so rerunning this stage
    # does not append duplicate records.
    connection.execute("DELETE FROM silver_entities")

    connection.execute("""
        INSERT INTO silver_entities
        SELECT
            entity_id,
            TRIM(first_name) AS first_name,
            TRIM(last_name) AS last_name,
            LOWER(TRIM(contact_email)) AS contact_email,
            registration_date,
            UPPER(TRIM(region)) AS region
        FROM (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY entity_id
                    ORDER BY
                        registration_date,
                        contact_email,
                        first_name,
                        last_name,
                        region
                ) AS row_num
            FROM bronze_entities
        ) AS ranked_entities
        WHERE row_num = 1
    """)

    silver_entity_count = connection.execute("""
        SELECT COUNT(*)
        FROM silver_entities
    """).fetchone()[0]

    print(f"Silver entities after deduplication: {silver_entity_count}")


def transform_transactions(connection):
    """
    Identify orphan transactions, write them to the DLQ,
    and load only transactions referencing Silver entities.
    """

    # Ensure the DLQ directory exists.
    DLQ_DIR.mkdir(parents=True, exist_ok=True)

    # Find transactions whose entity IDs do not exist in Silver.
    orphan_result = connection.execute("""
        SELECT t.*
        FROM bronze_transactions AS t
        LEFT JOIN silver_entities AS e
            ON t.entity_id = e.entity_id
        WHERE e.entity_id IS NULL
    """)

    columns = [
        description[0]
        for description in orphan_result.description
    ]

    orphan_rows = orphan_result.fetchall()
    orphan_transactions = []

    for row in orphan_rows:
        record = dict(zip(columns, row))

        orphan_transactions.append({
            "record": record,
            "error": (
                f"Referenced entity_id '{record['entity_id']}' "
                "does not exist in silver_entities."
            ),
        })

    # Save orphan transactions using an absolute project path.
    dlq_path = DLQ_DIR / "orphan_transactions.json"

    with dlq_path.open("w", encoding="utf-8") as file:
        json.dump(
            orphan_transactions,
            file,
            indent=2,
            default=str,
        )

    # Clear previously loaded Silver transactions.
    connection.execute("DELETE FROM silver_transactions")

    # Load only transactions whose entity IDs exist in Silver.
    connection.execute("""
        INSERT INTO silver_transactions
        SELECT
            t.transaction_id,
            t.entity_id,
            TRIM(t.category) AS category,
            t.transaction_amount,
            t.currency,
            CAST(t.timestamp AS TIMESTAMP) AS timestamp,
            CAST(t.timestamp AS DATE) AS transaction_date
        FROM bronze_transactions AS t
        INNER JOIN silver_entities AS e
            ON t.entity_id = e.entity_id
    """)

    silver_transaction_count = connection.execute("""
        SELECT COUNT(*)
        FROM silver_transactions
    """).fetchone()[0]

    print(f"Orphan transactions identified: {len(orphan_transactions)}")
    print(f"Orphan DLQ location: {dlq_path}")
    print(f"Silver transactions loaded: {silver_transaction_count}")


def run_transformations():
    """Run the complete Bronze-to-Silver transformation."""

    connection = duckdb.connect(str(DB_PATH))

    try:
        create_silver_tables(connection)

        transform_entities(connection)
        transform_transactions(connection)

        entity_count = connection.execute("""
            SELECT COUNT(*)
            FROM silver_entities
        """).fetchone()[0]

        transaction_count = connection.execute("""
            SELECT COUNT(*)
            FROM silver_transactions
        """).fetchone()[0]

        duplicate_count = connection.execute("""
            SELECT COUNT(*)
            FROM (
                SELECT entity_id
                FROM silver_entities
                GROUP BY entity_id
                HAVING COUNT(*) > 1
            ) AS duplicates
        """).fetchone()[0]

        print("\nSILVER TRANSFORMATION SUMMARY")
        print("-" * 40)
        print(f"Silver entities: {entity_count}")
        print(f"Silver transactions: {transaction_count}")
        print(f"Entity IDs with remaining duplicates: {duplicate_count}")

    finally:
        connection.close()


if __name__ == "__main__":
    run_transformations()