from dataclasses import dataclass, field
from typing import Dict, Optional

import pandas as pd

from app.utils.constants import REQUIRED_STANDARD_COLUMNS


@dataclass
class ValidationReport:
    is_valid: bool
    message: str
    row_count: int
    column_count: int
    original_rows: int = 0
    cleaned_rows: int = 0
    original_columns: list[str] = field(default_factory=list)
    mapped_columns: Dict[str, Optional[str]] = field(default_factory=dict)
    missing_required_columns: list[str] = field(default_factory=list)
    cleaning_warnings: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)


def validate_basic_dataframe(dataframe: pd.DataFrame) -> ValidationReport:
    if dataframe is None:
        return ValidationReport(False, "No dataframe was created from the uploaded file.", 0, 0, validation_errors=["No dataframe was created from the uploaded file."])

    row_count, column_count = dataframe.shape
    if column_count == 0:
        message = "Uploaded file has no columns."
        return ValidationReport(False, message, row_count, column_count, original_rows=row_count, cleaned_rows=row_count, original_columns=[], validation_errors=[message])

    if row_count == 0:
        message = "Uploaded file has headers but no transaction rows."
        return ValidationReport(False, message, row_count, column_count, original_rows=row_count, cleaned_rows=row_count, original_columns=[str(column) for column in dataframe.columns], validation_errors=[message])

    return ValidationReport(True, "Basic dataframe validation passed.", row_count, column_count, original_rows=row_count, cleaned_rows=row_count, original_columns=[str(column) for column in dataframe.columns])


def validate_transaction_dataset(
    dataframe: pd.DataFrame,
    *,
    original_rows: int,
    original_columns: list[str],
    mapped_columns: Dict[str, Optional[str]],
    missing_required_columns: list[str],
    cleaning_warnings: list[str] | None = None,
) -> ValidationReport:
    errors: list[str] = []
    cleaning_warnings = cleaning_warnings or []

    if dataframe is None:
        errors.append("No dataframe was created from the uploaded file.")
        return ValidationReport(
            is_valid=False,
            message="No dataframe was created from the uploaded file.",
            row_count=0,
            column_count=0,
            original_rows=original_rows,
            cleaned_rows=0,
            original_columns=original_columns,
            mapped_columns=mapped_columns,
            missing_required_columns=missing_required_columns,
            cleaning_warnings=cleaning_warnings,
            validation_errors=errors,
        )

    cleaned_rows, column_count = dataframe.shape
    if column_count == 0:
        errors.append("Uploaded file has no columns.")
    if original_rows == 0 or cleaned_rows == 0:
        errors.append("Uploaded file has headers but no transaction rows.")

    for column in REQUIRED_STANDARD_COLUMNS:
        if column in missing_required_columns or column not in dataframe.columns:
            errors.append(f"Missing required column: {column}.")

    if "amount" in dataframe.columns and "amount" not in missing_required_columns and cleaned_rows > 0:
        if dataframe["amount"].isna().all():
            errors.append("All amount values are missing or invalid.")

    if "user_id" in dataframe.columns and "user_id" not in missing_required_columns and cleaned_rows > 0:
        if dataframe["user_id"].isna().all():
            errors.append("All user_id values are missing.")

    if "transaction_time" in dataframe.columns and "transaction_time" not in missing_required_columns and cleaned_rows > 0:
        if dataframe["transaction_time"].isna().all():
            errors.append("All transaction_time values are missing or invalid.")

    is_valid = len(errors) == 0
    message = "Dataset validation passed." if is_valid else "Dataset validation failed: " + "; ".join(errors)
    return ValidationReport(
        is_valid=is_valid,
        message=message,
        row_count=cleaned_rows,
        column_count=column_count,
        original_rows=original_rows,
        cleaned_rows=cleaned_rows,
        original_columns=original_columns,
        mapped_columns=mapped_columns,
        missing_required_columns=missing_required_columns,
        cleaning_warnings=cleaning_warnings,
        validation_errors=errors,
    )
