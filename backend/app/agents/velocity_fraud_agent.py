import pandas as pd

from app.agents.base import AgentResult, BaseAgent
from app.utils.safe_ops import datetime_series, numeric_series, text_series


class VelocityFraudAgent(BaseAgent):
    name = "Velocity Fraud Agent"
    slug = "velocity_fraud"

    def run(self, dataframe: pd.DataFrame) -> AgentResult:
        if dataframe is None:
            return self.fail("No dataframe was available for velocity fraud analysis.")
        if len(dataframe.index) == 0:
            self.initialize_output_columns(dataframe)
            return self.summarize(dataframe)

        self.initialize_output_columns(dataframe)

        times = datetime_series(dataframe, "transaction_time")
        if times.notna().sum() == 0:
            return self.summarize(dataframe, ["No valid transaction_time values; velocity checks were skipped."])

        working = pd.DataFrame(
            {
                "user_id": text_series(dataframe, "user_id", "Unknown User"),
                "merchant": text_series(dataframe, "merchant", "Unknown Merchant"),
                "transaction_time": times,
                "amount": numeric_series(dataframe, "amount"),
            },
            index=dataframe.index,
        ).dropna(subset=["transaction_time"])

        if working.empty:
            return self.summarize(dataframe, ["No rows with usable timestamps; velocity checks were skipped."])

        global_median_amount = float(working["amount"].dropna().median()) if working["amount"].notna().any() else 0.0
        ten_minutes = pd.Timedelta(minutes=10)
        one_hour = pd.Timedelta(hours=1)

        for _, group in working.sort_values(["user_id", "transaction_time"]).groupby("user_id", dropna=False, sort=False):
            group = group.sort_values("transaction_time")
            if group.empty:
                continue

            user_median = float(group["amount"].dropna().median()) if group["amount"].notna().any() else global_median_amount
            small_threshold = max(1.0, min(user_median, global_median_amount) if global_median_amount > 0 else user_median)
            large_threshold = max(user_median * 3.0, global_median_amount * 3.0, 1000.0)

            indices = list(group.index)
            time_values = list(group["transaction_time"])
            merchants = [str(value or "Unknown Merchant") for value in group["merchant"].tolist()]
            amounts = list(group["amount"])

            start_10 = 0
            start_60 = 0
            merchant_counts: dict[str, int] = {}
            prior_small_count = 0
            small_flags = [False] * len(indices)

            for position, idx in enumerate(indices):
                current_time = time_values[position]
                current_amount = amounts[position]

                while start_10 <= position and time_values[start_10] < current_time - ten_minutes:
                    start_10 += 1

                while start_60 <= position and time_values[start_60] < current_time - one_hour:
                    old_merchant = merchants[start_60]
                    merchant_counts[old_merchant] = merchant_counts.get(old_merchant, 0) - 1
                    if merchant_counts[old_merchant] <= 0:
                        merchant_counts.pop(old_merchant, None)
                    if small_flags[start_60]:
                        prior_small_count = max(0, prior_small_count - 1)
                    start_60 += 1

                merchant = merchants[position]
                merchant_counts[merchant] = merchant_counts.get(merchant, 0) + 1

                window_10_count = position - start_10 + 1
                window_60_count = position - start_60 + 1
                merchant_count_60 = len(merchant_counts)

                reasons: list[str] = []
                patterns: list[str] = []
                score = 0.0

                if window_10_count >= 3:
                    score += 18
                    reasons.append(f"Same user made {window_10_count} transactions within 10 minutes.")
                    patterns.append("10-Minute Velocity")

                if window_60_count >= 5:
                    score += 14
                    reasons.append(f"Same user made {window_60_count} transactions within 1 hour.")
                    patterns.append("Hourly Velocity")

                if merchant_count_60 >= 3 and window_60_count >= 3:
                    score += 10
                    reasons.append(f"Rapid payments to {merchant_count_60} different merchants within 1 hour.")
                    patterns.append("Rapid Merchant Switching")

                if pd.notna(current_amount) and prior_small_count >= 2 and float(current_amount) >= large_threshold:
                    score += 12
                    reasons.append("Multiple small transactions were followed by a large transaction.")
                    patterns.append("Small-to-Large Burst")

                if score > 0:
                    self.set_row_finding(dataframe, idx, score, reasons, " + ".join(patterns) or "Velocity Fraud")

                if pd.notna(current_amount) and float(current_amount) <= small_threshold:
                    small_flags[position] = True
                    prior_small_count += 1

        return self.summarize(dataframe)
