# Azure Container Apps OCR Service - PDCA Development Plan

## **Intent**
Deploy the existing OCR pipeline as a scalable REST API service on Azure Container Apps, integrating with existing a1bgeneralresearch resources to provide remote document processing capabilities.

## **Success Criteria Checklist**
- [ ] FastAPI service processes documents via HTTP endpoints
- [ ] Service integrates with existing Azure storage (a1bgeneralresearch) 
- [ ] Service uses existing AI Foundry resource (a1bcontentunderstanding)
- [ ] Container deploys successfully to Azure Container Apps
- [ ] Zero breaking changes to existing local scripts
- [ ] End-to-end document upload → processing → results retrieval works

## **PDCA Incremental Implementation**

### **Preparation Phase**: ✅ COMPLETED (d8f9503) - Repository initialization and PDCA setup
- [x] Initialize Git repository with existing codebase
- [x] Create GitHub repository: https://github.com/danielaslet/mistral-ocr-pipeline
- [x] Add PDCA development methodology guidelines (CLAUDE.md)
- [x] Setup feature development structure with test evidence framework
- [x] Create Azure Container Apps OCR service feature plan
- [x] Push to remote repository with proper commit tracking

### **Increment 1**: ✅ COMPLETED (51354f0) - Create FastAPI wrapper service
- [x] Create `app.py` with FastAPI app structure
- [x] Add basic health check endpoint (`GET /health`)
- [x] Wrap existing `upload_to_blob.py` logic in `POST /upload-only` endpoint
- [x] Test locally with existing blob storage
- [x] Archive test evidence: API response validation

### **Increment 2**: ✅ COMPLETED (f1291d4) - Add document processing endpoints  
- [x] Wrap `analyze_content_understanding_blob_batch.py` in `POST /process-blob` endpoint
- [x] Add combined `POST /upload-and-process` endpoint
- [x] Add async job tracking with unique job IDs
- [x] Test complete upload → process workflow
- [x] Archive test evidence: End-to-end processing validation

### **Increment 3**: ❌ PENDING - Add results retrieval endpoints
- [ ] Implement `GET /status/{job_id}` for job status
- [ ] Implement `GET /results/{job_id}` for downloading outputs
- [ ] Add job persistence (in-memory for MVP)
- [ ] Test complete API workflow
- [ ] Archive test evidence: Full API lifecycle test

### **Increment 4**: ❌ PENDING - Containerize application
- [ ] Create `Dockerfile` with Python 3.13 base
- [ ] Add `requirements.txt` with all dependencies
- [ ] Configure environment variables for Azure resources
- [ ] Build and test container locally
- [ ] Archive test evidence: Container functionality validation

### **Increment 5**: ❌ PENDING - Azure Container Registry setup
- [ ] Create container registry in a1bgeneralresearch resource group
- [ ] Push container image to registry via Azure CLI
- [ ] Verify image deployment and accessibility
- [ ] Test image pull and run
- [ ] Archive test evidence: Registry and image validation

### **Increment 6**: ❌ PENDING - Deploy to Azure Container Apps
- [ ] Create Container Apps environment in a1bgeneralresearch
- [ ] Configure environment variables for existing resources
- [ ] Deploy container app with proper scaling rules
- [ ] Verify service accessibility via public endpoint
- [ ] Archive test evidence: Live service validation

### **Increment 7**: ❌ PENDING - Integration testing and documentation
- [ ] Test all endpoints with real documents
- [ ] Validate integration with existing storage and AI resources
- [ ] Update README with API documentation
- [ ] Create deployment scripts for Azure CLI automation
- [ ] Archive test evidence: Complete system validation

## **Azure CLI Commands Structure**
```bash
# Registry creation (Increment 5)
az acr create --name a1bocrregistry --resource-group a1bgeneralresearch --sku Basic

# Container Apps deployment (Increment 6) 
az containerapp env create --name ocr-env --resource-group a1bgeneralresearch
az containerapp create --name a1b-ocr-service --resource-group a1bgeneralresearch --environment ocr-env
```

## **Rollback Strategy**
Each increment creates a commit point. If any increment fails:
1. Revert to previous increment's commit
2. Analyze failure in test evidence
3. Adjust approach for current increment
4. Re-attempt with modified plan

## **File Structure**
```
feature_development/
  azure_container_apps_ocr/
    FEATURE_PLAN.md           # This plan
    test_evidence/
      increment_1/            # API wrapper validation
      increment_2/            # Processing endpoints validation  
      increment_3/            # Results endpoints validation
      increment_4/            # Container validation
      increment_5/            # Registry validation
      increment_6/            # Deployment validation
      increment_7/            # Integration validation
    deployment_scripts/       # Azure CLI automation scripts
```