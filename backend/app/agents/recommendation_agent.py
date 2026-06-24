import pandas as pd

from app.agents.base import AgentResult, BaseAgent
from app.core.recommendations import action_for_risk_level


class RecommendationAgent(BaseAgent):
    name = "Recommendation Agent"

    def run(self, dataframe: pd.DataFrame) -> AgentResult:
        if dataframe is None:
            return self.fail("No dataframe was available for recommendation generation.")
        if len(dataframe.index) == 0:
            dataframe["recommended_action"] = []
            return AgentResult(
                name=self.name,
                status="completed_no_findings",
                message="No transaction rows were available for recommendation generation.",
                triggered_count=0,
                warning_count=0,
            )

        if "risk_level" not in dataframe.columns:
            dataframe["risk_level"] = "Low Risk"

        dataframe["recommended_action"] = dataframe["risk_level"].map(action_for_risk_level)
        review_count = int(dataframe["recommended_action"].isin(["Send for manual review", "Block payment and escalate to fraud team"]).sum())
        return AgentResult(
            name=self.name,
            status="completed",
            message=f"Generated recommended_action for {len(dataframe.index)} transaction(s); {review_count} need manual review or escalation.",
            triggered_count=review_count,
            warning_count=0,
        )
