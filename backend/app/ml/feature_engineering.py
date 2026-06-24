from __future__ import annotations

import re

import numpy as np
import pandas as pd

TARGET_LEAKAGE_COLUMNS = {
    "fraud_score",
    "rule_fraud_score",
    "risk_level",
    "fraud_pattern",
    "fraud_reason",
    "triggered_agents",
    "confidence",
    "recommended_action",
    "review_status",
    "ml_fraud_probability",
}

FEATURE_COLUMNS = [
    "amount",
    "log_amount",
    "is_zero_amount",
    "is_negative_amount",
    "is_round_amount",
    "amount_zscore_global",
    "amount_zscore_vs_user",
    "user_transaction_count",
    "merchant_transaction_count",
    "location_transaction_count",
    "payment_method_transaction_count",
    "user_avg_amount",
    "merchant_avg_amount",
    "amount_vs_user_avg",
    "amount_vs_merchant_avg",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "txns_in_10min",
    "seconds_since_last_txn",
    "duplicate_transaction_id_flag",
    "duplicate_row_flag",
    "duplicate_count",
    "user_location_diversity",
    "missing_merchant_flag",
    "missing_location_flag",
    "missing_payment_method_flag",
]

_MISSING_TEXT = {"", "nan", "null", "none", "n/a", "na", "undefined"}
_REQUIRED_WITH_DEFAULTS = {
    "amount": 0.0,
    "user_id": "UNKNOWN",
    "transaction_time": pd.NaT,
    "merchant": "Unknown",
    "location": "Unknown",
    "payment_method": "Unknown",
    "transaction_id": None,
}


def _parse_amount(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float, np.integer, np.floating)):
        try:
            parsed = float(value)
            return parsed if np.isfinite(parsed) else 0.0
        except Exception:
            return 0.0
    text = str(value).strip()
    if text.lower() in _MISSING_TEXT:
        return 0.0
    normalized = text.replace(",", "")
    matches = re.findall(r"-?\d+(?:\.\d+)?", normalized)
    if not matches:
        return 0.0
    try:
        parsed = float(matches[0])
        return parsed if np.isfinite(parsed) else 0.0
    except Exception:
        return 0.0


def _ensure_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    safe = dataframe.copy()
    for column, default in _REQUIRED_WITH_DEFAULTS.items():
        if column not in safe.columns:
            if column == "transaction_id":
                safe[column] = [f"TXN{i}" for i in range(len(safe.index))]
            elif column == "transaction_time":
                safe[column] = pd.NaT
            else:
                safe[column] = default
    return safe


def _clean_amount_series(dataframe: pd.DataFrame, column: str = "amount") -> pd.Series:
    if dataframe is None or column not in dataframe.columns:
        return pd.Series([0.0] * (len(dataframe.index) if dataframe is not None else 0), index=dataframe.index if dataframe is not None else None, dtype="float64")
    return dataframe[column].apply(_parse_amount).astype(float)


def _clean_text_series(dataframe: pd.DataFrame, column: str, default: str = "Unknown") -> pd.Series:
    if dataframe is None or column not in dataframe.columns:
        return pd.Series([default] * (len(dataframe.index) if dataframe is not None else 0), index=dataframe.index if dataframe is not None else None, dtype="object")
    cleaned = dataframe[column].fillna(default).astype(str).str.strip()
    return cleaned.replace({"": default, "nan": default, "None": default, "none": default, "null": default, "N/A": default})


def _parse_transaction_time(series: pd.Series) -> pd.Series:
    if series is None:
        return pd.Series(dtype="datetime64[ns]")
    try:
        return pd.to_datetime(series, errors="coerce", format="mixed")
    except TypeError:
        return pd.to_datetime(series, errors="coerce")
    except Exception:
        return pd.Series([pd.NaT] * len(series.index), index=series.index, dtype="datetime64[ns]")


