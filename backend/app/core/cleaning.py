from dataclasses import dataclass, field
import re
from typing import Any

import numpy as np
import pandas as pd

from app.core.schema_mapping import normalize_column_name
from app.utils.constants import OPTIONAL_COLUMN_DEFAULTS, STANDARD_COLUMNS
from app.utils.safe_ops import clean_string_value, is_missing_like


@dataclass
class CleaningResult:
    dataframe: pd.DataFrame
    warnings: list[str] = field(default_factory=list)
    duplicate_row_count: int = 0
    duplicate_transaction_id_count: int = 0
    invalid_amount_count: int = 0
    invalid_transaction_time_count: int = 0


_AMOUNT_CURRENCY_PATTERN = re.compile(
    r"(?i)(₹|rs\.?|inr|usd|us\$|\$|eur|€|gbp|£|aud|cad|sgd|aed|jpy|yen|rupees?|dollars?)"
)
_AMOUNT_NUMBER_PATTERN = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def _clean_missing_markers(dataframe: pd.DataFrame) -> pd.DataFrame:
    cleaned = dataframe.copy()
    for column in cleaned.columns:
        if cleaned[column].dtype == object:
            cleaned[column] = cleaned[column].map(lambda value: pd.NA if is_missing_like(value) else value)
    return cleaned


def parse_amount_value(value: Any) -> float:
    """Parse messy currency/amount values defensively.

    Known missing markers are normalized to 0.0. Arbitrary unparseable text
    becomes NaN so validation and warnings can distinguish invalid amounts.
    Negative values are preserved.
    """
    try:
        if is_missing_like(value):
            return 0.0
        if isinstance(value, (int, float, np.integer, np.floating)):
            amount = float(value)
            if np.isnan(amount) or np.isinf(amount):
                return 0.0
            return amount

        text = str(value).strip()
        if not text or text.lower() in {"n/a", "na", "null", "none", "nan", "missing", "undefined"}:
            return 0.0

        is_parenthesized_negative = text.startswith("(") and text.endswith(")")
        text = _AMOUNT_CURRENCY_PATTERN.sub("", text)
        text = text.replace(",", "").replace(" ", "")
        text = text.replace("−", "-").replace("—", "-").replace("–", "-")
        match = _AMOUNT_NUMBER_PATTERN.search(text)
        if not match:
            return float("nan")

        amount = float(match.group(0))
        if np.isnan(amount) or np.isinf(amount):
            return 0.0
        return -abs(amount) if is_parenthesized_negative else amount
    except (TypeError, ValueError, OverflowError):
        return float("nan")

