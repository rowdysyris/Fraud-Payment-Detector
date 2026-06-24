import numpy as np
import pandas as pd

from app.agents.base import AgentResult, BaseAgent
from app.utils.safe_ops import numeric_series, safe_divide


class AmountAnomalyAgent(BaseAgent):
    name = "Amount Anomaly Agent"
    slug = "amount_anomaly"

    def run(self, dataframe: pd.DataFrame) -> AgentResult:
        if dataframe is None:
            return self.fail("No dataframe was available for amount anomaly analysis.")
        if len(dataframe.index) == 0:
            self.initialize_output_columns(dataframe)
            return self.summarize(dataframe)

        self.initialize_output_columns(dataframe)

        amount = numeric_series(dataframe, "amount")
        valid_amount = amount.dropna()
        if valid_amount.empty:
            return self.summarize(dataframe, ["Amount column has no numeric values; amount anomaly checks were skipped."])

        global_mean = float(valid_amount.mean())
        global_median = float(valid_amount.median())
        global_std = float(valid_amount.std(ddof=0)) if len(valid_amount) > 1 else 0.0
        q1 = float(valid_amount.quantile(0.25))
        q3 = float(valid_amount.quantile(0.75))
        iqr = q3 - q1
        iqr_upper = q3 + 1.5 * iqr if iqr > 0 else max(q3 * 2.5, q3 + 1000)
        extreme_upper = max(100000.0, q3 + 3.0 * iqr if iqr > 0 else global_mean * 5.0, global_median * 10.0)
        repeated_counts = amount.round(2).value_counts(dropna=True)

        user_medians = amount.groupby(dataframe.get("user_id", pd.Series(index=dataframe.index, dtype="object"))).transform("median") if "user_id" in dataframe.columns else pd.Series([np.nan] * len(dataframe.index), index=dataframe.index)
        user_means = amount.groupby(dataframe.get("user_id", pd.Series(index=dataframe.index, dtype="object"))).transform("mean") if "user_id" in dataframe.columns else pd.Series([np.nan] * len(dataframe.index), index=dataframe.index)

        for idx in dataframe.index:
            value = amount.at[idx]
            if pd.isna(value):
                continue

            reasons: list[str] = []
            score = 0.0
            pattern_parts: list[str] = []
            absolute_value = abs(float(value))

            if value == 0:
                score += 8
                reasons.append("Zero amount transaction detected.")
                pattern_parts.append("Zero Amount")

            status_text = str(dataframe.at[idx, "status"]).lower() if "status" in dataframe.columns else ""
            if value < 0 or any(token in status_text for token in ["refund", "reversal", "chargeback", "returned"]):
                score += 8
                reasons.append("Negative or refund-like amount detected.")
                pattern_parts.append("Refund/Negative Amount")

            if len(valid_amount) >= 2 and value > max(global_mean * 3.0, global_mean + 3.0 * global_std, global_median * 4.0, 1000.0):
                score += 10
                reasons.append("Amount is much higher than the dataset average.")
                pattern_parts.append("Global Amount Spike")

            user_mean = user_means.at[idx]
            user_median = user_medians.at[idx]
            if not pd.isna(user_mean) and user_mean > 0 and value > max(user_mean * 3.0, user_median * 4.0, user_mean + 1000.0):
                score += 7
                reasons.append("Amount is much higher than this user's normal average.")
                pattern_parts.append("User Amount Spike")

            if len(valid_amount) >= 4 and value > iqr_upper:
                score += 8
                reasons.append("Amount is an IQR outlier.")
                pattern_parts.append("IQR Outlier")

            if value > extreme_upper:
                score += 18
                reasons.append("Extreme transaction amount detected.")
                pattern_parts.append("Extreme Amount")

            if absolute_value >= 1000 and absolute_value % 1000 == 0:
                score += 4
                reasons.append("Large round-number amount detected.")
                pattern_parts.append("Round Amount")
            elif absolute_value >= 500 and absolute_value % 500 == 0:
                score += 2
                reasons.append("Round-number amount detected.")
                pattern_parts.append("Round Amount")

            repeated_count = int(repeated_counts.get(round(float(value), 2), 0))
            repeated_ratio = safe_divide(repeated_count, len(dataframe.index), default=0.0)
            if repeated_count >= 3 and repeated_ratio <= 0.6:
                score += 4
                reasons.append("Same amount is repeated across multiple transactions.")
                pattern_parts.append("Repeated Amount")

            if score > 0:
                self.set_row_finding(dataframe, idx, score, reasons, " + ".join(pattern_parts) or "Amount Anomaly")

        return self.summarize(dataframe)