def _safe_std(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(numeric.index) < 2:
        return 1.0
    std_val = float(numeric.std())
    if pd.isna(std_val) or std_val == 0 or not np.isfinite(std_val):
        return 1.0
    return std_val


def _count_by(dataframe: pd.DataFrame, column: str) -> pd.Series:
    if dataframe is None or dataframe.empty or column not in dataframe.columns:
        return pd.Series([0.0] * (len(dataframe.index) if dataframe is not None else 0), index=dataframe.index if dataframe is not None else None, dtype="float64")
    key = _clean_text_series(dataframe, column)
    return pd.to_numeric(key.map(key.value_counts(dropna=False)), errors="coerce").fillna(0.0)


def _mean_by_amount(dataframe: pd.DataFrame, group_column: str, amount: pd.Series, fallback: float) -> pd.Series:
    if dataframe is None or dataframe.empty or group_column not in dataframe.columns:
        return pd.Series([fallback] * (len(dataframe.index) if dataframe is not None else 0), index=dataframe.index if dataframe is not None else None, dtype="float64")
    working = pd.DataFrame({"group": _clean_text_series(dataframe, group_column), "amount": amount}, index=dataframe.index)
    means = working.groupby("group", dropna=False)["amount"].transform("mean")
    return pd.to_numeric(means, errors="coerce").fillna(fallback)


def _std_by_amount(dataframe: pd.DataFrame, group_column: str, amount: pd.Series, fallback: float) -> pd.Series:
    if dataframe is None or dataframe.empty or group_column not in dataframe.columns:
        return pd.Series([fallback] * (len(dataframe.index) if dataframe is not None else 0), index=dataframe.index if dataframe is not None else None, dtype="float64")
    working = pd.DataFrame({"group": _clean_text_series(dataframe, group_column), "amount": amount}, index=dataframe.index)
    stds = working.groupby("group", dropna=False)["amount"].transform("std")
    stds = pd.to_numeric(stds, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(fallback)
    return stds.mask(stds <= 0, fallback).fillna(fallback)


def _ratio(numerator: pd.Series, denominator: pd.Series | float) -> pd.Series:
    denom = denominator if isinstance(denominator, pd.Series) else pd.Series([denominator] * len(numerator.index), index=numerator.index)
    denom = pd.to_numeric(denom, errors="coerce").replace(0, np.nan)
    values = pd.to_numeric(numerator, errors="coerce") / denom
    return values.replace([np.inf, -np.inf], 0.0).fillna(0.0)


def _duplicate_row_flag(dataframe: pd.DataFrame) -> pd.Series:
    if dataframe is None or dataframe.empty:
        return pd.Series([], index=dataframe.index if dataframe is not None else None, dtype="int64")
    safe = dataframe.copy()
    removable = [column for column in TARGET_LEAKAGE_COLUMNS if column in safe.columns]
    if removable:
        safe = safe.drop(columns=removable)
    try:
        return safe.astype(str).duplicated(keep=False).astype(int)
    except Exception:
        return pd.Series([0] * len(dataframe.index), index=dataframe.index, dtype="int64")


def _missing_flag(dataframe: pd.DataFrame, column: str) -> pd.Series:
    if dataframe is None or column not in dataframe.columns:
        return pd.Series([1] * (len(dataframe.index) if dataframe is not None else 0), index=dataframe.index if dataframe is not None else None, dtype="int64")
    series = dataframe[column]
    return (series.isna() | series.astype(str).str.strip().str.lower().isin(_MISSING_TEXT | {"unknown"})).astype(int)


def _rolling_user_velocity(dataframe: pd.DataFrame, timestamps: pd.Series) -> tuple[pd.Series, pd.Series]:
    counts = pd.Series([1.0] * len(dataframe.index), index=dataframe.index, dtype="float64")
    seconds_since_last = pd.Series([99999.0] * len(dataframe.index), index=dataframe.index, dtype="float64")
    if dataframe.empty or "user_id" not in dataframe.columns:
        return counts, seconds_since_last

    working = pd.DataFrame({"user_id": _clean_text_series(dataframe, "user_id"), "time": timestamps}, index=dataframe.index)
    for _, group in working.groupby("user_id", dropna=False):
        if len(group.index) < 2:
            continue
        valid = group[group["time"].notna()].sort_values("time")
        if len(valid.index) < 2:
            continue
        time_range = valid["time"].max() - valid["time"].min()
        if pd.isna(time_range) or time_range.total_seconds() == 0:
            continue
        ns_values = valid["time"].astype("int64").to_numpy()
        window_ns = int(pd.Timedelta(minutes=10).value)
        starts = np.searchsorted(ns_values, ns_values - window_ns, side="left")
        rolling_counts = np.arange(len(ns_values)) - starts + 1
        counts.loc[valid.index] = rolling_counts.astype(float)
        diffs = valid["time"].diff().dt.total_seconds().fillna(99999.0).clip(lower=0.0, upper=99999.0)
        seconds_since_last.loc[valid.index] = diffs.astype(float)
    return counts, seconds_since_last


def _duplicate_count(dataframe: pd.DataFrame, amount: pd.Series) -> pd.Series:
    if dataframe is None or dataframe.empty:
        return pd.Series([], index=dataframe.index if dataframe is not None else None, dtype="float64")
    user = _clean_text_series(dataframe, "user_id")
    merchant = _clean_text_series(dataframe, "merchant")
    amount_text = amount.round(2).astype(str)
    key = user + "|" + merchant + "|" + amount_text
    return pd.to_numeric(key.map(key.value_counts(dropna=False)), errors="coerce").fillna(1.0)


def _nunique_by(dataframe: pd.DataFrame, group_column: str, value_column: str) -> pd.Series:
    if dataframe is None or dataframe.empty or group_column not in dataframe.columns or value_column not in dataframe.columns:
        return pd.Series([1.0] * (len(dataframe.index) if dataframe is not None else 0), index=dataframe.index if dataframe is not None else None, dtype="float64")
    working = pd.DataFrame({"group": _clean_text_series(dataframe, group_column), "value": _clean_text_series(dataframe, value_column)}, index=dataframe.index)
    values = working.groupby("group", dropna=False)["value"].transform("nunique")
    return pd.to_numeric(values, errors="coerce").fillna(1.0)


def _clip_extreme_feature_values(features: pd.DataFrame) -> pd.DataFrame:
    clipped = features.copy()
    for column in clipped.columns:
        values = pd.to_numeric(clipped[column], errors="coerce").replace([np.inf, -np.inf], 0.0).fillna(0.0)
        if column not in {"amount", "log_amount"} and len(values.index) >= 3:
            q01 = float(values.quantile(0.01))
            q99 = float(values.quantile(0.99))
            if np.isfinite(q01) and np.isfinite(q99) and q99 > q01:
                values = values.clip(lower=q01, upper=q99)
        clipped[column] = values
    return clipped


def build_ml_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Build stable, numeric, leakage-safe ML features for fraud inference/training."""
    if df is None:
        empty = pd.DataFrame(columns=FEATURE_COLUMNS, dtype="float64")
        return empty, FEATURE_COLUMNS.copy()

    dataframe = _ensure_columns(df)
    features = pd.DataFrame(index=dataframe.index)

    amount = _clean_amount_series(dataframe, "amount").reindex(dataframe.index).fillna(0.0)
    global_amount_mean = float(amount.mean()) if len(amount.index) else 0.0
    if not np.isfinite(global_amount_mean):
        global_amount_mean = 0.0
    global_amount_std = _safe_std(amount)

    features["amount"] = amount.astype(float)
    features["log_amount"] = np.log1p(amount.clip(lower=0)).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    features["is_zero_amount"] = amount.eq(0).astype(int)
    features["is_negative_amount"] = amount.lt(0).astype(int)
    features["is_round_amount"] = ((amount.abs() > 0) & (amount.abs() % 1000 == 0)).astype(int)
    features["amount_zscore_global"] = ((amount - global_amount_mean) / global_amount_std).replace([np.inf, -np.inf], 0.0).fillna(0.0).clip(-10, 10)

    features["user_transaction_count"] = _count_by(dataframe, "user_id")
    features["merchant_transaction_count"] = _count_by(dataframe, "merchant")
    features["location_transaction_count"] = _count_by(dataframe, "location")
    features["payment_method_transaction_count"] = _count_by(dataframe, "payment_method")

    user_avg = _mean_by_amount(dataframe, "user_id", amount, global_amount_mean)
    merchant_avg = _mean_by_amount(dataframe, "merchant", amount, global_amount_mean)
    user_std = _std_by_amount(dataframe, "user_id", amount, global_amount_std)
    features["user_avg_amount"] = user_avg
    features["merchant_avg_amount"] = merchant_avg
    features["amount_vs_user_avg"] = _ratio(amount, user_avg)
    features["amount_vs_merchant_avg"] = _ratio(amount, merchant_avg)
    features["amount_zscore_vs_user"] = ((amount - user_avg) / user_std).replace([np.inf, -np.inf], 0.0).fillna(0.0).clip(-10, 10)

    timestamps = _parse_transaction_time(dataframe["transaction_time"])
    features["hour_of_day"] = timestamps.dt.hour.fillna(-1).astype(float)
    features["day_of_week"] = timestamps.dt.dayofweek.fillna(-1).astype(float)
    features["is_weekend"] = timestamps.dt.dayofweek.isin([5, 6]).fillna(False).astype(int)

    txns_in_10min, seconds_since_last = _rolling_user_velocity(dataframe, timestamps)
    features["txns_in_10min"] = txns_in_10min
    features["seconds_since_last_txn"] = seconds_since_last

    transaction_ids = _clean_text_series(dataframe, "transaction_id")
    transaction_id_counts = transaction_ids.map(transaction_ids.value_counts(dropna=False)).fillna(1)
    features["duplicate_transaction_id_flag"] = pd.to_numeric(transaction_id_counts, errors="coerce").fillna(1).gt(1).astype(int)
    features["duplicate_row_flag"] = _duplicate_row_flag(dataframe).reindex(dataframe.index).fillna(0).astype(int)
    features["duplicate_count"] = _duplicate_count(dataframe, amount).reindex(dataframe.index).fillna(1.0)
    features["user_location_diversity"] = _nunique_by(dataframe, "user_id", "location")
    features["missing_merchant_flag"] = _missing_flag(dataframe, "merchant")
    features["missing_location_flag"] = _missing_flag(dataframe, "location")
    features["missing_payment_method_flag"] = _missing_flag(dataframe, "payment_method")

    for column in FEATURE_COLUMNS:
        if column not in features.columns:
            features[column] = 0.0

    features = features[FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    features = features.replace([np.inf, -np.inf], 0.0).fillna(0.0).astype(float)
    features = _clip_extreme_feature_values(features)
    return features, FEATURE_COLUMNS.copy()