def _parse_transaction_dates(series: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(series, errors="coerce", format="mixed")
    except (TypeError, ValueError):
        return pd.to_datetime(series, errors="coerce")


def _string_series(series: pd.Series, default: str | None = None, max_length: int | None = None) -> pd.Series:
    return series.map(lambda value: clean_string_value(value, default=default, max_length=max_length)).astype("object")


def clean_transactions_dataframe(dataframe: pd.DataFrame) -> CleaningResult:
    if dataframe is None:
        return CleaningResult(dataframe=pd.DataFrame(), warnings=["No dataframe was provided for cleaning."])

    cleaned = dataframe.copy()
    warnings: list[str] = []
    original_rows = len(cleaned.index)

    cleaned = _clean_missing_markers(cleaned).copy()

    if "original_row_number" not in cleaned.columns:
        cleaned["original_row_number"] = range(1, original_rows + 1)

    for column in STANDARD_COLUMNS:
        if column not in cleaned.columns:
            if column == "transaction_id":
                cleaned[column] = [f"SP-ROW-{index + 1:06d}" for index in range(original_rows)]
                warnings.append("transaction_id was missing during cleaning; generated row-based transaction IDs.")
            elif column in OPTIONAL_COLUMN_DEFAULTS:
                cleaned[column] = OPTIONAL_COLUMN_DEFAULTS[column]

    if "amount" in cleaned.columns:
        original_non_missing = cleaned["amount"].map(lambda value: not is_missing_like(value))
        cleaned["amount"] = cleaned["amount"].map(parse_amount_value).astype("float64")
        invalid_amount_count = int(original_non_missing.sum() - cleaned.loc[original_non_missing, "amount"].notna().sum())
        if invalid_amount_count > 0:
            warnings.append(f"{invalid_amount_count} amount value(s) could not be parsed and were set to missing.")
    else:
        invalid_amount_count = 0
        warnings.append("amount column was not available for cleaning.")

    if "transaction_time" in cleaned.columns:
        original_non_missing_dates = cleaned["transaction_time"].map(lambda value: not is_missing_like(value))
        cleaned["transaction_time"] = _parse_transaction_dates(cleaned["transaction_time"])
        invalid_time_count = int(original_non_missing_dates.sum() - cleaned.loc[original_non_missing_dates, "transaction_time"].notna().sum())
        if invalid_time_count > 0:
            warnings.append(f"{invalid_time_count} transaction_time value(s) could not be parsed and were set to missing.")
    else:
        invalid_time_count = 0
        warnings.append("transaction_time column was not available for cleaning.")

    if "user_id" in cleaned.columns:
        cleaned["user_id"] = _string_series(cleaned["user_id"], default=None, max_length=500)
    else:
        warnings.append("user_id column was not available for cleaning.")

    text_defaults = {
        "merchant": OPTIONAL_COLUMN_DEFAULTS["merchant"],
        "location": OPTIONAL_COLUMN_DEFAULTS["location"],
        "payment_method": OPTIONAL_COLUMN_DEFAULTS["payment_method"],
        "status": OPTIONAL_COLUMN_DEFAULTS["status"],
        "currency": OPTIONAL_COLUMN_DEFAULTS["currency"],
    }
    for column, default in text_defaults.items():
        if column in cleaned.columns:
            cleaned[column] = _string_series(cleaned[column], default=default, max_length=1000)

    if "transaction_id" in cleaned.columns:
        cleaned["transaction_id"] = _string_series(cleaned["transaction_id"], default=None, max_length=500)
        missing_transaction_ids = cleaned["transaction_id"].isna()
        if bool(missing_transaction_ids.any()):
            cleaned.loc[missing_transaction_ids, "transaction_id"] = [
                f"SP-ROW-{int(row_number):06d}" for row_number in cleaned.loc[missing_transaction_ids, "original_row_number"]
            ]
            warnings.append(f"{int(missing_transaction_ids.sum())} missing transaction_id value(s) were replaced with row-based IDs.")

    cleaned = cleaned.copy()
    duplicate_check_columns = [column for column in cleaned.columns if column not in {"original_row_number"}]
    if "transaction_id" in duplicate_check_columns:
        transaction_ids = cleaned["transaction_id"].fillna("").astype(str)
        generated_transaction_ids = transaction_ids.str.match(r"^SP-ROW-\d{6}$").all() if len(transaction_ids.index) else False
        if generated_transaction_ids:
            duplicate_check_columns = [column for column in duplicate_check_columns if column != "transaction_id"]
    duplicate_row_mask = cleaned[duplicate_check_columns].duplicated(keep=False) if duplicate_check_columns else pd.Series([False] * len(cleaned.index), index=cleaned.index)
    duplicate_row_count = int(cleaned[duplicate_check_columns].duplicated().sum()) if duplicate_check_columns else 0
    cleaned["duplicate_row_flag"] = duplicate_row_mask
    if duplicate_row_count > 0:
        warnings.append(f"Detected {duplicate_row_count} duplicate row(s). Rows were preserved and flagged.")

    if "transaction_id" in cleaned.columns:
        duplicate_transaction_id_mask = cleaned["transaction_id"].duplicated(keep=False) & cleaned["transaction_id"].notna()
        duplicate_transaction_id_count = int(duplicate_transaction_id_mask.sum())
        cleaned["duplicate_transaction_id_flag"] = duplicate_transaction_id_mask
        if duplicate_transaction_id_count > 0:
            warnings.append(f"Detected {duplicate_transaction_id_count} row(s) sharing duplicate transaction_id values. Rows were preserved and flagged.")
    else:
        duplicate_transaction_id_count = 0
        cleaned["duplicate_transaction_id_flag"] = False

    if len(cleaned.index) != original_rows:
        warnings.append("Cleaning changed row count unexpectedly; this should be reviewed.")

    return CleaningResult(
        dataframe=cleaned,
        warnings=warnings,
        duplicate_row_count=duplicate_row_count,
        duplicate_transaction_id_count=duplicate_transaction_id_count,
        invalid_amount_count=invalid_amount_count,
        invalid_transaction_time_count=invalid_time_count,
    )


def clean_starter_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    cleaned = dataframe.copy()
    cleaned.columns = [normalize_column_name(column) for column in cleaned.columns]
    for column in cleaned.select_dtypes(include=["object"]).columns:
        cleaned[column] = cleaned[column].map(lambda value: clean_string_value(value, default=None))
    return cleaned
