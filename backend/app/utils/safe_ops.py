import math
import re
from datetime import date, datetime
from typing import Any, Iterable

import numpy as np
import pandas as pd

from app.utils.constants import MISSING_MARKERS


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    return cleaned.strip("._") or "file"


def is_missing_like(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        _pd_null_check_failed = True
    if isinstance(value, str):
        return value.strip().lower() in MISSING_MARKERS
    return False


def clean_string_value(value: Any, default: str | None = None, max_length: int | None = None) -> str | None:
    if is_missing_like(value):
        return default
    text = str(value).strip()
    if text.lower() in MISSING_MARKERS:
        return default
    text = re.sub(r"\s+", " ", text)
    if max_length is not None and len(text) > max_length:
        return text[:max_length]
    return text


def make_unique_column_names(columns: Iterable[Any]) -> list[str]:
    seen: dict[str, int] = {}
    output: list[str] = []
    for index, column in enumerate(columns):
        base = str(column).strip() if str(column).strip() else f"unnamed_column_{index + 1}"
        count = seen.get(base, 0)
        if count == 0:
            output.append(base)
        else:
            output.append(f"{base}_{count + 1}")
        seen[base] = count + 1
    return output


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if is_missing_like(value):
            return default
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if is_missing_like(value):
            return default
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except (TypeError, ValueError, OverflowError):
        return default


def safe_divide(numerator: Any, denominator: Any, default: float = 0.0) -> float:
    num = safe_float(numerator, default=default)
    den = safe_float(denominator, default=0.0)
    if den == 0:
        return default
    result = num / den
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def clamp_number(value: Any, minimum: float = 0.0, maximum: float = 100.0) -> float:
    number = safe_float(value, default=minimum)
    return max(minimum, min(maximum, number))


def safe_series(dataframe: pd.DataFrame, column: str, default: Any = np.nan) -> pd.Series:
    if dataframe is None or column not in dataframe.columns:
        length = 0 if dataframe is None else len(dataframe.index)
        return pd.Series([default] * length, index=None if dataframe is None else dataframe.index)
    return dataframe[column]


def numeric_series(dataframe: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    series = safe_series(dataframe, column, default=default)
    return pd.to_numeric(series, errors="coerce")


def datetime_series(dataframe: pd.DataFrame, column: str) -> pd.Series:
    series = safe_series(dataframe, column, default=pd.NaT)
    try:
        return pd.to_datetime(series, errors="coerce", format="mixed")
    except (TypeError, ValueError):
        return pd.to_datetime(series, errors="coerce")


def text_series(dataframe: pd.DataFrame, column: str, default: str = "Unknown") -> pd.Series:
    series = safe_series(dataframe, column, default=default)
    return series.map(lambda value: clean_string_value(value, default=default, max_length=1000)).astype("object")


def dataframe_null_safe(dataframe: pd.DataFrame) -> pd.DataFrame:
    safe = dataframe.copy()
    safe = safe.replace({np.nan: None, pd.NaT: None})
    safe = safe.where(pd.notnull(safe), None)
    return safe


def to_json_records(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    safe = dataframe_null_safe(dataframe)

    def convert(value: Any) -> Any:
        if isinstance(value, (pd.Timestamp, datetime, date)):
            return value.isoformat()
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            number = float(value)
            return None if math.isnan(number) or math.isinf(number) else number
        if isinstance(value, np.bool_):
            return bool(value)
        return value

    records = safe.to_dict(orient="records")
    return [{key: convert(value) for key, value in record.items()} for record in records]


def join_messages(messages: Iterable[str]) -> str:
    cleaned = [str(message).strip() for message in messages if str(message).strip()]
    return "; ".join(cleaned)


def append_text(existing: Any, additions: Iterable[str]) -> str:
    current = []
    if not is_missing_like(existing):
        current = [part.strip() for part in str(existing).split("; ") if part.strip()]
    for addition in additions:
        text = str(addition).strip()
        if text and text not in current:
            current.append(text)
    return "; ".join(current)


def build_bool_series(dataframe: pd.DataFrame, default: bool = False) -> pd.Series:
    length = 0 if dataframe is None else len(dataframe.index)
    return pd.Series([default] * length, index=None if dataframe is None else dataframe.index, dtype="bool")
