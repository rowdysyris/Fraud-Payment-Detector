import pandas as pd

from app.agents.base import AgentResult, BaseAgent
from app.core.cleaning import CleaningResult, clean_transactions_dataframe


class DataCleaningAgent(BaseAgent):
    name = "Data Cleaning Agent"

    def run(self, dataframe: pd.DataFrame, cleaning_result: CleaningResult | None = None) -> AgentResult:
        if dataframe is None:
            return self.fail("No dataframe was available for data cleaning.")
        result = cleaning_result or clean_transactions_dataframe(dataframe)
        row_count = len(result.dataframe.index)
        warning_count = len(result.warnings)
        if warning_count:
            return AgentResult(
                name=self.name,
                status="completed_with_warnings",
                message=f"Cleaned {row_count} row(s). Warnings: {'; '.join(result.warnings[:4])}",
            )
        return self.ok(f"Cleaned {row_count} row(s) without ingestion warnings.")
