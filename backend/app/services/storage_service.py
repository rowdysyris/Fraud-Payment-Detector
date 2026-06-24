from pathlib import Path
from uuid import uuid4

import pandas as pd

from app.config import settings
from app.utils.safe_ops import safe_filename


class StorageService:
    def create_job_dir(self) -> tuple[str, Path]:
        settings.ensure_directories()
        job_id = uuid4().hex
        job_dir = settings.storage_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        return job_id, job_dir

    def save_uploaded_file(self, job_dir: Path, filename: str, content: bytes) -> Path:
        safe_name = safe_filename(filename or "uploaded_file")
        path = job_dir / f"original_{safe_name}"
        path.write_bytes(content)
        return path

    def get_job_dir(self, job_id: str) -> Path:
        safe_job_id = safe_filename(job_id)
        return settings.storage_dir / safe_job_id

    def get_output_file(self, job_id: str, filename: str) -> Path:
        safe_job_id = safe_filename(job_id)
        safe_name = safe_filename(filename)
        return settings.storage_dir / safe_job_id / safe_name

    def output_file_exists(self, job_id: str, filename: str) -> bool:
        return self.get_output_file(job_id, filename).is_file()

    def load_scored_transactions(self, job_id: str) -> pd.DataFrame:
        job_dir = self.get_job_dir(job_id)
        if not job_dir.is_dir():
            raise FileNotFoundError("Job not found. Please run analysis first.")
        path = self.get_output_file(job_id, settings.all_scored_filename)
        if not path.is_file():
            raise FileNotFoundError("All scored transactions file was not found for this job.")
        return pd.read_csv(path, keep_default_na=False)

    def save_scored_transactions(self, job_id: str, dataframe: pd.DataFrame) -> Path:
        job_dir = self.get_job_dir(job_id)
        if not job_dir.is_dir():
            raise FileNotFoundError("Job not found. Please run analysis first.")
        path = self.get_output_file(job_id, settings.all_scored_filename)
        dataframe.to_csv(path, index=False)
        return path

    def update_transaction_review_status(self, job_id: str, transaction_id: str, review_status: str) -> pd.DataFrame:
        dataframe = self.load_scored_transactions(job_id)
        if "transaction_id" not in dataframe.columns:
            raise KeyError("transaction_id column is missing from scored transactions.")
        mask = dataframe["transaction_id"].astype(str).eq(str(transaction_id))
        if not bool(mask.any()):
            raise LookupError("Transaction not found for this job.")

        dataframe.loc[mask, "review_status"] = review_status
        self.save_scored_transactions(job_id, dataframe)

        fraud_path = self.get_output_file(job_id, settings.fraud_transactions_filename)
        if fraud_path.is_file():
            fraud_df = pd.read_csv(fraud_path, keep_default_na=False)
            if "transaction_id" in fraud_df.columns:
                fraud_mask = fraud_df["transaction_id"].astype(str).eq(str(transaction_id))
                if bool(fraud_mask.any()):
                    fraud_df.loc[fraud_mask, "review_status"] = review_status
                    fraud_df.to_csv(fraud_path, index=False)

        return dataframe.loc[mask].copy()
