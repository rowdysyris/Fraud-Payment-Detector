import pandas as pd

from app.agents.amount_anomaly_agent import AmountAnomalyAgent
from app.agents.duplicate_payment_agent import DuplicatePaymentAgent
from app.agents.final_risk_scoring_agent import FinalRiskScoringAgent
from app.agents.location_risk_agent import LocationRiskAgent
from app.agents.merchant_risk_agent import MerchantRiskAgent
from app.agents.recommendation_agent import RecommendationAgent
from app.agents.user_behavior_agent import UserBehaviorAgent
from app.agents.velocity_fraud_agent import VelocityFraudAgent
from app.core.cleaning import clean_transactions_dataframe
from app.utils.constants import FINAL_OUTPUT_COLUMNS


def _agent_dataframe() -> pd.DataFrame:
    return clean_transactions_dataframe(
        pd.DataFrame(
            {
                "transaction_id": ["T1", "T2", "T3", "T4", "T4", "T6"],
                "user_id": ["U1", "U1", "U1", "U1", "U1", "U2"],
                "transaction_time": [
                    "2026-01-01 10:00:00",
                    "2026-01-01 10:03:00",
                    "2026-01-01 10:06:00",
                    "2026-01-01 10:08:00",
                    "2026-01-01 10:08:00",
                    "2026-01-01 11:00:00",
                ],
                "amount": [100, 100, 100, "₹100000", "₹100000", 0],
                "merchant": ["Store A", "Store B", "Store C", "Store D", "Store D", "Store E"],
                "location": ["Bhopal", "Bhopal", "Delhi", "Mumbai", "Mumbai", "Unknown Location"],
                "payment_method": ["UPI", "UPI", "Card", "Card", "Card", "Wallet"],
                "status": ["success", "success", "success", "success", "success", "refund"],
                "currency": ["INR", "INR", "INR", "INR", "INR", "INR"],
            }
        )
    ).dataframe


def test_all_fraud_agents_run_without_crashing_and_add_columns() -> None:
    dataframe = _agent_dataframe()
    agents = [
        AmountAnomalyAgent(),
        VelocityFraudAgent(),
        UserBehaviorAgent(),
        MerchantRiskAgent(),
        LocationRiskAgent(),
        DuplicatePaymentAgent(),
        FinalRiskScoringAgent(),
        RecommendationAgent(),
    ]

    results = [agent.run(dataframe) for agent in agents]

    assert all(result.status.startswith("completed") for result in results)
    for column in FINAL_OUTPUT_COLUMNS:
        assert column in dataframe.columns
    assert dataframe["fraud_score"].between(0, 100).all()
    assert dataframe["risk_level"].isin({"Low Risk", "Medium Risk", "High Risk", "Critical Risk"}).all()
    assert int(dataframe["velocity_fraud_triggered"].sum()) >= 1
    assert int(dataframe["duplicate_payment_triggered"].sum()) >= 1
    assert int(dataframe["amount_anomaly_triggered"].sum()) >= 1
    assert dataframe["recommended_action"].notna().all()


def test_agents_do_not_crash_on_one_row_dataframe() -> None:
    dataframe = clean_transactions_dataframe(
        pd.DataFrame(
            {
                "user_id": ["U1"],
                "transaction_time": ["2026-01-01 10:00:00"],
                "amount": [100],
            }
        )
    ).dataframe

    for agent in [
        AmountAnomalyAgent(),
        VelocityFraudAgent(),
        UserBehaviorAgent(),
        MerchantRiskAgent(),
        LocationRiskAgent(),
        DuplicatePaymentAgent(),
        FinalRiskScoringAgent(),
        RecommendationAgent(),
    ]:
        result = agent.run(dataframe)
        assert result.status.startswith("completed")

    for column in FINAL_OUTPUT_COLUMNS:
        assert column in dataframe.columns
