"""
Metriviz FastAPI Backend Module
High-performance asynchronous REST API using FastAPI.
Connects frontend requests to the Pandas, NumPy, and Seaborn data analysis engine.
Strictly upload-driven: No static sample datasets.
Streams in-memory chart image bytes and automatically deletes files on refresh.
"""

import os
import uuid
import json
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from werkzeug.utils import secure_filename
try:
    from backend import analysis
except ImportError:
    import analysis

# Initialize FastAPI Application
app = FastAPI(
    title="Metriviz Analytics API",
    description="FastAPI Backend for CSV Data Analytics, Pandas/NumPy manipulations, and Seaborn visual plots",
    version="3.0.0"
)

# Enable Cross-Origin Resource Sharing (CORS) for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Local Temporary Uploads Directory
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Pydantic Request Models
class VisualizeRequest(BaseModel):
    filename: str
    x_axis: str
    y_axis: str
    chart_type: str = Field(default="bar")
    palette: str = Field(default="berry")
    theme: str = Field(default="dark")


@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify FastAPI backend service is active."""
    return {
        "status": "success",
        "message": "Metriviz FastAPI Backend (api.py + analysis.py) is active and ready for CSV uploads.",
        "framework": "FastAPI",
        "version": "3.0.0"
    }


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Receives user-uploaded CSV or Excel file from frontend, stores it temporarily in backend/uploads,
    and runs Pandas analysis via analysis.py to extract columns, types, and summary metrics.
    """
    allowed_exts = ('.csv', '.xlsx', '.xls')
    if not file.filename or not file.filename.lower().endswith(allowed_exts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv, .xlsx, and .xls files are supported."
        )

    original_name = secure_filename(file.filename)
    unique_prefix = uuid.uuid4().hex[:8]
    stored_filename = f"{unique_prefix}_{original_name}"
    filepath = os.path.join(UPLOAD_FOLDER, stored_filename)

    try:
        # Read file contents and write to disk
        contents = await file.read()
        with open(filepath, "wb") as f:
            f.write(contents)

        # Delegate data extraction to Pandas via analysis module
        parsed_info = analysis.parse_csv_file(filepath)
        parsed_info["status"] = "success"
        parsed_info["filename"] = stored_filename
        parsed_info["display_name"] = original_name
        return parsed_info

    except Exception as e:
        analysis.delete_file_from_disk(filepath)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pandas parsing error: {str(e)}"
        )


@app.post("/api/visualize")
async def visualize(req: VisualizeRequest):
    """
    Queries and analyzes the user's uploaded CSV file using Pandas and NumPy,
    then renders a Seaborn statistical chart purely in-memory as Base64 bytes.
    No images are ever saved to disk.
    """
    filepath = os.path.join(UPLOAD_FOLDER, secure_filename(req.filename))
    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uploaded file not found on server (may have been cleaned up on refresh)."
        )

    try:
        is_dark = req.theme == "dark"
        result = analysis.generate_chart_image_bytes(
            filepath=filepath,
            x_axis=req.x_axis,
            y_axis=req.y_axis,
            chart_type=req.chart_type,
            palette=req.palette,
            is_dark=is_dark
        )
        result["status"] = "success"
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/cleanup")
async def cleanup_file(request: Request):
    """
    Deletes the uploaded CSV file from server disk.
    Called automatically when the frontend is refreshed, closed, or when user clears data.
    Supports JSON payloads, form data, and browser sendBeacon payloads.
    """
    filename = None
    try:
        body = await request.json()
        filename = body.get("filename")
    except Exception:
        raw_body = await request.body()
        if raw_body:
            try:
                parsed = json.loads(raw_body.decode("utf-8"))
                filename = parsed.get("filename")
            except Exception:
                filename = raw_body.decode("utf-8").strip()

    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing for cleanup."
        )

    filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
    deleted = analysis.delete_file_from_disk(filepath)

    return {
        "status": "success" if deleted else "not_found",
        "message": f"File {filename} {'deleted from server' if deleted else 'not found or already deleted'}"
    }


if __name__ == "__main__":
    print("Starting Metriviz FastAPI Backend on http://127.0.0.1:5000 ...")
    uvicorn.run("api:app", host="0.0.0.0", port=5000, reload=False)
