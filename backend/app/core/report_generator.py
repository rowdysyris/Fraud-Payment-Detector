from pathlib import Path
from typing import Any, Dict, Iterable

import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.config import settings
from app.core.recommendations import build_recommendations
from app.schemas import AnalysisSummary
from app.utils.safe_ops import safe_float, safe_int


def _safe_pdf_text(value: Any, max_length: int | None = None) -> str:
    text = str(value if value is not None else "")
    text = text.replace("₹", "Rs. ")
    text = text.encode("latin-1", errors="replace").decode("latin-1")
    text = " ".join(text.split())
    if max_length is not None and len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


def _risk_mask(dataframe: pd.DataFrame) -> pd.Series:
    if dataframe is None or dataframe.empty or "risk_level" not in dataframe.columns:
        index = dataframe.index if dataframe is not None else None
        return pd.Series([], index=index, dtype="bool")
    return dataframe["risk_level"].isin(["Medium Risk", "High Risk", "Critical Risk"])


def write_fraud_reports(
    job_dir: Path,
    scored_dataframe: pd.DataFrame,
    summary: AnalysisSummary,
    report_context: Dict[str, Any] | None = None,
) -> Dict[str, Path]:
    job_dir.mkdir(parents=True, exist_ok=True)

    all_scored_path = job_dir / settings.all_scored_filename
    fraud_transactions_path = job_dir / settings.fraud_transactions_filename
    summary_report_path = job_dir / settings.summary_report_filename

    safe_dataframe = scored_dataframe.copy() if scored_dataframe is not None else pd.DataFrame()
    safe_dataframe.to_csv(all_scored_path, index=False)

    fraud_rows = safe_dataframe.loc[_risk_mask(safe_dataframe)].copy() if not safe_dataframe.empty else pd.DataFrame(columns=safe_dataframe.columns)
    fraud_rows.to_csv(fraud_transactions_path, index=False)

    _write_pdf(summary_report_path, summary, safe_dataframe, report_context or {})

    return {
        "all_scored": all_scored_path,
        "fraud_transactions": fraud_transactions_path,
        "summary_report": summary_report_path,
    }


def write_starter_reports(job_dir: Path, scored_dataframe: pd.DataFrame, summary: AnalysisSummary) -> Dict[str, Path]:
    return write_fraud_reports(job_dir, scored_dataframe, summary)


def _draw_wrapped_text(pdf: canvas.Canvas, text: str, x: int, y: int, max_width_chars: int = 95, line_height: int = 14) -> int:
    clean = _safe_pdf_text(text)
    if not clean:
        pdf.drawString(x, y, "")
        return y - line_height

    words = clean.split()
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if len(candidate) > max_width_chars and line:
            pdf.drawString(x, y, line)
            y -= line_height
            line = word
        else:
            line = candidate
    if line:
        pdf.drawString(x, y, line)
        y -= line_height
    return y


def _ensure_page_space(pdf: canvas.Canvas, y: int, min_y: int = 72) -> int:
    if y < min_y:
        pdf.showPage()
        pdf.setFont("Helvetica", 10)
        return letter[1] - 72
    return y


def _section(pdf: canvas.Canvas, title: str, y: int) -> int:
    y = _ensure_page_space(pdf, y, 110)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(72, y, _safe_pdf_text(title))
    pdf.setFont("Helvetica", 10)
    return y - 18


def _bullets(pdf: canvas.Canvas, items: Iterable[Any], y: int, empty_text: str = "No data available.") -> int:
    rendered = False
    for item in items:
        y = _ensure_page_space(pdf, y)
        y = _draw_wrapped_text(pdf, f"- {item}", 84, y, max_width_chars=90)
        rendered = True
    if not rendered:
        y = _ensure_page_space(pdf, y)
        y = _draw_wrapped_text(pdf, f"- {empty_text}", 84, y, max_width_chars=90)
    return y - 6


def _dict_lines(mapping: Dict[str, Any]) -> list[str]:
    return [f"{key}: {value}" for key, value in mapping.items()]


