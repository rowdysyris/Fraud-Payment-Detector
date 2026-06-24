import pandas as pd

from app.agents.base import AgentResult, BaseAgent
from app.utils.safe_ops import datetime_series, numeric_series, text_series


_UNKNOWN_LOCATIONS = {"unknown location", "unknown", "missing", "none", "nan", ""}


class LocationRiskAgent(BaseAgent):
    name = "Location Risk Agent"
    slug = "location_risk"

    def run(self, dataframe: pd.DataFrame) -> AgentResult:
        if dataframe is None:
            return self.fail("No dataframe was available for location risk analysis.")
        if len(dataframe.index) == 0:
            self.initialize_output_columns(dataframe)
            return self.summarize(dataframe)

        self.initialize_output_columns(dataframe)

        working = pd.DataFrame(
            {
                "user_id": text_series(dataframe, "user_id", "Unknown User"),
                "location": text_series(dataframe, "location", "Unknown Location"),
                "transaction_time": datetime_series(dataframe, "transaction_time"),
                "amount": numeric_series(dataframe, "amount"),
            },
            index=dataframe.index,
        )
        valid_amount = working["amount"].dropna()
        global_q75 = float(valid_amount.quantile(0.75)) if not valid_amount.empty else 0.0
        sort_columns = ["user_id", "transaction_time"] if working["transaction_time"].notna().any() else ["user_id"]
        one_hour = pd.Timedelta(hours=1)

        for _, group in working.sort_values(sort_columns).groupby("user_id", dropna=False, sort=False):
            group = group.sort_values("transaction_time") if group["transaction_time"].notna().any() else group
            indices = list(group.index)
            time_values = list(group["transaction_time"])
            locations = [str(value or "Unknown Location") for value in group["location"].tolist()]
            amounts = list(group["amount"])

            seen_locations: set[str] = set()
            previous_valid_time = None
            previous_valid_location: str | None = None
            start_60 = 0
            location_counts: dict[str, int] = {}

            for position, idx in enumerate(indices):
                location = locations[position]
                normalized_location = location.strip().lower()
                is_unknown_location = normalized_location in _UNKNOWN_LOCATIONS
                current_time = time_values[position]
                amount = amounts[position]

                if pd.notna(current_time):
                    while start_60 <= position and pd.notna(time_values[start_60]) and time_values[start_60] < current_time - one_hour:
                        old_location = locations[start_60]
                        if old_location.strip().lower() not in _UNKNOWN_LOCATIONS:
                            location_counts[old_location] = location_counts.get(old_location, 0) - 1
                            if location_counts[old_location] <= 0:
                                location_counts.pop(old_location, None)
                        start_60 += 1
                    if not is_unknown_location:
                        location_counts[location] = location_counts.get(location, 0) + 1

                reasons: list[str] = []
                patterns: list[str] = []
                score = 0.0

                if not is_unknown_location and location not in seen_locations and seen_locations:
                    score += 4
                    reasons.append("New location observed for this user.")
                    patterns.append("New User Location")
                    if pd.notna(amount) and float(amount) >= max(global_q75, 1000.0):
                        score += 3
                        reasons.append("New user location also has a high transaction amount.")
                        patterns.append("High Amount New Location")

                if pd.notna(current_time):
                    if len(location_counts) >= 2:
                        score += 5
                        reasons.append("Multiple locations were used by the same user within 1 hour.")
                        patterns.append("Multi-Location Burst")

                    if previous_valid_time is not None and previous_valid_location is not None:
                        if previous_valid_location != location and not is_unknown_location:
                            denominator = 60.0
                            minutes = abs((current_time - previous_valid_time).total_seconds()) / denominator if denominator != 0 else 0.0
                            if minutes <= 30:
                                score += 8
                                reasons.append("Different locations appeared too close together for the same user.")
                                patterns.append("Impossible Travel-Like Pattern")

                if score > 0:
                    self.set_row_finding(dataframe, idx, score, reasons, " + ".join(patterns) or "Location Risk")

                if not is_unknown_location:
                    seen_locations.add(location)
                    if pd.notna(current_time):
                        previous_valid_time = current_time
                        previous_valid_location = location

        return self.summarize(dataframe)
