# Feature Development

This directory contains all feature development work following the PDCA methodology outlined in `CLAUDE.md`.

## Current Features in Development

### Azure Container Apps OCR Service
**Status**: Planning Phase  
**Location**: `azure_container_apps_ocr/`  
**Objective**: Deploy existing OCR pipeline as scalable REST API service

## PDCA Workflow

Each feature follows the Plan → Do → Check → Act cycle with incremental implementation:

1. **Plan**: Detailed feature plan with incremental steps
2. **Do**: Implement smallest possible functional increment
3. **Check**: Validate and archive test evidence
4. **Act**: Commit changes and update tracking

## Directory Structure

```
feature_development/
  feature_name/
    FEATURE_PLAN.md           # PDCA plan with increments
    test_evidence/            # Validation results per increment
      increment_1/
      increment_2/
      ...
    deployment_scripts/       # Azure CLI automation (if applicable)
    sql_scripts/             # Database changes (if applicable)
```

## Getting Started

1. Review `CLAUDE.md` for full development methodology
2. Navigate to specific feature directory
3. Review `FEATURE_PLAN.md` for current status
4. Follow incremental implementation approach
5. Archive test evidence after each increment