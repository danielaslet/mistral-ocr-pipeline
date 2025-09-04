import os
import uuid
import yaml
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from azure.storage.blob import ContainerClient

from upload_to_blob import upload_file_to_blob
# Note: analyze_content_understanding_blob_batch will be refactored in Increment 2

load_dotenv()

app = FastAPI(
    title="Azure OCR Service",
    description="OCR pipeline with Azure blob integration and Content Understanding API",
    version="1.0.0"
)

# Job tracking (in-memory for MVP)
jobs = {}

class JobStatus(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, failed
    created_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    files_processed: int = 0
    results: Optional[dict] = None

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "Azure OCR Service",
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Azure OCR Service",
        "description": "OCR pipeline with Azure blob integration",
        "endpoints": {
            "health": "/health",
            "upload_only": "/upload-only",
            "process_blob": "/process-blob", 
            "upload_and_process": "/upload-and-process",
            "status": "/status/{job_id}",
            "results": "/results/{job_id}"
        },
        "docs": "/docs"
    }

@app.post("/upload-only")
async def upload_only(
    file: UploadFile = File(...),
    blob_name: Optional[str] = None
):
    """Upload a file to blob storage without processing"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        # Create temporary file
        temp_path = f"/tmp/{uuid.uuid4()}_{file.filename}"
        with open(temp_path, "wb") as temp_file:
            content = await file.read()
            temp_file.write(content)
        
        # Upload to blob
        final_blob_name = blob_name or file.filename
        uploaded_name = upload_file_to_blob(temp_path, final_blob_name)
        
        # Clean up temp file
        os.unlink(temp_path)
        
        return {
            "message": "File uploaded successfully",
            "blob_name": uploaded_name,
            "original_filename": file.filename,
            "size_bytes": len(content),
            "uploaded_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        # Clean up temp file if it exists
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

# Placeholder endpoints for future increments
@app.post("/process-blob")
async def process_blob():
    """Process all PDFs in blob container - To be implemented in Increment 2"""
    raise HTTPException(status_code=501, detail="Not implemented yet - coming in Increment 2")

@app.post("/upload-and-process")
async def upload_and_process():
    """Upload file and process immediately - To be implemented in Increment 2"""
    raise HTTPException(status_code=501, detail="Not implemented yet - coming in Increment 2")

@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Get job status - To be implemented in Increment 3"""
    raise HTTPException(status_code=501, detail="Not implemented yet - coming in Increment 3")

@app.get("/results/{job_id}")
async def get_job_results(job_id: str):
    """Get job results - To be implemented in Increment 3"""
    raise HTTPException(status_code=501, detail="Not implemented yet - coming in Increment 3")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)