"""Generate reproducible mock entity and transaction data."""

import csv
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"

# Seed the random number generator for reproducibility.
random.seed(42)


# Entity data configuration
VALID_ENTITY_COUNT = 1000
MALFORMED_ENTITY_COUNT = 60
DUPLICATE_ENTITY_COUNT = 60

# Transaction data configuration
TOTAL_TRANSACTIONS = 5000
NEGATIVE_AMOUNT_COUNT = 50
MISSING_ENTITY_ID_COUNT = 50
INVALID_CURRENCY_COUNT = 50
ORPHAN_TRANSACTION_COUNT = 50


FIRST_NAMES = [
    "Aarav", "Priya", "Ravi", "Ananya", "Arjun",
    "Meera", "Karan", "Divya", "Rohan", "Sneha",
]

LAST_NAMES = [
    "Sharma", "Kumar", "Patel", "Reddy", "Iyer",
    "Singh", "Nair", "Gupta", "Rao", "Verma",
]

REGIONS = [
    "North",
    "South",
    "East",
    "West",
    "Central",
    "Northeast",
    "Northwest",
    "Southeast",
]

CATEGORIES = [
    "Electronics",
    "Clothing",
    "Grocery",
    "Healthcare",
    "Retail",
]

CURRENCIES = ["USD", "EUR", "GBP"]

MALFORMED_EMAILS = [
    "john.example.com",
    "john@",
    "@example.com",
    "john.example",
    "invalid-email",
]


def new_uuid():
    """Generate a UUID using the seeded random number generator."""
    return str(uuid.UUID(int=random.getrandbits(128), version=4))


def generate_entities():
    """
    Generate valid entities, malformed-email entities,
    and exact duplicate records.

    Returns:
        valid_entity_ids: IDs of entities with valid emails.
        rejected_entity_ids: IDs of entities with malformed emails.
    """

    entities = []
    valid_entity_ids = []
    rejected_entity_ids = []

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------
    # 1. Generate valid, unique entities.
    # --------------------------------------------------
    for i in range(VALID_ENTITY_COUNT):
        entity_id = new_uuid()

        entity = {
            "entity_id": entity_id,
            "first_name": random.choice(FIRST_NAMES),
            "last_name": random.choice(LAST_NAMES),
            "contact_email": f"user{i}@example.com",
            "registration_date": (
                datetime.now()
                - timedelta(days=random.randint(1, 1000))
            ).date().isoformat(),
            "region": random.choice(REGIONS),
        }

        entities.append(entity)
        valid_entity_ids.append(entity_id)

    # --------------------------------------------------
    # 2. Generate entities with deliberately malformed
    #    email addresses.
    # --------------------------------------------------
    for i in range(MALFORMED_ENTITY_COUNT):
        entity_id = new_uuid()

        entity = {
            "entity_id": entity_id,
            "first_name": random.choice(FIRST_NAMES),
            "last_name": random.choice(LAST_NAMES),
            "contact_email": MALFORMED_EMAILS[
                i % len(MALFORMED_EMAILS)
            ],
            "registration_date": (
                datetime.now()
                - timedelta(days=random.randint(1, 1000))
            ).date().isoformat(),
            "region": random.choice(REGIONS),
        }

        entities.append(entity)
        rejected_entity_ids.append(entity_id)

    # --------------------------------------------------
    # 3. Create exact duplicates of valid entities.
    #    Copy every field, including entity_id.
    # --------------------------------------------------
    duplicates = [
        entity.copy()
        for entity in entities[:DUPLICATE_ENTITY_COUNT]
    ]

    entities.extend(duplicates)

    # Shuffle the records so that groups are not
    # arranged together in the generated CSV.
    random.shuffle(entities)

    # --------------------------------------------------
    # 4. Write entities to CSV.
    # --------------------------------------------------
    entity_fields = [
        "entity_id",
        "first_name",
        "last_name",
        "contact_email",
        "registration_date",
        "region",
    ]

    with (RAW_DIR / "entities.csv").open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=entity_fields)
        writer.writeheader()
        writer.writerows(entities)

    print("\nENTITY DATA GENERATION")
    print("-" * 40)
    print(f"Valid unique entities: {VALID_ENTITY_COUNT}")
    print(f"Malformed-email entities: {MALFORMED_ENTITY_COUNT}")
    print(f"Exact duplicate records: {DUPLICATE_ENTITY_COUNT}")
    print(f"Total entity records: {len(entities)}")

    return valid_entity_ids, rejected_entity_ids


