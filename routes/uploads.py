import logging
from typing import Optional
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status

from database.models import User
from services.auth_service import get_current_user_optional
from services.excel_service import (
    process_procurement_data,
    process_expenses_data,
    auto_detect_and_import,
)
from services.sync_service import (
    preview_import_deletion,
    delete_import_batch,
    clean_legacy_sample_data,
)
from services.analytics_service import get_import_history_list

logger = logging.getLogger("routes.uploads")

router = APIRouter(tags=["Excel Uploads & Data Sync"])

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


def _validate_excel_upload(file: UploadFile, content: bytes):
    """Shared validation for Excel uploads."""
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload an Excel (.xlsx or .xls) file.")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File is too large. Maximum file size is 10 MB.")


@router.post("/api/upload/procurement")
async def upload_procurement_excel(
    file: UploadFile = File(...),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Upload and import Procurement / Requirements Workbook."""
    content = await file.read()
    _validate_excel_upload(file, content)

    username = user.username if user else "admin"
    try:
        result = process_procurement_data(content, file.filename, uploaded_by=username)
        return {
            "success": True,
            "message": f"Procurement data from '{file.filename}' processed successfully.",
            "data": result,
        }
    except Exception as e:
        logger.exception("Failed to process procurement file: %s", e)
        raise HTTPException(status_code=500, detail="Unable to process the uploaded file. Please check the file format and try again.")


@router.post("/api/upload/expenses")
async def upload_expenses_excel(
    file: UploadFile = File(...),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Upload and import Monthly Expenses Workbook."""
    content = await file.read()
    _validate_excel_upload(file, content)

    username = user.username if user else "admin"
    try:
        result = process_expenses_data(content, file.filename, uploaded_by=username)
        return {
            "success": True,
            "message": f"Expense data from '{file.filename}' processed successfully.",
            "data": result,
        }
    except Exception as e:
        logger.exception("Failed to process expenses file: %s", e)
        raise HTTPException(status_code=500, detail="Unable to process the uploaded file. Please check the file format and try again.")


@router.post("/api/upload/auto")
async def upload_auto_excel(
    file: UploadFile = File(...),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Intelligently detect file type (Procurement or Expenses) and import."""
    content = await file.read()
    _validate_excel_upload(file, content)

    username = user.username if user else "admin"
    try:
        result = auto_detect_and_import(content, file.filename, uploaded_by=username)
        return {
            "success": True,
            "message": f"Excel workbook '{file.filename}' processed and imported successfully.",
            "data": result,
        }
    except Exception as e:
        logger.exception("Failed to auto-import file: %s", e)
        raise HTTPException(status_code=500, detail="Unable to process the uploaded file. Please check the file format and try again.")


@router.post("/api/sync/excel")
async def sync_excel_file(
    file: UploadFile = File(...),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Synchronization endpoint for live Excel updates.
    Accepts an Excel file and performs auto-detection + upsert.
    Designed to be called by external file watchers, cron jobs, or webhooks.
    """
    content = await file.read()
    _validate_excel_upload(file, content)

    username = user.username if user else "system_sync"
    try:
        result = auto_detect_and_import(content, file.filename, uploaded_by=username)
        return {
            "success": True,
            "message": f"Sync completed for '{file.filename}'.",
            "data": result,
            "sync_type": "file_upload",
        }
    except Exception as e:
        logger.exception("Sync failed for file: %s", e)
        raise HTTPException(status_code=500, detail="Synchronization failed. Please try again.")


@router.get("/api/imports")
def list_imports():
    """Retrieve history of uploaded Excel files."""
    return get_import_history_list()


@router.get("/api/admin/imports/{import_id}/preview")
def preview_import_delete(
    import_id: str,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Admin endpoint to preview records affected by deleting an import batch."""
    try:
        preview = preview_import_deletion(import_id)
        return preview
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error previewing import deletion: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to generate preview: {str(e)}")


@router.delete("/api/admin/imports/{import_id}")
def delete_import(
    import_id: str,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Protected Admin endpoint to safely delete an import batch:
    - Removes batch procurement and expense records
    - Removes products created exclusively by this import (source_type == 'excel_import')
    - Preserves legitimate electronic equipment inventory
    """
    try:
        result = delete_import_batch(import_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error deleting import batch: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to delete import batch: {str(e)}")


@router.post("/api/admin/cleanup-sample-data")
def cleanup_sample_data(
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Protected Admin endpoint to safely clean up any legacy sample Excel imports.
    Guarantees permanent electronic equipment data is preserved.
    """
    try:
        result = clean_legacy_sample_data()
        return result
    except Exception as e:
        logger.exception("Error cleaning sample data: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to clean sample data: {str(e)}")
