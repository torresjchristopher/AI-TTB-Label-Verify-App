# TTB LabelVerify

**Local-first OCR, normalization, comparison, and human review for alcohol-label applications.**

TTB LabelVerify is a modular proof of concept for accelerating repetitive alcohol-label review. The same OCR and rules engine is exposed through three interchangeable interfaces:

- **CLI** for scripting, folder processing, benchmarking, and secure terminal-only use.
- **TUI** for a guided terminal workflow without running a web server.
- **Web interface** for larger teams that need saved comparison profiles, batch upload, visual exception review, and manual approve/deny decisions.

All three formats use the same underlying processing pipeline. Changing the interface does not change the OCR model, normalization rules, field-matching behavior, or exported results.

---

## Local-first security model

The most secure deployment mode is local execution through PowerShell or a terminal on an approved workstation.

In local mode:

- No cloud account is required.
- No required cloud OCR API calls in normal operation; OCR and compliance run client-side.
- No backend database in this prototype; operational data is session-local in browser context.
- No external API keys required for core scanning flow.
- OCR inference runs on the workstation CPU.
- Images are not sent to a third-party AI API.
- The web interface binds to `127.0.0.1` by default rather than exposing itself to the network.
- Extracted text and reports remain in local output directories.
- The CLI can be used without starting any HTTP server.
- The application can operate behind restrictive outbound-firewall policies once dependencies and models are installed.
- Designed for restricted network environments where outbound ML endpoints may be blocked.

Local-only operation reduces external data exposure, but it does not by itself establish federal production compliance. A production deployment would still require agency review of access control, audit logging, records retention, encryption, workstation configuration, vulnerability management, and authorization requirements.

### CLI

The CLI is the smallest and most automation-friendly format with the absolute lowest security vulnerabilities along with the TUI. It is appropriate for:

- Processing entire folders
- Scheduled or scripted jobs
- Performance benchmarking
- Server environments
- Restricted workstations where a browser interface is unnecessary

### TUI

The TUI exposes the same capabilities through a guided terminal menu easier to navigate for audiences:

1. Edit Label
2. Process Batch
3. Quit

It adds no graphical framework and uses Python's standard terminal input/output.

### Web interface

The web edition runs locally on `127.0.0.1` and is intended for broader operational use with accesibility for audiences with limited technological fluency. It adds:

- Reusable label profiles
- Multi-image upload
- Worker selection
- Visual exception review
- Manual approve/deny decisions
- Downloadable CSV and JSON reports

The web interface is not a separate AI implementation. It calls the same local pipeline used by the CLI and TUI.

---

## Installation

### Recommended: reuse the working ONNX environment

Copy an existing working `.venv` folder into this project, then run:

```powershell
.\.venv\Scripts\python.exe run_web.py
```

Open:

```text
http://127.0.0.1:8000
```

### Full Windows installation

From PowerShell inside the project folder:

```powershell
py -3.8 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --no-cache-dir -r requirements.txt
python run_web.py
```

### Stop the local web server

Return to PowerShell and press:

```text
Ctrl+C
```

---

## Running each interface

### Web

```powershell
.\.venv\Scripts\python.exe run_web.py
```

### TUI

```powershell
.\.venv\Scripts\python.exe labelscan_tui.py
```

### CLI self-test

```powershell
.\.venv\Scripts\python.exe labelscan_cli.py self-test
```

### CLI folder scan

```powershell
.\.venv\Scripts\python.exe labelscan_cli.py scan "C:\path\to\labels" --limit 50 --workers 2
```

### Difficult-image scan

```powershell
.\.venv\Scripts\python.exe labelscan_cli.py scan "C:\path\to\labels" --limit 50 --workers 2 --aggressive
```

---

## Outputs

Each completed batch can produce:

- `results.csv` — field-level comparison results
- `results.json` — full structured results
- `summary.json` — aggregate counts and timing
- `text/` — raw OCR text for each image
- `review-decisions.csv` — manual approve/deny decisions
- `review-decisions.json` — structured manual decisions

Reports include the original filename, application/profile identifier, processing status, overall result, elapsed time, OCR confidence, field status, expected value, detected evidence, confidence, and reason.

---

### Local First Ease, Security, and Accesibility:

In a centralized on-premises deployment, only the designated office server or workstation needs Python, ONNX Runtime, the OCR models, and the application dependencies installed. Staff members would use their normal browsers to access the app over the internal network; they would not each install the software. This means only 1 install of dependencies, no installs across the office by employees varying in cybersecurity skill-level, no malformed downloads, simple and easy performance. 

