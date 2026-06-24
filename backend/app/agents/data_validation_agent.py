import pandas as pd

from app.agents.base import AgentResult, BaseAgent
from app.core.validation import ValidationReport, validate_basic_dataframe


class DataValidationAgent(BaseAgent):
    name = "Data Validation Agent"

    def run(self, dataframe: pd.DataFrame, validation_report: ValidationReport | None = None) -> AgentResult:
        if dataframe is None:
            return self.fail("No dataframe was available for validation.")
        report = validation_report or validate_basic_dataframe(dataframe)
        if report.is_valid:
            return self.ok(f"Validated {report.cleaned_rows or report.row_count} usable transaction row(s).")
        return AgentResult(name=self.name, status="failed", message=report.message)
