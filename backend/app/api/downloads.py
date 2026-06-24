from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.services.storage_service import StorageService

router = APIRouter(prefix=settings.api_prefix, tags=["downloads"])
storage_service = StorageService()


def _download(job_id: str, filename: str, media_type: str, missing_message: str) -> FileResponse:
    job_dir = storage_service.get_job_dir(job_id)
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="Job not found. Please run analysis first.")
    path = storage_service.get_output_file(job_id, filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=missing_message)
    return FileResponse(path, media_type=media_type, filename=filename)


@router.get("/download/fraud-transactions/{job_id}")
def download_fraud_transactions(job_id: str) -> FileResponse:
    return _download(
        job_id,
        settings.fraud_transactions_filename,
        "text/csv",
        "Fraud transactions file was not found for this job.",
    )


@router.get("/download/all-scored/{job_id}")
def download_all_scored(job_id: str) -> FileResponse:
    return _download(
        job_id,
        settings.all_scored_filename,
        "text/csv",
        "All scored transactions file was not found for this job.",
    )


@router.get("/download/summary-report/{job_id}")
def download_summary_report(job_id: str) -> FileResponse:
    return _download(
        job_id,
        settings.summary_report_filename,
        "application/pdf",
        "Summary report was not found for this job.",
    )
