# DocIntel AI

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A PDF analysis app with page-linked document maps, relevance-ranked sections, and resume-to-job keyword matching.**

DocIntel AI combines a FastAPI service, a browser interface, and an offline CLI. Its analysis uses PDF text/layout extraction and TF-IDF ranking; resume scores are keyword coverage indicators, not hiring recommendations. The Sheets script is an optional integration that must be installed and configured by the operator.

---

## Key Features

1. **Notion-Inspired Frontend SPA**: Completely rewritten in plain HTML, CSS, and Vanilla JS. It features a responsive sidebar layout, calm sand-gray tones, dynamic loading states, and a dark theme toggle. All technical language (like TF-IDF or JSON) has been removed in favor of user-first terminology.
2. **Document Map**: Extracts section labels and short excerpts, then lets users jump to the referenced page in an in-browser PDF preview. Heading detection is heuristic and works best on text PDFs with clear formatting.
3. **Information Finder ("Find what matters")**: Performs keyword/sentence relevance ranking across multiple PDFs from a specific perspective or question. Results are displayed as cards categorized as **Best Match** and **Also Relevant**.
4. **Resume Matcher ("Will my resume fit?")**: Compares a resume PDF against a pasted job description using a curated skill list and text heuristics. The score measures weighted keyword coverage; it does not assess experience quality or predict hiring outcomes.
5. **Usage Analytics**: Tracks analysis attempts, resume checks, daily usage, and workflow breakdowns. Configure Upstash Redis REST credentials for shared production storage. Local SQLite is intended for development; serverless `/tmp` storage is ephemeral. Metrics are usage counts, not unique users.
6. **Activity Log & Local History**: Saves the last 10 transactions in `localStorage`, letting users click and restore previous analyses instantly.
7. **Google Sheets Ops Dashboard**: Auto-analyzes incoming resumes submitted through a Google Form, processes them via the Vercel API, and displays results, missing skills, and color-coded match scores in a spreadsheet.
8. **Invoice Review Assistant**: Extracts labeled invoice / purchase-order fields and compares vendor, PO number, line items, and invoice total. Every finding includes source text and page references; unsupported layouts are marked for manual review. This is a rule-based prototype, not an accounting approval system.

---

## Project Layout

```
docintel-ai/
├── README.md
├── vercel.json                 # Vercel serverless deployment config
├── Dockerfile                  # Offline CPU processing container
├── docker-compose.yml
├── requirements.txt            # Python dependencies
├── src/
│   ├── api.py                  # FastAPI serverless endpoints
│   ├── invoice_review.py       # Invoice / PO extraction and evidence checks
│   ├── resume_fit.py           # Skill extraction, matching, and scoring
│   ├── database.py             # Redis / SQLite analytics layer
│   ├── pdf_reader.py           # PDF parsing utilities
│   ├── section_splitter.py     # Font-based heading section splitter
│   ├── relevance_scorer.py     # TF-IDF relevance scorer
│   └── output_formatter.py     # Data packaging and sentence trim
├── frontend/
│   └── index.html              # Redesigned SPA (FastAPI entrypoint)
├── public/
│   └── index.html              # Redesigned SPA (Vercel static entrypoint)
├── scripts/
│   └── apps_script.js          # Google Apps Script project code
└── docs/
    └── approach.md
```

### Try the invoice review demo

The synthetic invoice pair uses explicit labels and a deliberately overpriced toner line. Generate the sample PDFs with `python scripts/generate_sample_pdfs.py`, then upload `samples/invoice_review/invoice.pdf` and `samples/invoice_review/purchase_order.pdf` in **Invoice Review**. Expected checks: vendor and PO number match; toner unit price and invoice total exceed the PO. The prototype currently expects selectable-text PDFs and explicitly labeled line items in the format shown in the sample generator; other layouts may be marked for manual review.

---

## Local Development Setup

To run the application locally:

1. **Create an environment and install dependencies** (Python 3.11):
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

2. **Start the API Server**:
   Run uvicorn in the workspace directory (with reload enabled):
   ```bash
   uvicorn src.api:app --reload
   ```

3. **Open the App**:
   Navigate to `http://127.0.0.1:8000/` to interact with the full SPA dashboard.

---

## Production Deployment on Vercel

The backend integrates FastAPI with Vercel serverless functions (`@vercel/python`).

1. **Routing**: Vercel detects the FastAPI app exported from `src/index.py` and serves its routes directly. Static assets in `public/` are served by Vercel; the app page is also available from the FastAPI root route for local development.
2. **Database Setup**: Configure `KV_REST_API_URL` and `KV_REST_API_TOKEN` in the deployment environment with your Upstash Redis REST credentials. Without these values, SQLite may be used and serverless data will not be durable.
3. **Trigger Build**: Push your main branch to GitHub:
   ```bash
   git add .
   git commit -m "feat: complete document intelligence extension"
   git push origin main
   ```

---

## Google Sheets Integration

Follow these steps to synchronize incoming resume submissions:

### 1. Form & Sheet Layout
Create a Google Form with fields: **Name**, **Email**, **Resume** (File Upload), and **Job Description**. Link the Form to a Google Sheet. Ensure the Submissions sheet contains the following columns:
1. `Timestamp`
2. `Name`
3. `Email`
4. `Resume File` (Google Drive share URL)
5. `Job Description` (pasted text)
6. `Status` (Set default dropdown values: `New`, `Processed`, `Reviewed`, `Followed Up`)
7. `Matched Keywords`
8. `Missing Keywords`
9. `Match Score` (formatted as Percentage inside the sheet)
10. `Notes`

### 2. Copy the Apps Script
1. In your Google Sheet, click **Extensions** -> **Apps Script**.
2. Paste the contents of [`scripts/apps_script.js`](scripts/apps_script.js).
3. Replace the `API_URL` variable with your Vercel deployment URL (e.g. `https://your-app.vercel.app/api/resume-fit`).
4. Click Save.

### 3. Set up the Trigger
1. Click the clock icon (**Triggers**) on the left toolbar of the Apps Script dashboard.
2. Click **+ Add Trigger**.
3. Select `processNewSubmissions` as the function to run.
4. Set event source to **Time-driven**, minutes timer, and select **Every 10 minutes**.
5. Save and authorize permissions.

---

## Dashboard Calculations

You can add the following reporting features to a separate Dashboard sheet:

1. **Most Missing Skills Report**: Place this formula in your Dashboard sheet to parse missing skills, count them, and sort by highest occurrence:
   ```formula
   =QUERY(ARRAYFORMULA(TRIM(FLATTEN(SPLIT(Submissions!H2:H, ",")))), "select Col1, count(Col1) where Col1 is not null group by Col1 order by count(Col1) desc label Col1 'Skill', count(Col1) 'Missing Count'")
   ```
2. **Conditional Formatting**: Apply a color scale to the `Match Score` column (Column I):
   * **Red** (< 40%): Background `#FEE2E2`, Text `#991B1B`
   * **Yellow** (40% - 70%): Background `#FEF3C7`, Text `#92400E`
   * **Green** (> 70%): Background `#DCFCE7`, Text `#166534`
