# Mistral OCR Pipeline

This project provides OCR processing pipelines with Azure Blob Storage integration and multiple processing options.

## Available Scripts

### 1. Local File Processing
- `main.py` - Process local PDFs with Azure Document Intelligence or Mistral OCR
- `analyze_content_understanding.py` - Process single files with Content Understanding API

### 2. Azure Blob Storage Integration
- `upload_to_blob.py` - Upload local files to Azure Blob Storage
- `analyze_content_understanding_blob_batch.py` - Process all PDFs in blob container

## Setup

1. Create `.env` with:
   ```ini
   # For local processing
   AZURE_DI_ENDPOINT=https://<your-azure-endpoint>
   AZURE_DI_API_KEY=<your-azure-key>
   AZURE_MISTRAL_OCR_ENDPOINT=<your-mistral-endpoint>
   AZURE_MISTRAL_OCR_API_KEY=<your-mistral-key>
   
   # For Content Understanding API
   AIFOUNDARY_API_ENDPOINT=<your-endpoint>
   AIFOUNDARY_API_KEY=<your-key>
   ```

2. Configure blob storage in `analyze_content_understanding_blob_config.yaml`:
   ```yaml
   blob_container_url: "https://your-storage.blob.core.windows.net/container"
   sas_token: "your-sas-token-with-rwc-permissions"
   analyzer_id: "prebuilt-documentAnalyzer"
   ```

3. Install dependencies:
   ```bash
   pip install python-dotenv pyyaml azure-ai-documentintelligence azure-storage-blob pymupdf httpx
   ```

## Usage

### Upload files to blob storage:
```bash
python upload_to_blob.py ./input/myfile.pdf
python upload_to_blob.py ./input/myfile.pdf custom-name.pdf
```

### Process all PDFs in blob container:
```bash
python analyze_content_understanding_blob_batch.py
```

### Process local files:
```bash
python main.py  # Uses config.yaml
python analyze_content_understanding.py <path-to-pdf>
```

## Outputs

- **JSON logs**: `./sow/outputs/logs/`
- **Markdown**: `./sow/outputs/markdown/`  
- **Styled HTML**: `./sow/outputs/html/`
