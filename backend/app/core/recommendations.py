import pandas as pd


def action_for_risk_level(risk_level: str) -> str:
    normalized = str(risk_level or "").strip().lower()
    if normalized == "critical risk":
        return "Block payment and escalate to fraud team"
    if normalized == "high risk":
        return "Send for manual review"
    if normalized == "medium risk":
        return "Monitor only"
    return "Allow transaction"


def add_recommended_actions(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe is None:
        return pd.DataFrame()
    recommended = dataframe.copy()
    if "risk_level" not in recommended.columns:
        recommended["risk_level"] = "Low Risk"
    recommended["recommended_action"] = recommended["risk_level"].map(action_for_risk_level)
    return recommended


def build_recommendations(dataframe: pd.DataFrame) -> list[str]:
    if dataframe is None or dataframe.empty or "risk_level" not in dataframe.columns:
        return ["No transaction rows were available for recommendation generation."]

    counts = dataframe["risk_level"].value_counts().to_dict()
    recommendations: list[str] = []
    critical = int(counts.get("Critical Risk", 0))
    high = int(counts.get("High Risk", 0))
    medium = int(counts.get("Medium Risk", 0))

    if critical:
        recommendations.append(f"Immediately block and escalate {critical} critical-risk transaction(s).")
    if high:
        recommendations.append(f"Send {high} high-risk transaction(s) to manual fraud review.")
    if medium:
        recommendations.append(f"Monitor {medium} medium-risk transaction(s) for follow-up activity.")
    if not recommendations:
        recommendations.append("No high-risk fraud patterns were detected; allow transactions with normal monitoring.")
    return recommendations


def build_starter_recommendations() -> list[str]:
    return [
        "Run the deterministic fraud agents on the cleaned transaction dataset.",
        "Review high-risk and critical transactions before settlement.",
        "Use the generated fraud reasons to prioritize manual review.",
    ]