def generate_transactions(valid_entity_ids, rejected_entity_ids):
    """
    Generate transactions containing valid records,
    schema-validation failures, and orphan references.
    """

    transactions = []

    start_date = datetime.now() - timedelta(days=365)
    end_date = datetime.now()
    total_seconds = int((end_date - start_date).total_seconds())

    # Generate the baseline transaction records.
    for _ in range(TOTAL_TRANSACTIONS):
        timestamp = start_date + timedelta(
            seconds=random.randint(0, total_seconds)
        )

        transaction = {
            "transaction_id": new_uuid(),
            "entity_id": random.choice(valid_entity_ids),
            "category": random.choice(CATEGORIES),
            "transaction_amount": round(
                random.uniform(10, 5000), 2
            ),
            "currency": random.choice(CURRENCIES),
            "timestamp": timestamp.isoformat(),
        }

        transactions.append(transaction)

    # --------------------------------------------------
    # 1. Negative transaction amounts.
    # Indices: 0-49.
    # --------------------------------------------------
    negative_start = 0
    negative_end = NEGATIVE_AMOUNT_COUNT

    for i in range(negative_start, negative_end):
        transactions[i]["transaction_amount"] = -abs(
            transactions[i]["transaction_amount"]
        )

    # --------------------------------------------------
    # 2. Missing/null entity IDs.
    # Indices: 50-99.
    # --------------------------------------------------
    missing_start = negative_end
    missing_end = missing_start + MISSING_ENTITY_ID_COUNT

    for i in range(missing_start, missing_end):
        transactions[i]["entity_id"] = None

    # --------------------------------------------------
    # 3. Invalid currencies.
    # Indices: 100-149.
    # --------------------------------------------------
    currency_start = missing_end
    currency_end = currency_start + INVALID_CURRENCY_COUNT

    for i in range(currency_start, currency_end):
        transactions[i]["currency"] = "INR"

    # --------------------------------------------------
    # 4. Orphan transactions.
    # Indices: 150-199.
    #
    # These records have valid transaction fields but
    # reference entities rejected for malformed emails.
    # They should pass Pydantic validation and then be
    # rejected during the Silver transformation.
    # --------------------------------------------------
    orphan_start = currency_end
    orphan_end = orphan_start + ORPHAN_TRANSACTION_COUNT

    for i in range(orphan_start, orphan_end):
        transactions[i]["entity_id"] = random.choice(
            rejected_entity_ids
        )

    # Save the transaction JSON.
    with (RAW_DIR / "transactions.json").open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(transactions, file, indent=2)

    validation_failures = (
        NEGATIVE_AMOUNT_COUNT
        + MISSING_ENTITY_ID_COUNT
        + INVALID_CURRENCY_COUNT
    )

    print("\nTRANSACTION DATA GENERATION")
    print("-" * 40)
    print(f"Total transactions: {len(transactions)}")
    print(f"Negative amounts: {NEGATIVE_AMOUNT_COUNT}")
    print(f"Missing entity IDs: {MISSING_ENTITY_ID_COUNT}")
    print(f"Invalid currencies: {INVALID_CURRENCY_COUNT}")
    print(f"Orphan transactions: {ORPHAN_TRANSACTION_COUNT}")
    print(f"Expected validation failures: {validation_failures}")
    print(
        "Expected valid transactions before orphan filtering: "
        f"{TOTAL_TRANSACTIONS - validation_failures}"
    )


def main():
    """Generate entity and transaction datasets."""
    valid_entity_ids, rejected_entity_ids = generate_entities()

    generate_transactions(
        valid_entity_ids,
        rejected_entity_ids,
    )

    print("\nMock data generation completed successfully.")


if __name__ == "__main__":
    main()