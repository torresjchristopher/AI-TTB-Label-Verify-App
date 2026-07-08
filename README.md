# TTB LabelVerify — Review Web Edition

A local-only alcohol-label OCR and comparison application built for individual
or batch review. The browser interface runs on `127.0.0.1`; uploaded labels and
results remain on the local computer.

## Workflow

### 1. Edit Label

Create reusable comparison profiles containing expected application values:

- Application ID
- Brand name
- Class/type
- Alcohol content
- Net contents
- Producer/bottler
- Producer address
- Country of origin
- Imported status

### 2. Process Batch

Choose one image or a batch, then select:

- A saved comparison label or Generic TTB Scan
- 1–4 OCR workers
- Optional aggressive recovery

Workers process separate images concurrently. Two workers are the recommended
default for typical computers.

## Human review

After processing:

- **Pass** means the configured evidence was supported.
- **Review** means the image is clickable. The reviewer can inspect the full
  image, field-level findings, and OCR text, then manually approve or deny it.
- **Fail** means a definite mismatch or required failure was detected. Confirmed
  failures are locked as automatic failures and cannot be manually overridden.

Manual decisions are saved per batch and can be downloaded as
`review-decisions.csv` or `review-decisions.json`.

## Generic TTB Scan

When no comparison label is selected, the app checks visible required items such
as alcohol content, net contents, and Government Warning evidence. Missing
items are routed to Review because they may appear on another panel.

## Run with an existing environment

Copy the working `.venv` folder from the previous ONNX CLI into this folder,
then install the small web dependencies if they are not already present:

```powershell
.\.venv\Scripts\python.exe -m pip install fastapi==0.103.2 uvicorn==0.23.2 python-multipart==0.0.9
.\.venv\Scripts\python.exe run_web.py
```

Open:

```text
http://127.0.0.1:8000
```

## Full installation

```powershell
py -3.8 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --no-cache-dir -r requirements.txt
python run_web.py
```

## Outputs

Each completed batch provides:

- OCR and comparison results in CSV and JSON
- Batch summary JSON
- Extracted text files
- Manual decision CSV and JSON

## Safety behavior

The application is decision-support software. It does not issue a COLA or make
a final legal determination. It never converts unreadable evidence into an
automatic pass, and it prevents human approval from overriding a definite
machine-detected failure.
