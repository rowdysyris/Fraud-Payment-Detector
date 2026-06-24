import pandas as pd

from app.agents.base import AgentResult, BaseAgent
from app.core.schema_mapping import SchemaMappingResult, map_transaction_schema


class SchemaMappingAgent(BaseAgent):
    name = "Schema Mapping Agent"

    def run(self, dataframe: pd.DataFrame, mapping_result: SchemaMappingResult | None = None) -> AgentResult:
        if dataframe is None:
            return self.fail("No dataframe was available for schema mapping.")
        result = mapping_result or map_transaction_schema(dataframe)
        mapped_count = sum(1 for source in result.mapped_columns.values() if source is not None)
        missing = ", ".join(result.missing_required_columns)
        if result.missing_required_columns:
            return AgentResult(
                name=self.name,
                status="needs_attention",
                message=f"Mapped {mapped_count} standard column(s). Missing required column(s): {missing}.",
            )
        return self.ok(f"Mapped {mapped_count} standard column(s). Required fields are available.")
