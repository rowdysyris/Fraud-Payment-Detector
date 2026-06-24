from dataclasses import dataclass, field
import re
from typing import Dict, Optional

import pandas as pd

from app.utils.constants import (
    COLUMN_SYNONYMS,
    OPTIONAL_COLUMN_DEFAULTS,
    OPTIONAL_STANDARD_COLUMNS,
    REQUIRED_STANDARD_COLUMNS,
    STANDARD_COLUMNS,
)
from app.utils.safe_ops import make_unique_column_names


@dataclass
class SchemaMappingResult:
    dataframe: pd.DataFrame
    mapped_columns: Dict[str, Optional[str]]
    missing_required_columns: list[str]
    original_columns: list[str]
    warnings: list[str] = field(default_factory=list)


def normalize_column_name(column_name: object) -> str:
    value = str(column_name or "").strip().lower()
    value = value.replace("₹", " rupee ").replace("$", " usd ")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "unnamed_column"


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _tokenize(value: str) -> set[str]:
    return {token for token in normalize_column_name(value).split("_") if token}


def _score_column_for_standard(normalized_column: str, standard_column: str) -> int:
    column_compact = _compact(normalized_column)
    column_tokens = _tokenize(normalized_column)
    best_score = 0

    for synonym in COLUMN_SYNONYMS[standard_column]:
        normalized_synonym = normalize_column_name(synonym)
        synonym_compact = _compact(normalized_synonym)
        synonym_tokens = _tokenize(normalized_synonym)

        if normalized_column == normalized_synonym:
            best_score = max(best_score, 100)
        elif column_compact == synonym_compact:
            best_score = max(best_score, 98)
        elif synonym_compact and synonym_compact in column_compact:
            best_score = max(best_score, 88)
        elif column_compact and column_compact in synonym_compact and len(column_compact) >= 3:
            best_score = max(best_score, 82)
        elif synonym_tokens and synonym_tokens.issubset(column_tokens):
            best_score = max(best_score, 78)
        elif column_tokens and synonym_tokens:
            overlap = column_tokens.intersection(synonym_tokens)
            if overlap:
                denominator = max(len(synonym_tokens), 1)
                score = 55 + int(20 * len(overlap) / denominator if denominator != 0 else 0)
                best_score = max(best_score, score)

    return best_score


def _build_candidates(columns: list[object]) -> list[tuple[str, object, str]]:
    return [(normalize_column_name(column), column, _compact(normalize_column_name(column))) for column in columns]


def build_schema_mapping(dataframe: pd.DataFrame) -> Dict[str, str]:
    result = map_transaction_schema(dataframe)
    return {standard: original for standard, original in result.mapped_columns.items() if original is not None}


def map_transaction_schema(dataframe: pd.DataFrame) -> SchemaMappingResult:
    if dataframe is None:
        return SchemaMappingResult(
            dataframe=pd.DataFrame(),
            mapped_columns={column: None for column in STANDARD_COLUMNS},
            missing_required_columns=REQUIRED_STANDARD_COLUMNS.copy(),
            original_columns=[],
            warnings=["No dataframe was provided for schema mapping."],
        )

    original_columns = [str(column) for column in dataframe.columns]
    mapped = dataframe.copy()
    normalized_initial_columns = [str(column or "").strip().lower() or f"unnamed_column_{index + 1}" for index, column in enumerate(mapped.columns)]
    normalized_unique_columns = make_unique_column_names(normalized_initial_columns)
    original_by_normalized = {
        normalized: original for normalized, original in zip(normalized_unique_columns, original_columns, strict=False)
    }
    mapped.columns = normalized_unique_columns
    candidates = _build_candidates(list(mapped.columns))
    used_original_columns: set[object] = set()
    mapped_columns: Dict[str, Optional[str]] = {column: None for column in STANDARD_COLUMNS}
    warnings: list[str] = []

    mapping_order = [*REQUIRED_STANDARD_COLUMNS, *[column for column in STANDARD_COLUMNS if column not in REQUIRED_STANDARD_COLUMNS]]

    for standard_column in mapping_order:
        best_original: object | None = None
        best_score = 0
        for normalized_column, original_column, _ in candidates:
            if original_column in used_original_columns:
                continue
            score = _score_column_for_standard(normalized_column, standard_column)
            if score > best_score:
                best_score = score
                best_original = original_column

        threshold = 55 if standard_column in {"merchant", "location", "payment_method", "status", "currency"} else 60
        if best_original is not None:
            best_tokens = _tokenize(str(best_original))
            if standard_column == "transaction_id" and best_tokens.intersection({"user", "customer", "cust", "account", "cardholder", "merchant", "shop", "vendor", "seller", "amount", "amt", "date", "time", "timestamp", "status", "currency"}):
                best_score = min(best_score, 40)
            if standard_column == "amount" and not best_tokens.intersection({"amount", "amt", "value", "price", "total", "payment", "paid", "charge", "cost", "gross", "net"}):
                best_score = min(best_score, 40)
            if standard_column == "transaction_time" and not best_tokens.intersection({"date", "time", "timestamp", "datetime", "created", "paid", "purchase", "order"}):
                best_score = min(best_score, 40)
            if standard_column == "user_id" and not best_tokens.intersection({"user", "customer", "cust", "account", "cardholder", "client", "member", "buyer"}):
                best_score = min(best_score, 40)
        if best_original is not None and best_score >= threshold:
            mapped_columns[standard_column] = original_by_normalized.get(str(best_original), str(best_original))
            used_original_columns.add(best_original)
            if standard_column not in mapped.columns:
                mapped[standard_column] = mapped[best_original]
        elif standard_column in OPTIONAL_STANDARD_COLUMNS and standard_column != "transaction_id":
            mapped[standard_column] = OPTIONAL_COLUMN_DEFAULTS.get(standard_column, "Unknown")

    if mapped_columns.get("transaction_id") is None and "transaction_id" not in mapped.columns:
        mapped["transaction_id"] = [f"SP-ROW-{index + 1:06d}" for index in range(len(mapped.index))]
        mapped_columns["transaction_id"] = None
        warnings.append("transaction_id column was not found; generated stable row-based transaction IDs.")

    missing_required_columns = [column for column in REQUIRED_STANDARD_COLUMNS if mapped_columns.get(column) is None and column not in mapped.columns]
    return SchemaMappingResult(
        dataframe=mapped,
        mapped_columns=mapped_columns,
        missing_required_columns=missing_required_columns,
        original_columns=original_columns,
        warnings=warnings,
    )
