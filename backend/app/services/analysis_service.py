from typing import Any

import pandas as pd
from fastapi import HTTPException, UploadFile

from app.agents.amount_anomaly_agent import AmountAnomalyAgent
from app.agents.base import AgentResult
from app.agents.data_cleaning_agent import DataCleaningAgent
from app.agents.data_validation_agent import DataValidationAgent
from app.agents.duplicate_payment_agent import DuplicatePaymentAgent
from app.agents.final_risk_scoring_agent import FinalRiskScoringAgent
from app.agents.location_risk_agent import LocationRiskAgent
from app.agents.merchant_risk_agent import MerchantRiskAgent
from app.agents.recommendation_agent import RecommendationAgent
from app.agents.schema_mapping_agent import SchemaMappingAgent
from app.agents.user_behavior_agent import UserBehaviorAgent
from app.agents.velocity_fraud_agent import VelocityFraudAgent
from app.config import settings
from app.core.cleaning import clean_transactions_dataframe
from app.core.file_loader import read_upload_to_dataframe
from app.core.report_generator import write_fraud_reports
from app.core.schema_mapping import map_transaction_schema
from app.core.scoring import attach_starter_scores
from app.core.validation import validate_transaction_dataset
from app.schemas import AgentStatus, AnalysisResponse, AnalysisSummary, DownloadLinks, IngestionMetadata
from app.services.storage_service import StorageService
from app.utils.safe_ops import safe_float, to_json_records


