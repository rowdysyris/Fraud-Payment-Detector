from io import BytesIO
from pathlib import Path
from typing import Tuple

import pandas as pd
from fastapi import HTTPException, UploadFile

from app.config import settings
from app.utils.constants import ALLOWED_UPLOAD_EXTENSIONS, CSV_ENCODING_FALLBACKS
from app.utils.safe_ops import make_unique_column_names


def _validate_extension(filename: str | None) -> str:
    extension = Path(filename or "").suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Upload one of: {allowed}.")
    return extension


def _validate_size(content: bytes) -> None:
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File is too large. Max size is {settings.max_upload_size_mb} MB.")


def _read_csv_with_fallbacks(content: bytes) -> pd.DataFrame:
    errors: list[str] = []
    for encoding in CSV_ENCODING_FALLBACKS:
        try:
            return pd.read_csv(BytesIO(content), encoding=encoding, keep_default_na=False, index_col=False, on_bad_lines="skip")
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: decoding failed")
        except pd.errors.EmptyDataError as exc:
            raise HTTPException(status_code=400, detail="Uploaded CSV file has no readable columns or rows.") from exc
        except pd.errors.ParserError as exc:
            raise HTTPException(status_code=400, detail=f"Uploaded CSV could not be parsed: {exc}") from exc
        except Exception as exc:
            errors.append(f"{encoding}: {exc}")
    detail = "Uploaded CSV could not be read with supported encodings: " + "; ".join(errors)
    raise HTTPException(status_code=400, detail=detail)


def _read_excel(content: bytes, extension: str) -> pd.DataFrame:
    try:
        if extension == ".xlsx":
            return pd.read_excel(BytesIO(content), keep_default_na=False, engine="openpyxl")
        return pd.read_excel(BytesIO(content), keep_default_na=False)
    except ImportError as exc:
        raise HTTPException(status_code=400, detail="Excel .xls support requires the xlrd package. Install backend requirements and retry.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Uploaded Excel file could not be read: {exc}") from exc
    except pd.errors.EmptyDataError as exc:
        raise HTTPException(status_code=400, detail="Uploaded Excel file has no readable columns or rows.") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read uploaded Excel file: {exc}") from exc


async def read_upload_to_dataframe(file: UploadFile) -> Tuple[pd.DataFrame, bytes]:
    extension = _validate_extension(file.filename)
    content = await file.read()
    _validate_size(content)

    dataframe = _read_csv_with_fallbacks(content) if extension == ".csv" else _read_excel(content, extension)
    if dataframe is None:
        raise HTTPException(status_code=400, detail="No dataframe was created from the uploaded file.")

    dataframe = dataframe.copy()
    dataframe.columns = make_unique_column_names(dataframe.columns)
    return dataframe, content
