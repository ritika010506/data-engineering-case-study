from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class EntityContract(BaseModel):
    """Validation rules for customer/entity records."""

    model_config = ConfigDict(extra="forbid")

    entity_id: UUID
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    contact_email: EmailStr
    registration_date: date
    region: str = Field(min_length=1)


class TransactionContract(BaseModel):
    """Validation rules for transaction records."""

    model_config = ConfigDict(extra="forbid")

    transaction_id: UUID
    entity_id: UUID
    category: str = Field(min_length=1)
    transaction_amount: float = Field(gt=0)
    currency: str
    timestamp: datetime

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value):
        allowed_currencies = {"USD", "EUR", "GBP"}

        if value not in allowed_currencies:
            raise ValueError(f"Invalid currency: {value}")

        return value
