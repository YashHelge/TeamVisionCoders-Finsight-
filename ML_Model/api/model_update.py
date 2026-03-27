"""
Model Update API — TFLite model delivery + version check.
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from api.auth import CurrentUser, get_current_user
from config import settings

router = APIRouter()
logger = logging.getLogger("finsight.model_update")

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ML_Model", "models")
# Fallback to relative path
if not os.path.exists(MODEL_DIR):
    MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")


@router.get("/model/update")
async def check_model_update(
    device_version: str = Query("0.0.0", description="Current model version on device"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Check if a model update is available.
    Returns version info and download URL if update needed.
    """
    current = settings.TFLITE_MODEL_VERSION

    if device_version == current:
        return {
            "update_available": False,
            "current_version": current,
            "device_version": device_version,
        }

    return {
        "update_available": True,
        "current_version": current,
        "device_version": device_version,
        "download_url": "/api/v1/model/download",
        "model_size_bytes": _get_model_size(),
    }


@router.get("/model/download")
async def download_model(
    user: CurrentUser = Depends(get_current_user),
):
    """Download the latest TFLite model."""
    model_path = os.path.join(MODEL_DIR, "finsight_classifier.tflite")

    if not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail="Model file not found")

    return FileResponse(
        model_path,
        media_type="application/octet-stream",
        filename="finsight_classifier.tflite",
    )


def _get_model_size() -> int:
    model_path = os.path.join(MODEL_DIR, "finsight_classifier.tflite")
    if os.path.exists(model_path):
        return os.path.getsize(model_path)
    return 0