def _top_entity_lines(rows: list[dict], entity_key: str) -> list[str]:
    lines: list[str] = []
    for row in rows[:10]:
        entity = row.get(entity_key, "Unknown")
        count = safe_int(row.get("transaction_count", 0))
        avg_score = safe_float(row.get("average_fraud_score", 0.0))
        max_score = safe_float(row.get("max_fraud_score", 0.0))
        amount_at_risk = safe_float(row.get("amount_at_risk", 0.0))
        lines.append(
            f"{entity} | transactions: {count} | avg score: {avg_score:.1f} | max score: {max_score:.0f} | amount at risk: {amount_at_risk:.2f}"
        )
    return lines


def _agent_lines(agent_summary: Dict[str, dict]) -> list[str]:
    lines: list[str] = []
    for name, data in agent_summary.items():
        triggered = safe_int(data.get("triggered_count", 0))
        status = data.get("status", "unknown")
        message = data.get("message", "")
        lines.append(f"{name} | status: {status} | triggered rows: {triggered} | {message}")
    return lines


def _pattern_lines(dataframe: pd.DataFrame) -> list[str]:
    if dataframe is None or dataframe.empty or "fraud_pattern" not in dataframe.columns:
        return []
    suspicious = dataframe.loc[_risk_mask(dataframe)].copy()
    if suspicious.empty:
        suspicious = dataframe.copy()
    counts: dict[str, int] = {}
    for value in suspicious["fraud_pattern"].dropna().astype(str):
        for part in value.split(" + "):
            clean = part.strip()
            if clean and clean.lower() not in {"none", "no suspicious pattern detected"}:
                counts[clean] = counts.get(clean, 0) + 1
    return [f"{pattern}: {count}" for pattern, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:10]]


def _write_pdf(path: Path, summary: AnalysisSummary, dataframe: pd.DataFrame, context: Dict[str, Any]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=letter)
    _, height = letter
    y = height - 72

    job_id = context.get("job_id", "Unknown")
    risk_distribution = context.get("risk_distribution") or summary.risk_distribution or {}
    top_risky_users = context.get("top_risky_users") or []
    top_risky_merchants = context.get("top_risky_merchants") or []
    agent_summary = context.get("agent_summary") or {}
    recommendations = context.get("recommended_next_actions") or build_recommendations(dataframe)

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(72, y, "SentinelPay AI - Fraud Summary Report")
    y -= 24
    pdf.setFont("Helvetica", 10)
    y = _draw_wrapped_text(pdf, "Agentic Fraud Payment Investigator | Manager Review Report", 72, y)
    y -= 10

    y = _section(pdf, "Executive Summary", y)
    metrics = [
        f"Job ID: {job_id}",
        f"Total transactions: {summary.total_transactions}",
        f"Valid transactions: {summary.valid_transactions or summary.validated_transactions}",
        f"Suspicious transactions: {summary.suspicious_transactions}",
        f"High-risk transactions: {summary.high_risk_transactions}",
        f"Critical-risk transactions: {summary.critical_risk_transactions or summary.critical_fraud_transactions}",
        f"Total fraud amount at risk: {summary.total_amount_at_risk:.2f}",
    ]
    y = _bullets(pdf, metrics, y)

    y = _section(pdf, "Risk Distribution", y)
    y = _bullets(pdf, _dict_lines(risk_distribution), y)

    y = _section(pdf, "Top Risky Users", y)
    y = _bullets(pdf, _top_entity_lines(top_risky_users, "user_id"), y)

    y = _section(pdf, "Top Risky Merchants", y)
    y = _bullets(pdf, _top_entity_lines(top_risky_merchants, "merchant"), y)

    y = _section(pdf, "Most Common Fraud Patterns", y)
    y = _bullets(pdf, _pattern_lines(dataframe), y)

    y = _section(pdf, "Agent Findings Summary", y)
    y = _bullets(pdf, _agent_lines(agent_summary), y)

    y = _section(pdf, "Recommended Next Actions", y)
    y = _bullets(pdf, recommendations, y)

    y = _section(pdf, "Disclaimer", y)
    y = _draw_wrapped_text(
        pdf,
        "This system flags suspicious transactions for review. It does not prove legal fraud.",
        84,
        y,
        max_width_chars=90,
    )

    pdf.setFont("Helvetica", 8)
    pdf.drawString(72, 40, "Generated by SentinelPay AI")
    pdf.showPage()
    pdf.save()
