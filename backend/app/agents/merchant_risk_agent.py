import pandas as pd

from app.agents.base import AgentResult, BaseAgent
from app.utils.safe_ops import build_bool_series, numeric_series, text_series


class MerchantRiskAgent(BaseAgent):
    name = "Merchant Risk Agent"
    slug = "merchant_risk"

    def run(self, dataframe: pd.DataFrame) -> AgentResult:
        if dataframe is None:
            return self.fail("No dataframe was available for merchant risk analysis.")
        if len(dataframe.index) == 0:
            self.initialize_output_columns(dataframe)
            return self.summarize(dataframe)

        self.initialize_output_columns(dataframe)

        working = pd.DataFrame(
            {
                "merchant": text_series(dataframe, "merchant", "Unknown Merchant"),
                "user_id": text_series(dataframe, "user_id", "Unknown User"),
                "amount": numeric_series(dataframe, "amount"),
            },
            index=dataframe.index,
        )

        merchant_counts = working.groupby("merchant", dropna=False).size()
        user_counts = working.groupby("merchant", dropna=False)["user_id"].nunique(dropna=True)
        avg_amounts = working.groupby("merchant", dropna=False)["amount"].mean()

        count_q75 = float(merchant_counts.quantile(0.75)) if len(merchant_counts) else 0.0
        count_iqr = float(merchant_counts.quantile(0.75) - merchant_counts.quantile(0.25)) if len(merchant_counts) >= 4 else 0.0
        high_volume_threshold = max(5.0, count_q75 + 1.5 * count_iqr)

        user_q75 = float(user_counts.quantile(0.75)) if len(user_counts) else 0.0
        high_user_threshold = max(3.0, user_q75 + 1.0)

        valid_avg = avg_amounts.dropna()
        avg_q75 = float(valid_avg.quantile(0.75)) if not valid_avg.empty else 0.0
        avg_iqr = float(valid_avg.quantile(0.75) - valid_avg.quantile(0.25)) if len(valid_avg) >= 4 else 0.0
        high_avg_threshold = max(1000.0, avg_q75 + 1.5 * avg_iqr)

        previous_triggered = build_bool_series(dataframe, False)
        for column in ["amount_anomaly_triggered", "velocity_fraud_triggered", "user_behavior_triggered"]:
            if column in dataframe.columns:
                previous_triggered = previous_triggered | dataframe[column].fillna(False).astype(bool)
        suspicious_by_merchant = previous_triggered.groupby(working["merchant"], dropna=False).sum()

        row_merchant_count = working["merchant"].map(merchant_counts).fillna(0).astype(float)
        row_unique_users = working["merchant"].map(user_counts).fillna(0).astype(float)
        row_avg_amount = working["merchant"].map(avg_amounts).fillna(0.0).astype(float)
        row_suspicious_count = working["merchant"].map(suspicious_by_merchant).fillna(0).astype(float)

        self._apply_mask(
            dataframe,
            (row_merchant_count >= high_volume_threshold) & (row_merchant_count >= 5),
            5,
            "Merchant received unusually high transaction volume.",
            "High Merchant Volume",
        )
        self._apply_mask(
            dataframe,
            (row_unique_users >= high_user_threshold) & (row_unique_users >= 3),
            4,
            "Merchant received payments from many different users.",
            "Many Users To Merchant",
        )
        self._apply_mask(
            dataframe,
            (row_avg_amount >= high_avg_threshold) & (row_avg_amount > 0),
            5,
            "Merchant has an unusually high average transaction amount.",
            "High Merchant Average",
        )
        self._apply_mask(
            dataframe,
            (row_suspicious_count >= row_merchant_count.mul(0.4).clip(lower=2)) & (row_merchant_count >= 2),
            6,
            "Merchant is involved in multiple transactions already flagged by other agents.",
            "Merchant Linked To Suspicion",
        )

        return self.summarize(dataframe)

    def _apply_mask(self, dataframe: pd.DataFrame, mask: pd.Series, score: float, reason: str, pattern: str) -> None:
        mask = mask.reindex(dataframe.index, fill_value=False).fillna(False).astype(bool)
        if not bool(mask.any()):
            return
        dataframe.loc[mask, self.score_column] = (pd.to_numeric(dataframe.loc[mask, self.score_column], errors="coerce").fillna(0.0) + score).clip(0, self.max_score)
        dataframe.loc[mask, self.triggered_column] = True

        current_reasons = dataframe.loc[mask, self.reason_column].fillna("").astype(str)
        empty_reason = current_reasons.str.strip().isin(["", "None", "nan"])
        dataframe.loc[mask, self.reason_column] = current_reasons.where(empty_reason, current_reasons + "; " + reason).where(~empty_reason, reason)

        current_patterns = dataframe.loc[mask, self.pattern_column].fillna("None").astype(str)
        empty_pattern = current_patterns.str.strip().isin(["", "None", "nan"])
        dataframe.loc[mask, self.pattern_column] = current_patterns.where(empty_pattern, current_patterns + " + " + pattern).where(~empty_pattern, pattern)