The office-wide mode will remain local to the organization’s network, but it also needs IT-managed firewall rules, authentication, HTTPS, access controls, backups, and audit policy before production use. With a central office deployment, only the designated server or main workstation needs the dependencies installed. Everyone else can access the application through a browser over the internal network. They would not need Python, ONNX Runtime, OCR models, or a copy of the repository on their computers.

This means the local first option is also the most secure and easiest to install using a centralized local computer system without any third-party internet access is the most secure. 

This app runs like that without any third-party internet connection required after download. 


### Non-Local-First for Demo Purposes:

https://torresjchristopher-ai-ttb-label-verify-app-demo.hf.space

## Why this exists

TTB LabelVerify automates the high-volume extraction and comparison work while preserving human review for ambiguous images, nuanced wording, and uncertain evidence.


---

## Two-step web workflow

### 1. Edit Label

Create reusable comparison profiles containing the expected application values:

- Application ID
- Brand name
- Class/type
- Alcohol content
- Net contents
- Producer/bottler
- Producer address
- Country of origin
- Imported status

Profiles are stored by the local application and immediately become available in the batch-processing selector. An image filename is not required because one profile may be used to evaluate one or many submitted images.

### 2. Process Batch

Upload one image or a batch, then choose:

- A saved comparison profile or **Generic TTB Scan**
- **1–4 OCR workers**
- Optional **Aggressive recovery** for difficult images

The results table displays status, OCR confidence, processing time, and the fields responsible for review or failure.

- **Pass:** expected evidence is supported.
- **Review:** the image is clickable for full-size inspection and a manual approve/deny decision.
- **Fail:** a definite mismatch or required failure was detected. Confirmed automatic failures are locked and cannot be manually approved.

Manual decisions are exported with timestamps in CSV and JSON form.

---

## Generic TTB Scan

When no comparison profile is selected, the application performs generic required-component identification instead of comparing against application values.

It checks for visible evidence of:

- Alcohol content or proof
- Net contents
- Government Warning

Missing information is routed to **Review**, not automatically failed, because a required item may be present on another label panel that was not included in the submitted image.

---

## OCR technology

TTB LabelVerify uses **RapidOCR** with **ONNX Runtime** for local CPU inference.

ONNX is the model-execution format and runtime; it is not the OCR model itself. RapidOCR supplies the trained text-detection, orientation, and recognition models. The pipeline performs three related tasks:

1. **Text detection** locates text regions in the image.
2. **Orientation classification** corrects rotated text where possible.
3. **Text recognition** converts the detected regions into characters and confidence scores.

The installed RapidOCR configuration uses compact PP-OCR-derived ONNX models. This avoids the much larger PaddlePaddle development and training dependency tree while retaining modern OCR inference capability.

### Recovery for difficult images

A fast first pass is used for normal images. When OCR confidence or text coverage is weak, the application can perform additional recovery passes:

- EXIF orientation correction
- Image resizing
- CLAHE contrast enhancement
- Sharpening
- Adaptive thresholding
- Likely label-region cropping
- Two-to-four-times crop upscaling
- Rotated neck-label scans
- Confidence-based deduplication of OCR results

**Aggressive recovery** forces these additional passes. It can improve extraction from small or low-contrast labels, but increases processing time.

No OCR system can reliably reconstruct characters that are absent from the source image because of insufficient resolution, severe blur, glare, obstruction, or an unsubmitted rear panel. Those cases are intentionally routed to review.

---

## One processing engine, three interfaces

The project is intentionally modular. Interface code is separated from the OCR and validation engine.

```text
Uploaded image or folder
        │
        ▼
Image validation and decoding
        │
        ▼
Preprocessing and label-region recovery
        │
        ▼
RapidOCR + ONNX Runtime
        │
        ▼
Text normalization and field extraction
        │
        ▼
Field-specific comparison and confidence rules
        │
        ▼
Pass / Review / Fail
        │
        ├── CLI reports
        ├── TUI workflow
        └── Web review interface
```


### Field-specific rules

Different fields require different comparison behavior:

- **Brand names:** case and ordinary punctuation are normalized. A minor OCR difference such as `CASAMIGO` versus `CASAMIGOS` is routed to Review rather than automatically failed.
- **Class/type:** expected terms may appear on separate OCR lines. Full expected-token coverage passes; partial coverage routes to Review or Fail according to threshold.
- **ABV and proof:** values are parsed numerically. Proof may be converted to ABV. Material numerical differences remain strict failures.
- **Net contents:** units are normalized to milliliters before comparison. `0.75 L` and `750 mL` are equivalent.
- **Government Warning:** the exact capitalized heading is checked separately from fuzzy body-phrase recovery. Boldness and physical type size still require visual confirmation.
- **Country of origin:** evaluated only for records marked as imported.

### Human-in-the-loop control

The system separates uncertainty from confirmed contradiction:

