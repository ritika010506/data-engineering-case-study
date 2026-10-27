import json

import duckdb
import pytest
from pydantic import ValidationError

from src.contracts import EntityContract, TransactionContract
from src import transformations


def valid_entity():
    return {
        "entity_id": "550e8400-e29b-41d4-a716-446655440000",
        "first_name": "Ravi",
        "last_name": "Kumar",
        "contact_email": "ravi@example.com",
        "registration_date": "2025-01-15",
        "region": "South",
    }


def valid_transaction():
    return {
        "transaction_id": "550e8400-e29b-41d4-a716-446655440001",
        "entity_id": "550e8400-e29b-41d4-a716-446655440000",
        "category": "Electronics",
        "transaction_amount": 150.50,
        "currency": "USD",
        "timestamp": "2025-01-15T10:30:00",
    }


# --------------------------------------------------
# 1. Entity validation tests
# --------------------------------------------------

def test_valid_entity_accepted():
    entity = EntityContract.model_validate(valid_entity())

    assert entity.first_name == "Ravi"
    assert entity.contact_email == "ravi@example.com"


def test_invalid_email_rejected():
    record = valid_entity()
    record["contact_email"] = "not-an-email"

    with pytest.raises(ValidationError):
        EntityContract.model_validate(record)


# --------------------------------------------------
# 2. Transaction validation tests
# --------------------------------------------------

@pytest.mark.parametrize("amount", [-50.0, 0])
def test_invalid_transaction_amount_rejected(amount):
    record = valid_transaction()
    record["transaction_amount"] = amount

    with pytest.raises(ValidationError):
        TransactionContract.model_validate(record)


@pytest.mark.parametrize("entity_id", [None, ""])
def test_null_or_empty_entity_id_rejected(entity_id):
    record = valid_transaction()
    record["entity_id"] = entity_id

    with pytest.raises(ValidationError):
        TransactionContract.model_validate(record)


def test_missing_entity_id_rejected():
    record = valid_transaction()
    del record["entity_id"]

    with pytest.raises(ValidationError):
        TransactionContract.model_validate(record)


def test_invalid_currency_rejected():
    record = valid_transaction()
    record["currency"] = "INR"

    with pytest.raises(ValidationError):
        TransactionContract.model_validate(record)


# --------------------------------------------------
# 3. Silver entity deduplication test
# --------------------------------------------------

def test_silver_entities_are_deduplicated():
    connection = duckdb.connect(":memory:")

    try:
        transformations.create_silver_tables(connection)

        connection.execute("""
            CREATE TABLE bronze_entities (
                entity_id UUID,
                first_name VARCHAR,
                last_name VARCHAR,
                contact_email VARCHAR,
                registration_date DATE,
                region VARCHAR
            )
        """)

        entity = valid_entity()

        # Insert the same entity twice.
        connection.executemany(
            """
            INSERT INTO bronze_entities
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    entity["entity_id"],
                    entity["first_name"],
                    entity["last_name"],
                    entity["contact_email"],
                    entity["registration_date"],
                    entity["region"],
                ),
                (
                    entity["entity_id"],
                    entity["first_name"],
                    entity["last_name"],
                    entity["contact_email"],
                    entity["registration_date"],
                    entity["region"],
                ),
            ],
        )

        transformations.transform_entities(connection)

        result = connection.execute("""
            SELECT COUNT(*)
            FROM silver_entities
        """).fetchone()[0]

        assert result == 1

    finally:
        connection.close()


# --------------------------------------------------
# 4. Orphan transaction DLQ test
# --------------------------------------------------

def test_orphan_transaction_is_sent_to_dlq(tmp_path, monkeypatch):
    connection = duckdb.connect(":memory:")

    try:
        transformations.create_silver_tables(connection)

        # Redirect the DLQ to pytest's temporary directory.
        monkeypatch.setattr(
            transformations,
            "DLQ_DIR",
            tmp_path,
        )

        connection.execute("""
            CREATE TABLE bronze_transactions (
                transaction_id UUID,
                entity_id UUID,
                category VARCHAR,
                transaction_amount DOUBLE,
                currency VARCHAR,
                timestamp TIMESTAMP
            )
        """)

        valid_entity_id = "550e8400-e29b-41d4-a716-446655440000"
        orphan_entity_id = "550e8400-e29b-41d4-a716-446655440099"

        # Only the first entity exists in Silver.
        connection.execute(
            """
            INSERT INTO silver_entities
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                valid_entity_id,
                "Ravi",
                "Kumar",
                "ravi@example.com",
                "2025-01-15",
                "SOUTH",
            ],
        )

        # Both transactions have otherwise valid fields.
        connection.executemany(
            """
            INSERT INTO bronze_transactions
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "550e8400-e29b-41d4-a716-446655440001",
                    valid_entity_id,
                    "Electronics",
                    150.50,
                    "USD",
                    "2025-01-15 10:30:00",
                ),
                (
                    "550e8400-e29b-41d4-a716-446655440002",
                    orphan_entity_id,
                    "Clothing",
                    250.00,
                    "EUR",
                    "2025-01-16 11:30:00",
                ),
            ],
        )

        transformations.transform_transactions(connection)

        # Exactly one transaction should enter Silver.
        silver_count = connection.execute("""
            SELECT COUNT(*)
            FROM silver_transactions
        """).fetchone()[0]

        assert silver_count == 1

        # The orphan should be written to the DLQ.
        dlq_path = tmp_path / "orphan_transactions.json"

        assert dlq_path.exists()

        with dlq_path.open("r", encoding="utf-8") as file:
            dlq_records = json.load(file)

        assert len(dlq_records) == 1
        assert dlq_records[0]["record"]["entity_id"] == orphan_entity_id
        assert "error" in dlq_records[0]

    finally:
        connection.close()