class AnalysisService:
    def __init__(self) -> None:
        self.storage = StorageService()
        self.profile_agents = [DataValidationAgent(), SchemaMappingAgent(), DataCleaningAgent()]
        self.fraud_agents = [
            AmountAnomalyAgent(),
            VelocityFraudAgent(),
            UserBehaviorAgent(),
            MerchantRiskAgent(),
            LocationRiskAgent(),
            DuplicatePaymentAgent(),
            FinalRiskScoringAgent(),
            RecommendationAgent(),
        ]

    async def analyze_upload(self, file: UploadFile) -> AnalysisResponse:
        raw_dataframe, raw_content = await read_upload_to_dataframe(file)
        mapping_result = map_transaction_schema(raw_dataframe)
        cleaning_result = clean_transactions_dataframe(mapping_result.dataframe)
        validation_report = validate_transaction_dataset(
            cleaning_result.dataframe,
            original_rows=len(raw_dataframe.index),
            original_columns=mapping_result.original_columns,
            mapped_columns=mapping_result.mapped_columns,
            missing_required_columns=mapping_result.missing_required_columns,
            cleaning_warnings=[*mapping_result.warnings, *cleaning_result.warnings],
        )

        if not validation_report.is_valid:
            raise HTTPException(status_code=400, detail=validation_report.message)

        job_id, job_dir = self.storage.create_job_dir()
        self.storage.save_uploaded_file(job_dir, file.filename or "uploaded_file", raw_content)

        analyzed_dataframe = cleaning_result.dataframe.copy()
        agent_results: list[AgentResult] = []
        agent_results.append(self._run_profile_agent(DataValidationAgent(), analyzed_dataframe, validation_report))
        agent_results.append(self._run_profile_agent(SchemaMappingAgent(), raw_dataframe, mapping_result))
        agent_results.append(self._run_profile_agent(DataCleaningAgent(), analyzed_dataframe, cleaning_result))

        for agent in self.fraud_agents:
            agent_results.append(self._run_fraud_agent(agent, analyzed_dataframe))

        if "fraud_score" not in analyzed_dataframe.columns or "risk_level" not in analyzed_dataframe.columns:
            analyzed_dataframe = attach_starter_scores(analyzed_dataframe)
            agent_results.append(
                AgentResult(
                    name="Pipeline Recovery",
                    status="completed_with_warnings",
                    message="Final scoring columns were missing after agent execution, so safe default risk columns were attached.",
                    triggered_count=0,
                    warning_count=1,
                )
            )

        summary, risk_distribution, total_amount_at_risk = self._build_summary(
            analyzed_dataframe=analyzed_dataframe,
            total_rows=validation_report.original_rows,
            valid_rows=validation_report.cleaned_rows,
        )
        agent_summary = self._build_agent_summary(agent_results)
        top_risky_users = self._top_risky_entities(analyzed_dataframe, "user_id")
        top_risky_merchants = self._top_risky_entities(analyzed_dataframe, "merchant")
        sample_flagged_transactions = self._sample_flagged_transactions(analyzed_dataframe)
        warnings = self._build_warnings(validation_report.cleaning_warnings, agent_results)
        download_links = DownloadLinks(
            fraud_transactions=f"{settings.api_prefix}/download/fraud-transactions/{job_id}",
            all_scored=f"{settings.api_prefix}/download/all-scored/{job_id}",
            summary_report=f"{settings.api_prefix}/download/summary-report/{job_id}",
        )

        summary.top_risky_users = top_risky_users
        summary.top_risky_merchants = top_risky_merchants

        write_fraud_reports(
            job_dir,
            analyzed_dataframe,
            summary,
            report_context={
                "job_id": job_id,
                "risk_distribution": risk_distribution,
                "top_risky_users": top_risky_users,
                "top_risky_merchants": top_risky_merchants,
                "agent_summary": agent_summary,
            },
        )

        agents = [
            AgentStatus(
                name=result.name,
                status=result.status,
                message=result.message,
                triggered_count=int(result.triggered_count),
                warning_count=int(result.warning_count),
            )
            for result in agent_results
        ]

        metadata = IngestionMetadata(
            original_rows=int(validation_report.original_rows),
            cleaned_rows=int(validation_report.cleaned_rows),
            original_columns=validation_report.original_columns,
            mapped_columns=validation_report.mapped_columns,
            missing_required_columns=validation_report.missing_required_columns,
            cleaning_warnings=validation_report.cleaning_warnings,
            validation_errors=validation_report.validation_errors,
            is_valid=validation_report.is_valid,
        )

        return AnalysisResponse(
            job_id=job_id,
            filename=file.filename or "uploaded_file",
            status="success",
            message="File analyzed successfully. Fraud detection agents completed and reports were generated.",
            total_transactions=summary.total_transactions,
            valid_transactions=summary.valid_transactions,
            suspicious_transactions=summary.suspicious_transactions,
            high_risk_transactions=summary.high_risk_transactions,
            critical_risk_transactions=summary.critical_risk_transactions,
            total_amount_at_risk=total_amount_at_risk,
            risk_distribution=risk_distribution,
            agent_summary=agent_summary,
            top_risky_users=top_risky_users,
            top_risky_merchants=top_risky_merchants,
            sample_flagged_transactions=sample_flagged_transactions,
            download_urls=download_links,
            warnings=warnings,
            validation_errors=validation_report.validation_errors,
            summary=summary,
            agents=agents,
            preview=to_json_records(analyzed_dataframe.head(20)),
            transactions=to_json_records(analyzed_dataframe),
            ingestion_metadata=metadata,
            download_links=download_links,
        )

    def _run_profile_agent(self, agent: Any, dataframe: pd.DataFrame, context: Any) -> AgentResult:
        try:
            return agent.run(dataframe, context)
        except Exception as exc:
            return AgentResult(
                name=getattr(agent, "name", agent.__class__.__name__),
                status="failed",
                message=f"Agent failed safely: {exc}",
                triggered_count=0,
                warning_count=1,
            )

    def _run_fraud_agent(self, agent: Any, dataframe: pd.DataFrame) -> AgentResult:
        try:
            return agent.run(dataframe)
        except Exception as exc:
            return AgentResult(
                name=getattr(agent, "name", agent.__class__.__name__),
                status="failed",
                message=f"Agent failed safely: {exc}",
                triggered_count=0,
                warning_count=1,
            )

    def _build_summary(self, analyzed_dataframe: pd.DataFrame, total_rows: int, valid_rows: int) -> tuple[AnalysisSummary, dict[str, int], float]:
        risk_distribution = {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0, "Critical Risk": 0}
        if analyzed_dataframe is not None and not analyzed_dataframe.empty and "risk_level" in analyzed_dataframe.columns:
            actual_counts = analyzed_dataframe["risk_level"].fillna("Low Risk").value_counts().to_dict()
            for risk_level in risk_distribution:
                risk_distribution[risk_level] = int(actual_counts.get(risk_level, 0))

        suspicious_mask = self._suspicious_mask(analyzed_dataframe)
        suspicious_transactions = int(suspicious_mask.sum()) if suspicious_mask is not None else 0
        high_risk_transactions = int(risk_distribution.get("High Risk", 0))
        critical_risk_transactions = int(risk_distribution.get("Critical Risk", 0))
        total_amount_at_risk = self._amount_at_risk(analyzed_dataframe, suspicious_mask)

        summary = AnalysisSummary(
            total_transactions=int(total_rows),
            valid_transactions=int(valid_rows),
            validated_transactions=int(valid_rows),
            suspicious_transactions=suspicious_transactions,
            high_risk_transactions=high_risk_transactions,
            critical_risk_transactions=critical_risk_transactions,
            critical_transactions=critical_risk_transactions,
            critical_fraud_transactions=critical_risk_transactions,
            total_amount_at_risk=total_amount_at_risk,
            total_fraud_amount_at_risk=total_amount_at_risk,
            risk_distribution=risk_distribution,
        )
        return summary, risk_distribution, total_amount_at_risk

    def _suspicious_mask(self, dataframe: pd.DataFrame) -> pd.Series | None:
        if dataframe is None:
            return None
        if dataframe.empty:
            return pd.Series([], index=dataframe.index, dtype="bool")
        if "risk_level" in dataframe.columns:
            return dataframe["risk_level"].isin(["Medium Risk", "High Risk", "Critical Risk"])
        if "fraud_score" in dataframe.columns:
            return pd.to_numeric(dataframe["fraud_score"], errors="coerce").fillna(0) > 30
        return pd.Series([False] * len(dataframe.index), index=dataframe.index)

    def _amount_at_risk(self, dataframe: pd.DataFrame, mask: pd.Series | None) -> float:
        if dataframe is None or dataframe.empty or mask is None or "amount" not in dataframe.columns:
            return 0.0
        amounts = pd.to_numeric(dataframe.loc[mask, "amount"], errors="coerce").fillna(0.0).abs()
        return round(float(amounts.sum()), 2)

    def _build_agent_summary(self, agent_results: list[AgentResult]) -> dict[str, dict]:
        return {
            result.name: {
                "status": result.status,
                "message": result.message,
                "triggered_count": int(result.triggered_count),
                "warning_count": int(result.warning_count),
            }
            for result in agent_results
        }

    def _top_risky_entities(self, dataframe: pd.DataFrame, column: str, limit: int = 5) -> list[dict]:
        if dataframe is None or dataframe.empty or column not in dataframe.columns:
            return []
        if "fraud_score" not in dataframe.columns:
            return []

        working = dataframe.copy()
        working[column] = working[column].fillna("Unknown").astype(str).replace({"": "Unknown"})
        working["fraud_score"] = pd.to_numeric(working["fraud_score"], errors="coerce").fillna(0.0)
        if "amount" in working.columns:
            working["amount_at_risk_source"] = pd.to_numeric(working["amount"], errors="coerce").fillna(0.0).abs()
        else:
            working["amount_at_risk_source"] = 0.0
        suspicious = self._suspicious_mask(working)
        working["suspicious_flag"] = suspicious.astype(bool) if suspicious is not None else False
        working["suspicious_amount"] = working["amount_at_risk_source"].where(working["suspicious_flag"], 0.0)
        grouped = working.groupby(column, dropna=False).agg(
            transaction_count=(column, "size"),
            suspicious_transactions=("suspicious_flag", "sum"),
            average_fraud_score=("fraud_score", "mean"),
            max_fraud_score=("fraud_score", "max"),
            amount_at_risk=("suspicious_amount", "sum"),
        )
        grouped = grouped.sort_values(["max_fraud_score", "average_fraud_score", "amount_at_risk"], ascending=False).head(limit)
        records: list[dict] = []
        for entity, row in grouped.iterrows():
            records.append(
                {
                    column: str(entity),
                    "transaction_count": int(row["transaction_count"]),
                    "suspicious_transactions": int(row["suspicious_transactions"]),
                    "average_fraud_score": round(float(row["average_fraud_score"]), 2),
                    "max_fraud_score": round(float(row["max_fraud_score"]), 2),
                    "amount_at_risk": round(float(row["amount_at_risk"]), 2),
                }
            )
        return records

    def _sample_flagged_transactions(self, dataframe: pd.DataFrame, limit: int = 10) -> list[dict]:
        if dataframe is None or dataframe.empty:
            return []
        mask = self._suspicious_mask(dataframe)
        if mask is None or not bool(mask.any()):
            return []
        columns = [
            "transaction_id",
            "user_id",
            "transaction_time",
            "amount",
            "merchant",
            "location",
            "payment_method",
            "rule_fraud_score",
            "ml_fraud_probability",
            "fraud_score",
            "risk_level",
            "fraud_pattern",
            "fraud_reason",
            "triggered_agents",
            "confidence",
            "recommended_action",
            "review_status",
        ]
        available_columns = [column for column in columns if column in dataframe.columns]
        flagged = dataframe.loc[mask, available_columns].copy()
        if "fraud_score" in flagged.columns:
            flagged = flagged.sort_values("fraud_score", ascending=False)
        return to_json_records(flagged.head(limit))

    def _build_warnings(self, cleaning_warnings: list[str], agent_results: list[AgentResult]) -> list[str]:
        warnings = list(dict.fromkeys([str(warning) for warning in cleaning_warnings if str(warning).strip()]))
        for result in agent_results:
            if result.warning_count or result.status in {"failed", "completed_with_warnings"}:
                warnings.append(f"{result.name}: {result.message}")
        return list(dict.fromkeys(warnings))
