from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class Settings:
    app_name: str = "SentinelPay AI"
    app_version: str = "0.5.0"
    api_prefix: str = "/api"
    storage_dir: Path = Path(__file__).resolve().parent.parent / "storage"
    max_upload_size_mb: int = 50
    allowed_origins: List[str] = field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    fraud_transactions_filename: str = "fraud_transactions.csv"
    all_scored_filename: str = "all_transactions_with_fraud_scores.csv"
    summary_report_filename: str = "fraud_summary_report.pdf"

    def ensure_directories(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
