from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class AgentStatus(BaseModel):
    name: str
    status: str
    message: str
    triggered_count: int = 0
    warning_count: int = 0


class AnalysisSummary(BaseModel):
    total_transactions: int = 0
    valid_transactions: int = 0
    validated_transactions: int = 0
    suspicious_transactions: int = 0
    high_risk_transactions: int = 0
    critical_risk_transactions: int = 0
    critical_transactions: int = 0
    critical_fraud_transactions: int = 0
    total_amount_at_risk: float = 0.0
    total_fraud_amount_at_risk: float = 0.0
    risk_distribution: Dict[str, int] = Field(default_factory=dict)
    top_risky_users: List[dict] = Field(default_factory=list)
    top_risky_merchants: List[dict] = Field(default_factory=list)


class DownloadLinks(BaseModel):
    fraud_transactions: Optional[str] = None
    all_scored: Optional[str] = None
    summary_report: Optional[str] = None


class IngestionMetadata(BaseModel):
    original_rows: int = 0
    cleaned_rows: int = 0
    original_columns: List[str] = Field(default_factory=list)
    mapped_columns: Dict[str, Optional[str]] = Field(default_factory=dict)
    missing_required_columns: List[str] = Field(default_factory=list)
    cleaning_warnings: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    is_valid: bool = False


class AnalysisResponse(BaseModel):
    job_id: str
    filename: str
    status: str = "success"
    message: str

    total_transactions: int = 0
    valid_transactions: int = 0
    suspicious_transactions: int = 0
    high_risk_transactions: int = 0
    critical_risk_transactions: int = 0
    total_amount_at_risk: float = 0.0
    risk_distribution: Dict[str, int] = Field(default_factory=dict)
    agent_summary: Dict[str, dict] = Field(default_factory=dict)
    top_risky_users: List[dict] = Field(default_factory=list)
    top_risky_merchants: List[dict] = Field(default_factory=list)
    sample_flagged_transactions: List[dict] = Field(default_factory=list)
    download_urls: DownloadLinks = Field(default_factory=DownloadLinks)
    warnings: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)

    summary: AnalysisSummary
    agents: List[AgentStatus]
    preview: List[dict] = Field(default_factory=list)
    transactions: List[dict] = Field(default_factory=list)
    ingestion_metadata: Optional[IngestionMetadata] = None
    download_links: Optional[DownloadLinks] = None


class ErrorResponse(BaseModel):
    detail: str | dict


class ReviewStatusRequest(BaseModel):
    review_status: str
