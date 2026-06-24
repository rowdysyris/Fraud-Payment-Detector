from dataclasses import dataclass
from typing import Iterable, Protocol

import pandas as pd

from app.utils.constants import AGENT_SPECS
from app.utils.safe_ops import append_text, clamp_number


@dataclass
class AgentResult:
    name: str
    status: str
    message: str
    triggered_count: int = 0
    warning_count: int = 0


class Agent(Protocol):
    name: str

    def run(self, dataframe: pd.DataFrame) -> AgentResult:
        ...


class BaseAgent:
    name = "Base Agent"
    slug = "base"

    def ok(self, message: str, triggered_count: int = 0, warning_count: int = 0) -> AgentResult:
        status = "completed" if triggered_count else "completed_no_findings"
        if warning_count:
            status = "completed_with_warnings"
        return AgentResult(
            name=self.name,
            status=status,
            message=message,
            triggered_count=int(triggered_count),
            warning_count=int(warning_count),
        )

    def fail(self, message: str) -> AgentResult:
        return AgentResult(name=self.name, status="failed", message=message, triggered_count=0, warning_count=1)

    @property
    def spec(self) -> dict:
        return AGENT_SPECS[self.slug]

    @property
    def score_column(self) -> str:
        return str(self.spec["score_column"])

    @property
    def reason_column(self) -> str:
        return str(self.spec["reason_column"])

    @property
    def triggered_column(self) -> str:
        return str(self.spec["triggered_column"])

    @property
    def pattern_column(self) -> str:
        return str(self.spec["pattern_column"])

    @property
    def max_score(self) -> float:
        return float(self.spec["max_score"])

    def initialize_output_columns(self, dataframe: pd.DataFrame) -> None:
        dataframe[self.score_column] = 0.0
        dataframe[self.reason_column] = ""
        dataframe[self.triggered_column] = False
        dataframe[self.pattern_column] = "None"

    def set_row_finding(self, dataframe: pd.DataFrame, index: int, score: float, reasons: Iterable[str], pattern: str) -> None:
        safe_score = clamp_number(score, 0.0, self.max_score)
        current_score = clamp_number(dataframe.at[index, self.score_column], 0.0, self.max_score)
        dataframe.at[index, self.score_column] = clamp_number(current_score + safe_score, 0.0, self.max_score)
        dataframe.at[index, self.triggered_column] = bool(dataframe.at[index, self.score_column] > 0)
        dataframe.at[index, self.reason_column] = append_text(dataframe.at[index, self.reason_column], reasons)

        current_pattern = str(dataframe.at[index, self.pattern_column] or "None")
        if current_pattern in {"", "None", "nan"}:
            dataframe.at[index, self.pattern_column] = pattern
        elif pattern and pattern not in current_pattern.split(" + "):
            dataframe.at[index, self.pattern_column] = f"{current_pattern} + {pattern}"

    def summarize(self, dataframe: pd.DataFrame, warnings: list[str] | None = None) -> AgentResult:
        warnings = warnings or []
        if dataframe is None or self.triggered_column not in dataframe.columns:
            return self.ok("Agent completed without available transaction rows.", 0, len(warnings))
        triggered_count = int(dataframe[self.triggered_column].fillna(False).sum())
        message = f"Evaluated {len(dataframe.index)} transaction(s); flagged {triggered_count}."
        if warnings:
            message = message + " Warnings: " + "; ".join(warnings[:4])
        return self.ok(message, triggered_count=triggered_count, warning_count=len(warnings))
