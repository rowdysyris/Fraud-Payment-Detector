import pandas as pd

from app.agents.base import AgentResult, BaseAgent
from app.utils.safe_ops import datetime_series, numeric_series, text_series


class DuplicatePaymentAgent(BaseAgent):
    name = "Duplicate Payment Agent"
    slug = "duplicate_payment"

    def run(self, dataframe: pd.DataFrame) -> AgentResult:
        if dataframe is None:
            return self.fail("No dataframe was available for duplicate payment analysis.")
        if len(dataframe.index) == 0:
            self.initialize_output_columns(dataframe)
            return self.summarize(dataframe)

        self.initialize_output_columns(dataframe)

        transaction_ids = text_series(dataframe, "transaction_id", "")
        duplicate_transaction_id = transaction_ids.duplicated(keep=False) & transaction_ids.ne("")
        if "duplicate_transaction_id_flag" in dataframe.columns:
            duplicate_transaction_id = duplicate_transaction_id | dataframe["duplicate_transaction_id_flag"].fillna(False).astype(bool)

        if "duplicate_row_flag" in dataframe.columns:
            duplicate_full_row = dataframe["duplicate_row_flag"].fillna(False).astype(bool)
        else:
            base_columns = [column for column in ["transaction_id", "user_id", "transaction_time", "amount", "merchant", "location", "payment_method", "status", "currency"] if column in dataframe.columns]
            duplicate_full_row = dataframe[base_columns].duplicated(keep=False) if base_columns else pd.Series([False] * len(dataframe.index), index=dataframe.index)

        times = datetime_series(dataframe, "transaction_time")
        working = pd.DataFrame(
            {
                "user_id": text_series(dataframe, "user_id", "Unknown User"),
                "merchant": text_series(dataframe, "merchant", "Unknown Merchant"),
                "amount": numeric_series(dataframe, "amount").round(2),
                "transaction_time": times,
            },
            index=dataframe.index,
        )

        exact_payment_duplicate = working.duplicated(subset=["user_id", "merchant", "amount", "transaction_time"], keep=False)
        exact_payment_duplicate = exact_payment_duplicate & working["amount"].notna() & working["transaction_time"].notna()

        quick_same_amount = pd.Series([False] * len(dataframe.index), index=dataframe.index)
        dated = working.dropna(subset=["transaction_time", "amount"]).copy()
        if not dated.empty:
            ordered = dated.sort_values(["user_id", "amount", "transaction_time"])
            grouped = ordered.groupby(["user_id", "amount"], dropna=False)["transaction_time"]
            previous_gap = (ordered["transaction_time"] - grouped.shift()).abs().dt.total_seconds().map(lambda seconds: seconds / 60 if 60 != 0 else 0)
            next_gap = (grouped.shift(-1) - ordered["transaction_time"]).abs().dt.total_seconds().map(lambda seconds: seconds / 60 if 60 != 0 else 0)
            quick_ordered = previous_gap.le(10).fillna(False) | next_gap.le(10).fillna(False)
            quick_same_amount.loc[ordered.index] = quick_ordered.to_numpy(dtype=bool)

        self._apply_mask(dataframe, duplicate_transaction_id, 10, "Duplicate transaction_id detected.", "Duplicate Transaction ID")
        self._apply_mask(dataframe, duplicate_full_row, 8, "Duplicate full row detected.", "Duplicate Row")
        self._apply_mask(dataframe, exact_payment_duplicate, 10, "Same user, merchant, amount, and timestamp appeared more than once.", "Exact Payment Duplicate")
        self._apply_mask(dataframe, quick_same_amount, 7, "Same user repeated the same amount quickly.", "Rapid Same Amount Repeat")

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
