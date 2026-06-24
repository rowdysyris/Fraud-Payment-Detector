import pandas as pd

from app.agents.base import AgentResult, BaseAgent
from app.core.scoring import final_score_dataframe
from app.utils.constants import FINAL_OUTPUT_COLUMNS


class FinalRiskScoringAgent(BaseAgent):
    name = "Final Risk Scoring Agent"

    def run(self, dataframe: pd.DataFrame) -> AgentResult:
        if dataframe is None:
            return self.fail("No dataframe was available for final risk scoring.")
        if len(dataframe.index) == 0:
            scored = final_score_dataframe(dataframe)
            for column in FINAL_OUTPUT_COLUMNS:
                if column in scored.columns and column != "recommended_action":
                    dataframe[column] = scored[column]
            return AgentResult(
                name=self.name,
                status="completed_no_findings",
                message="No transaction rows were available for final risk scoring.",
                triggered_count=0,
                warning_count=0,
            )
        scored = final_score_dataframe(dataframe)
        for column in FINAL_OUTPUT_COLUMNS:
            if column in scored.columns and column != "recommended_action":
                dataframe[column] = scored[column]
        suspicious = int((dataframe["fraud_score"] > 30).sum()) if "fraud_score" in dataframe.columns else 0
        return AgentResult(
            name=self.name,
            status="completed",
            message=f"Assigned fraud_score and risk_level to {len(dataframe.index)} transaction(s); {suspicious} require monitoring or review.",
            triggered_count=suspicious,
            warning_count=0,
        )
