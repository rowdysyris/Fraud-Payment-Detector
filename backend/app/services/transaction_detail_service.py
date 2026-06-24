from __future__ import annotations

from typing import Any

import pandas as pd

from app.utils.constants import AGENT_SPECS
from app.utils.safe_ops import safe_float, to_json_records

DISCLAIMER = "This system flags suspicious transactions for review. It does not prove legal fraud."

AGENT_ORDER = [
    "amount_anomaly",
    "velocity_fraud",
    "user_behavior",
    "merchant_risk",
    "location_risk",
    "duplicate_payment",
]


def _safe_text(value: Any, default: str = "Unknown") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text if text else default


def _row_to_dict(row: pd.Series) -> dict[str, Any]:
    record = to_json_records(pd.DataFrame([row.to_dict()]))
    return record[0] if record else {}


def _agent_in_triggered(row: pd.Series, agent_display_name: str, keywords: list[str] | None = None) -> bool:
    triggered = _safe_text(row.get("triggered_agents", ""), default="").lower()
    if agent_display_name.lower() in triggered:
        return True
    return any(keyword.lower() in triggered for keyword in (keywords or []))


def build_agent_breakdown(row: pd.Series) -> list[dict[str, Any]]:
    breakdown: list[dict[str, Any]] = []
    for slug in AGENT_ORDER:
        spec = AGENT_SPECS[slug]
        score = safe_float(row.get(spec["score_column"], 0.0), default=0.0)
        reason = _safe_text(row.get(spec["reason_column"], ""), default="")
        fired = bool(row.get(spec["triggered_column"], False)) or score > 0 or _agent_in_triggered(row, spec["display_name"])
        breakdown.append(
            {
                "agent_name": spec["display_name"],
                "fired": bool(fired),
                "score_contribution": round(float(score), 2),
                "reason": reason if fired and reason else "No signal detected.",
            }
        )

    ml_probability = safe_float(row.get("ml_fraud_probability", 0.0), default=0.0)
    ml_contribution = round(ml_probability * 0.30, 2)
    ml_fired = ml_probability >= 70 or _agent_in_triggered(row, "ML Fraud Model", ["ml", "model"])
    ml_reason = (
        f"ML model predicted {ml_probability:.1f}/100 fraud probability."
        if ml_fired or ml_probability > 0
        else "No ML anomaly signal detected."
    )
    breakdown.append(
        {
            "agent_name": "ML Fraud Model",
            "fired": bool(ml_fired),
            "score_contribution": ml_contribution,
            "reason": ml_reason,
        }
    )
    return breakdown


def build_user_timeline(dataframe: pd.DataFrame, selected_row: pd.Series, max_rows: int = 20) -> list[dict[str, Any]]:
    if dataframe is None or dataframe.empty:
        return []
    if "user_id" not in dataframe.columns:
        return []

    selected_user = _safe_text(selected_row.get("user_id", ""), default="")
    if not selected_user:
        return []

    working = dataframe.copy()
    working["_original_order"] = range(len(working.index))
    user_rows = working.loc[working["user_id"].astype(str).eq(str(selected_user))].copy()
    if user_rows.empty:
        return []

    selected_id = _safe_text(selected_row.get("transaction_id", ""), default="")
    selected_time = pd.to_datetime(selected_row.get("transaction_time"), errors="coerce")
    user_rows["_parsed_time"] = pd.to_datetime(user_rows.get("transaction_time", pd.NaT), errors="coerce")

    if pd.notna(selected_time) and user_rows["_parsed_time"].notna().any():
        window_start = selected_time - pd.Timedelta(hours=24)
        window_end = selected_time + pd.Timedelta(hours=24)
        window_rows = user_rows.loc[user_rows["_parsed_time"].between(window_start, window_end, inclusive="both")].copy()
        if not window_rows.empty:
            user_rows = window_rows
        user_rows = user_rows.sort_values(["_parsed_time", "_original_order"], na_position="last")
    else:
        user_rows = user_rows.sort_values("_original_order")

    if len(user_rows.index) > max_rows:
        if selected_id and "transaction_id" in user_rows.columns:
            matching_positions = list(user_rows.index[user_rows["transaction_id"].astype(str).eq(str(selected_id))])
            if matching_positions:
                selected_position = user_rows.index.get_loc(matching_positions[0])
                start = max(0, selected_position - max_rows // 2)
                end = min(len(user_rows.index), start + max_rows)
                start = max(0, end - max_rows)
                user_rows = user_rows.iloc[start:end].copy()
            else:
                user_rows = user_rows.head(max_rows).copy()
        else:
            user_rows = user_rows.head(max_rows).copy()

    timeline_columns = [
        "transaction_id",
        "transaction_time",
        "amount",
        "merchant",
        "location",
        "payment_method",
        "fraud_score",
        "risk_level",
    ]
    for column in timeline_columns:
        if column not in user_rows.columns:
            user_rows[column] = None
    user_rows["is_selected"] = user_rows["transaction_id"].astype(str).eq(str(selected_id)) if selected_id else False
    return to_json_records(user_rows[timeline_columns + ["is_selected"]])


def build_explanation(row: pd.Series, agent_breakdown: list[dict[str, Any]]) -> dict[str, Any]:
    transaction_id = _safe_text(row.get("transaction_id"), "Unknown Transaction")
    risk_level = _safe_text(row.get("risk_level"), "Low Risk")
    fraud_score = safe_float(row.get("fraud_score"), 0.0)
    fraud_pattern = _safe_text(row.get("fraud_pattern"), "No suspicious pattern detected")
    fraud_reason = _safe_text(row.get("fraud_reason"), "No fraud signals detected")
    recommended_action = _safe_text(row.get("recommended_action"), "Allow transaction")

    fired_agents = [item for item in agent_breakdown if item.get("fired")]
    evidence = []
    for item in fired_agents:
        reason = _safe_text(item.get("reason"), default="")
        if reason and reason != "No signal detected.":
            evidence.append(f"{item.get('agent_name')}: {reason}")
    if not evidence:
        evidence.append(fraud_reason)

    agent_names = ", ".join(str(item.get("agent_name")) for item in fired_agents) if fired_agents else "baseline fraud scoring"
    summary = f"Transaction {transaction_id} is rated {risk_level} with a fraud score of {fraud_score:.0f}/100."
    why_flagged = (
        f"The transaction was flagged because {agent_names} produced risk signals. Pattern: {fraud_pattern}. {fraud_reason}"
        if fired_agents
        else "No major fraud agent fired. The transaction remains low risk based on the available data."
    )

    return {
        "summary": summary,
        "why_flagged": why_flagged,
        "risk_evidence": evidence,
        "recommended_next_step": recommended_action,
        "disclaimer": DISCLAIMER,
    }


def build_transaction_detail_payload(job_id: str, dataframe: pd.DataFrame, transaction_id: str) -> dict[str, Any]:
    if dataframe is None or dataframe.empty or "transaction_id" not in dataframe.columns:
        raise LookupError("Transaction not found for this job.")
    mask = dataframe["transaction_id"].astype(str).eq(str(transaction_id))
    if not bool(mask.any()):
        raise LookupError("Transaction not found for this job.")
    selected_row = dataframe.loc[mask].iloc[0]
    transaction = _row_to_dict(selected_row)
    agent_breakdown = build_agent_breakdown(selected_row)
    return {
        "job_id": job_id,
        "transaction": transaction,
        "user_timeline": build_user_timeline(dataframe, selected_row),
        "agent_breakdown": agent_breakdown,
        "explanation": build_explanation(selected_row, agent_breakdown),
    }
