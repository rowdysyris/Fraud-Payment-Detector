import pandas as pd

from app.agents.base import AgentResult, BaseAgent
from app.utils.safe_ops import datetime_series, numeric_series, text_series


class UserBehaviorAgent(BaseAgent):
    name = "User Behavior Agent"
    slug = "user_behavior"

    def run(self, dataframe: pd.DataFrame) -> AgentResult:
        if dataframe is None:
            return self.fail("No dataframe was available for user behavior analysis.")
        if len(dataframe.index) == 0:
            self.initialize_output_columns(dataframe)
            return self.summarize(dataframe)

        self.initialize_output_columns(dataframe)

        working = pd.DataFrame(
            {
                "user_id": text_series(dataframe, "user_id", "Unknown User"),
                "merchant": text_series(dataframe, "merchant", "Unknown Merchant"),
                "payment_method": text_series(dataframe, "payment_method", "Unknown Method"),
                "transaction_time": datetime_series(dataframe, "transaction_time"),
                "amount": numeric_series(dataframe, "amount"),
            },
            index=dataframe.index,
        )
        valid_amount = working["amount"].dropna()
        global_q75 = float(valid_amount.quantile(0.75)) if not valid_amount.empty else 0.0
        global_median = float(valid_amount.median()) if not valid_amount.empty else 0.0

        sort_columns = ["user_id", "transaction_time"] if working["transaction_time"].notna().any() else ["user_id"]
        working_sorted = working.sort_values(sort_columns)

        for user_id, group in working_sorted.groupby("user_id", dropna=False):
            amounts = group["amount"].dropna()
            user_median = float(amounts.median()) if not amounts.empty else global_median
            q1 = float(amounts.quantile(0.25)) if len(amounts) >= 4 else user_median
            q3 = float(amounts.quantile(0.75)) if len(amounts) >= 4 else user_median
            iqr = q3 - q1
            normal_upper = q3 + 1.5 * iqr if iqr > 0 else max(user_median * 3.0, global_q75 * 2.0, 1000.0)

            seen_merchants: set[str] = set()
            seen_methods: set[str] = set()
            for idx, row in group.iterrows():
                amount = row["amount"]
                merchant = str(row["merchant"] or "Unknown Merchant")
                method = str(row["payment_method"] or "Unknown Method")

                reasons: list[str] = []
                patterns: list[str] = []
                score = 0.0

                high_for_user = pd.notna(amount) and amount > max(user_median * 2.5, global_q75, 1000.0)
                if merchant not in seen_merchants and seen_merchants and high_for_user:
                    score += 7
                    reasons.append("First-time merchant for this user with a high amount.")
                    patterns.append("New Merchant High Amount")

                if method not in seen_methods and seen_methods:
                    score += 4
                    reasons.append("New payment method observed for this user.")
                    patterns.append("New Payment Method")

                if pd.notna(amount) and user_median > 0 and amount > max(user_median * 3.0, user_median + 1000.0):
                    score += 6
                    reasons.append("Sudden spending change compared with this user's median amount.")
                    patterns.append("Sudden Spending Change")

                if pd.notna(amount) and len(amounts) >= 3 and amount > normal_upper:
                    score += 5
                    reasons.append("Amount is outside this user's normal transaction range.")
                    patterns.append("Outside User Range")

                if score > 0:
                    self.set_row_finding(dataframe, idx, score, reasons, " + ".join(patterns) or "User Behavior Risk")

                seen_merchants.add(merchant)
                seen_methods.add(method)

        return self.summarize(dataframe)
