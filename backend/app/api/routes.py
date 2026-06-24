from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.schemas import AnalysisResponse, ReviewStatusRequest
from app.services.analysis_service import AnalysisService
from app.services.storage_service import StorageService
from app.services.transaction_detail_service import build_transaction_detail_payload
from app.utils.safe_ops import to_json_records

router = APIRouter(prefix=settings.api_prefix, tags=["analysis"])
analysis_service = AnalysisService()
storage_service = StorageService()

ALLOWED_REVIEW_STATUSES = {"Pending Review", "Reviewed", "Confirmed Fraud", "Marked Safe"}


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_transactions(file: UploadFile = File(...)) -> AnalysisResponse:
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="No file was uploaded.")

    try:
        return await analysis_service.analyze_upload(file)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="SentinelPay AI could not complete analysis safely. Please verify the file format and try again.",
        ) from exc


@router.get("/transaction-detail/{job_id}/{transaction_id}")
def get_transaction_detail(job_id: str, transaction_id: str) -> dict:
    try:
        dataframe = storage_service.load_scored_transactions(job_id)
        return build_transaction_detail_payload(job_id, dataframe, transaction_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Transaction detail could not be loaded safely for this job.",
        ) from exc


@router.patch("/transaction-review/{job_id}/{transaction_id}")
def update_transaction_review(job_id: str, transaction_id: str, payload: ReviewStatusRequest) -> dict:
    review_status = str(payload.review_status or "").strip()
    if review_status not in ALLOWED_REVIEW_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Invalid review_status. Allowed values: Pending Review, Reviewed, Confirmed Fraud, Marked Safe.",
        )
    try:
        updated_rows = storage_service.update_transaction_review_status(job_id, transaction_id, review_status)
        records = to_json_records(updated_rows)
        return {"job_id": job_id, "updated_count": len(records), "transaction": records[0] if records else {}}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Transaction review status could not be updated safely.",
        ) from exc
