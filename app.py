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
from blob_processor import BlobProcessor

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
            "results": "/results/{job_id}",
            "jobs": "/jobs"
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

@app.post("/process-blob")
async def process_blob(background_tasks: BackgroundTasks):
    """Process all PDFs in blob container"""
    try:
        # Create job ID for tracking
        job_id = str(uuid.uuid4())
        
        # Initialize job status
        jobs[job_id] = JobStatus(
            job_id=job_id,
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
            files_processed=0
        )
        
        # Start processing in background
        background_tasks.add_task(process_blob_background, job_id)
        
        return {
            "message": "Processing started",
            "job_id": job_id,
            "status": "pending",
            "created_at": jobs[job_id].created_at,
            "status_url": f"/status/{job_id}",
            "results_url": f"/results/{job_id}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start processing: {str(e)}")

@app.post("/upload-and-process")
async def upload_and_process(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    blob_name: Optional[str] = None
):
    """Upload file and process immediately"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        # Create job ID for tracking
        job_id = str(uuid.uuid4())
        
        # Initialize job status
        jobs[job_id] = JobStatus(
            job_id=job_id,
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
            files_processed=0
        )
        
        # Read file content before background task
        file_content = await file.read()
        
        # Start upload and process in background
        background_tasks.add_task(upload_and_process_background, job_id, file_content, file.filename, blob_name)
        
        return {
            "message": "Upload and processing started",
            "job_id": job_id,
            "status": "pending",
            "original_filename": file.filename,
            "created_at": jobs[job_id].created_at,
            "status_url": f"/status/{job_id}",
            "results_url": f"/results/{job_id}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start upload and processing: {str(e)}")

@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Get job status and progress information"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    job = jobs[job_id]
    response = {
        "job_id": job.job_id,
        "status": job.status,
        "created_at": job.created_at,
        "files_processed": job.files_processed
    }
    
    if job.completed_at:
        response["completed_at"] = job.completed_at
        
    if job.error_message:
        response["error_message"] = job.error_message
        
    # Add processing summary for completed jobs
    if job.status == "completed" and job.results:
        response["summary"] = {
            "total_files": job.results.get("files_processed", 0),
            "timestamp": job.results.get("timestamp"),
            "status": job.results.get("status")
        }
    
    return response

@app.get("/results/{job_id}")
async def get_job_results(job_id: str):
    """Get complete job results and output file information"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    job = jobs[job_id]
    
    if job.status == "pending":
        raise HTTPException(status_code=202, detail="Job is still pending. Check status later.")
    
    if job.status == "processing":
        raise HTTPException(status_code=202, detail="Job is still processing. Check status later.")
    
    if job.status == "failed":
        return {
            "job_id": job.job_id,
            "status": "failed",
            "error_message": job.error_message,
            "created_at": job.created_at,
            "completed_at": job.completed_at
        }
    
    if job.status == "completed":
        if not job.results:
            raise HTTPException(status_code=500, detail="Job completed but no results found")
            
        return {
            "job_id": job.job_id,
            "status": "completed",
            "created_at": job.created_at,
            "completed_at": job.completed_at,
            "files_processed": job.files_processed,
            "results": job.results
        }
    
    raise HTTPException(status_code=500, detail=f"Unknown job status: {job.status}")

@app.get("/jobs")
async def list_jobs():
    """List all jobs with their current status"""
    job_list = []
    for job_id, job in jobs.items():
        job_summary = {
            "job_id": job.job_id,
            "status": job.status,
            "created_at": job.created_at,
            "files_processed": job.files_processed
        }
        
        if job.completed_at:
            job_summary["completed_at"] = job.completed_at
            
        if job.error_message:
            job_summary["error_message"] = job.error_message
            
        job_list.append(job_summary)
    
    return {
        "total_jobs": len(job_list),
        "jobs": sorted(job_list, key=lambda x: x["created_at"], reverse=True)
    }

# Background task functions
async def process_blob_background(job_id: str):
    """Background task to process all blobs"""
    try:
        jobs[job_id].status = "processing"
        
        # Process blobs
        processor = BlobProcessor()
        result = processor.process_all_blobs()
        
        # Update job status
        jobs[job_id].status = "completed"
        jobs[job_id].completed_at = datetime.now(timezone.utc).isoformat()
        jobs[job_id].files_processed = result["files_processed"]
        jobs[job_id].results = result
        
    except Exception as e:
        jobs[job_id].status = "failed"
        jobs[job_id].completed_at = datetime.now(timezone.utc).isoformat()
        jobs[job_id].error_message = str(e)

async def upload_and_process_background(job_id: str, file_content: bytes, filename: str, blob_name: Optional[str]):
    """Background task to upload file and process"""
    temp_path = None
    try:
        jobs[job_id].status = "processing"
        
        # Create temporary file
        temp_path = f"/tmp/{uuid.uuid4()}_{filename}"
        with open(temp_path, "wb") as temp_file:
            temp_file.write(file_content)
        
        # Upload to blob
        final_blob_name = blob_name or filename
        upload_file_to_blob(temp_path, final_blob_name)
        
        # Process the uploaded file
        processor = BlobProcessor()
        result = processor.process_single_blob(final_blob_name)
        
        # Update job status
        jobs[job_id].status = "completed"
        jobs[job_id].completed_at = datetime.now(timezone.utc).isoformat()
        jobs[job_id].files_processed = 1
        jobs[job_id].results = {
            "status": "completed",
            "files_processed": 1,
            "results": [result],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        jobs[job_id].status = "failed"
        jobs[job_id].completed_at = datetime.now(timezone.utc).isoformat()
        jobs[job_id].error_message = str(e)
    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)