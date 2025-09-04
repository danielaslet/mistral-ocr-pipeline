
This readme file explains how to use the PDF to content understanding workflow:

⸻

📘 Azure Content Understanding Batch Processor

This project runs Azure Content Understanding against a batch of PDF files stored in an Azure Blob Storage container. It generates three output files per input:
	•	A Markdown version of the extracted content
	•	A Styled HTML version for human-friendly viewing
	•	A JSON log of the raw service response

⸻

📁 File Overview

1. analyze_content_understanding_blob_batch.py

This is the main script. It:
	•	Lists all .pdf files from an Azure Blob Storage container (optionally scoped to a folder prefix)
	•	Constructs URLs with a shared SAS token
	•	Sends each file to Azure Content Understanding
	•	Waits for the job to complete and downloads the result
	•	Extracts the raw Markdown and converts it to styled HTML
	•	Saves output files in structured folders

2. analyze_content_understanding_helpers.py

This contains shared helper functions to:
	•	Extract markdown from the raw API response
	•	Convert markdown to HTML with optional regex visualization rules
	•	Save markdown, HTML, and JSON log files

You should not need to modify this file.

3. analyze_content_understanding_blob_config.yaml

The configuration file used by the script. It lets you define:
	•	The blob container URL and optional folder prefix
	•	A shared SAS token (read+list permissions required)
	•	Analyzer ID to use (e.g., "prebuilt-documentAnalyzer")
	•	Output folders for Markdown, HTML, and JSON logs
	•	Optional regex-based HTML visualization rules

⸻

⚙️ How to Use

✅ Step 1: Prepare Your Files
	•	Upload your PDFs to an Azure Blob Storage container
	•	Make sure they’re readable with the SAS token

✅ Step 2: Configure the YAML

Update analyze_content_understanding_blob_config.yaml like so:

blob_container_url: "https://<account>.blob.core.windows.net/<container>"
prefix: ""  # or "some/folder" if using a virtual directory
sas_token: "sp=r&st=...&se=...&sv=...&sr=c&sig=..."

analyzer_id: "prebuilt-documentAnalyzer"

log_output_dir: ./outputs/logs
markdown_output_dir: ./outputs/markdown
html_output_dir: ./outputs/html

enable_visualization: true
visualization_rules:
  - condition: '(?m)<!--\\s*(.*?)\\s*-->'
    treatment: '<p style="color:blue;">--- COMMENT: \\1 ---</p>'

✅ Note: sas_token must have r (read) and l (list) permissions to work properly.

✅ Step 3: Run the Script

python analyze_content_understanding_blob_batch.py

The script will:
	•	List all .pdf files in the specified container/prefix
	•	Print how many files were found and their names
	•	Show progress using “(x of N)” while processing each file
	•	Save outputs with filenames matching the original PDF names:
	•	document.pdf → document.md, document.html, document.json

⸻

📂 Example Output Structure

outputs/
├── logs/
│   └── some_file.json
├── markdown/
│   └── some_file.md
└── html/
    └── some_file.html


⸻

💡 Notes
	•	HTML output includes styled tables and optional visual indicators based on regex rules
	•	File names in all outputs exactly match the input PDF name (only the extension changes)
	•	If you want to skip already-processed files or track progress in a manifest, this can be added

⸻

Let me know if you’d like to include automated upload of outputs back to Blob Storage, error handling summaries, or a CSV manifest of results.