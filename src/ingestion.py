import csv
import json
from pathlib import Path

import duckdb
from pydantic import ValidationError

from contracts import EntityContract, TransactionContract


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
DLQ_DIR = BASE_DIR / "data" / "dlq"
DB_PATH = BASE_DIR / "warehouse.duckdb"


def validate_records(records, contract, dlq_path):
    """Validate records and save invalid records to a DLQ JSON file."""
    valid_records = []
    invalid_records = []

    for record in records:
        try:
            validated = contract.model_validate(record)
            valid_records.append(validated.model_dump(mode="json"))

        except ValidationError as exc:
            invalid_records.append({
                "record": record,
                "error": exc.errors(include_url=False),
            })

    with dlq_path.open("w", encoding="utf-8") as file:
        json.dump(invalid_records, file, indent=2, default=str)

    return valid_records, invalid_records


def create_bronze_tables(connection):
    """Create the Bronze tables if they do not already exist."""
    connection.execute("""
        CREATE TABLE IF NOT EXISTS bronze_entities (
            entity_id UUID,
            first_name VARCHAR,
            last_name VARCHAR,
            contact_email VARCHAR,
            registration_date DATE,
            region VARCHAR
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS bronze_transactions (
            transaction_id UUID,
            entity_id UUID,
            category VARCHAR,
            transaction_amount DOUBLE,
            currency VARCHAR,
            timestamp TIMESTAMP
        )
    """)


def load_bronze_entities(connection, records):
    """Insert validated entity records into Bronze."""
    if not records:
        return

    connection.executemany("""
        INSERT INTO bronze_entities VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (
            r["entity_id"],
            r["first_name"],
            r["last_name"],
            r["contact_email"],
            r["registration_date"],
            r["region"],
        )
        for r in records
    ])


def load_bronze_transactions(connection, records):
    """Insert validated transaction records into Bronze."""
    if not records:
        return

    connection.executemany("""
        INSERT INTO bronze_transactions VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (
            r["transaction_id"],
            r["entity_id"],
            r["category"],
            r["transaction_amount"],
            r["currency"],
            r["timestamp"],
        )
        for r in records
    ])


def run_ingestion():
    DLQ_DIR.mkdir(parents=True, exist_ok=True)

    # Read customer CSV.
    with (RAW_DIR / "entities.csv").open(
        "r", newline="", encoding="utf-8"
    ) as file:
        entities = list(csv.DictReader(file))

    # Read transaction JSON.
    with (RAW_DIR / "transactions.json").open(
        "r", encoding="utf-8"
    ) as file:
        transactions = json.load(file)

    # Validate customer records.
    valid_entities, invalid_entities = validate_records(
        entities,
        EntityContract,
        DLQ_DIR / "invalid_entities.json",
    )

    # Validate transaction records.
    valid_transactions, invalid_transactions = validate_records(
        transactions,
        TransactionContract,
        DLQ_DIR / "invalid_transactions.json",
    )

    # Initialize the database and Bronze tables.
    connection = duckdb.connect(str(DB_PATH))

    try:
        create_bronze_tables(connection)

        # Clear previous Bronze data before reloading.
        connection.execute("DELETE FROM bronze_transactions")
        connection.execute("DELETE FROM bronze_entities")

        # Load only the newly validated records.
        load_bronze_entities(connection, valid_entities)
        load_bronze_transactions(connection, valid_transactions)

        entity_count = connection.execute(
            "SELECT COUNT(*) FROM bronze_entities"
        ).fetchone()[0]

        transaction_count = connection.execute(
            "SELECT COUNT(*) FROM bronze_transactions"
        ).fetchone()[0]

        print("\nINGESTION SUMMARY")
        print("-" * 35)
        print(f"Entity records read: {len(entities)}")
        print(f"Valid entities: {len(valid_entities)}")
        print(f"Invalid entities: {len(invalid_entities)}")
        print(f"Transaction records read: {len(transactions)}")
        print(f"Valid transactions: {len(valid_transactions)}")
        print(f"Invalid transactions: {len(invalid_transactions)}")
        print(f"Rows in bronze_entities: {entity_count}")
        print(f"Rows in bronze_transactions: {transaction_count}")
        print(f"Database: {DB_PATH}")

    finally:
        connection.close()


if __name__ == "__main__":
    run_ingestion()