- Missing or low-confidence evidence becomes **Review**.
- A clear numeric or textual contradiction becomes **Fail**.
- Review images can be opened and manually approved or denied.
- Confirmed machine failures remain locked to prevent an accidental approval through the review interface.

This design reduces false-positive failures without weakening strict comparison where the evidence is definitive.

### Concurrent workers

The worker setting controls how many separate images are processed concurrently.

- **1 worker:** lowest CPU and memory use
- **2 workers:** recommended default on typical workstations
- **3–4 workers:** potentially higher throughput on higher-core machines

Workers do not increase the accuracy of a single image. They increase batch throughput by allowing multiple images to be evaluated at the same time. Scaling is not perfectly linear because workers share CPU cores, memory bandwidth, and RAM.

---

## Measured prototype behavior

The local proof tests established that:

- ONNX Runtime loaded all OCR models successfully.
- The generated self-test completed without processing errors.
- The self-test correctly matched brand, class/type, ABV, net contents, and Government Warning evidence.
- Real product images completed in approximately **3.9–8.1 seconds per image** in the observed two-image test.
- The final automated test suite passes **15 tests** covering normalization, matching, generic scan behavior, web health, and review workflow.

Run the tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected result for the packaged version:

```text
15 passed
```

Observed timings are prototype measurements on one workstation and are not performance guarantees for other hardware or image sets.

---

## Estimated operational impact

The estimates below use stakeholder-provided workload assumptions, not independently audited production measurements:

- **150,000 applications per year**
- **10–15 minutes of manual review per application**
- **47 reviewing agents**

### Current manual workload

```text
150,000 × 10 minutes = 25,000 staff hours per year
150,000 × 15 minutes = 37,500 staff hours per year
```

That equals approximately:

- **532–798 hours per agent per year**
- **10.2–15.3 hours per agent per week**
- **12.0–18.0 full-time-equivalent years of annual capacity** at 2,080 hours per FTE

These figures represent review capacity, not a recommendation to reduce staffing. Recovered capacity could be redirected to complex applications, escalations, quality assurance, applicant communication, and policy work.

### Raw batch-processing throughput

At the observed prototype range of roughly **5–8 seconds per image**:

- One worker can theoretically perform approximately **450–720 OCR scans per hour**.
- Two concurrent workers can theoretically perform approximately **900–1,440 OCR scans per hour**, subject to hardware contention.
- Manual review at 10–15 minutes per application processes approximately **4–6 applications per hour**.

Therefore, the **machine extraction and comparison stage alone** has a theoretical raw throughput advantage of approximately **75×–360×** over sequential manual review.

This is not the same as claiming the complete regulatory workflow is 75–360 times faster. Human exception handling, image preparation, missing panels, and nuanced regulatory review still consume time.

### Example 50-image batch

Manual processing:

```text
50 × 10–15 minutes = 8.3–12.5 staff hours
```

Estimated local OCR processing with two workers at 5–8 seconds per image:

```text
Approximately 2.1–3.3 minutes of machine elapsed time
```

The resulting queue allows agents to focus primarily on exceptions rather than performing every extraction and comparison manually.

### Illustrative annual labor savings

Actual savings depend on the percentage of applications that can be confidently triaged and the amount of human confirmation retained. The following scenarios are illustrative rather than contractual forecasts.

| Scenario | Estimated annual hours recovered | Capacity recovered | Value at $50 loaded labor/hour |
|---|---:|---:|---:|
| 50% of routine review time avoided | 12,500–18,750 | 6.0–9.0 FTE-years | $625,000–$937,500 |
| 80% routine triage, with 30-second pass confirmation and 3-minute exception review | 22,500–35,000 | 10.8–16.8 FTE-years | $1.125M–$1.750M |

For a different loaded hourly cost, use:

```text
Estimated annual value = verified staff hours recovered × loaded hourly labor cost
```

At a loaded labor range of **$40–$80 per hour**, the second illustrative scenario corresponds to approximately **$900,000–$2.8 million per year** in recovered review capacity.

These values exclude deployment, validation, security assessment, support, training, hardware, and ongoing quality-control costs. A controlled pilot with representative labels is required before using them as a budget forecast.



## Current scope and limitations

- The prototype does not integrate directly with COLAs Online.
- Potential AI API upscaling of poor quality images.
---

## Project status

The packaged prototype has a functioning local OCR pipeline, deterministic normalization and matching, CLI/TUI/web modularity, concurrent batch processing, generic required-component scanning, exception review, and manual decision export. With more data, more workflow context, and more data to train on, I could hone in on pain points, performance, and truly train the software to adapt to the workflow in full production, however, this demo highlights the technologies in action with a solution designed for local only implementation and maintenance. 
