# DocIntel AI

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A production-quality document intelligence platform — collapsible navigation outlines, target viewpoint analysis, and resume match checking.**

DocIntel AI has been extended from a command-line tool into a full-scale document intelligence system. It offers a beautiful Notion-inspired sidebar SPA interface with light/dark modes, target-driven section queries, and a robust resume fit checker with automatic Google Form and Spreadsheet synchronization.

---

## Key Features

1. **Notion-Inspired Frontend SPA**: Completely rewritten in plain HTML, CSS, and Vanilla JS. It features a responsive sidebar layout, calm sand-gray tones, dynamic loading states, and a dark theme toggle. All technical language (like TF-IDF or JSON) has been removed in favor of user-first terminology.
2. **Document Navigator ("See what's inside")**: Drops a document, learns its font sizes and hierarchies, and generates an interactive, collapsible accordion tree outline with page numbers.
3. **Information Finder ("Find what matters")**: Performs keyword/sentence relevance ranking across multiple PDFs from a specific perspective or question. Results are displayed as cards categorized as **Best Match** and **Also Relevant**.
4. **Resume Matcher ("Will my resume fit?")**: Compares a resume PDF against a pasted job description. It extracts role-specific unigram and bigram skills (filtering out English stopwords and 108 recruitment-filler words), matches them against the text, classifies matching strength (**Strong**, **Moderate**, or **Weak Match**), and details a human explanation of the results.
5. **Durable Analytics**: Tracks processed documents, resume checks, daily usage, and workflow breakdowns. It automatically uses **Vercel KV / Upstash Redis** in production via lightweight HTTPS REST calls (no heavy binary client dependencies) and falls back to **SQLite** (`docintel.db`) in local development.
6. **Activity Log & Local History**: Saves the last 10 transactions in `localStorage`, letting users click and restore previous analyses instantly.
7. **Google Sheets Ops Dashboard**: Auto-analyzes incoming resumes submitted through a Google Form, processes them via the Vercel API, and displays results, missing skills, and color-coded match scores in a spreadsheet.

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

---

## Local Development Setup

To run the application locally:

1. **Activate the environment**:
   Using the stable pyenv Python environment:
   ```bash
   /Users/shouryatuhar/.pyenv/versions/3.11.9/bin/python3 -m pip install -r requirements.txt
   ```

2. **Start the API Server**:
   Run uvicorn in the workspace directory (with reload enabled):
   ```bash
   export PYTHONPATH=src
   /Users/shouryatuhar/.pyenv/versions/3.11.9/bin/uvicorn src.api:app --reload
   ```

3. **Open the App**:
   Navigate to `http://127.0.0.1:8000/` to interact with the full SPA dashboard.

---

## Production Deployment on Vercel

The backend integrates FastAPI with Vercel serverless functions (`@vercel/python`).

1. **Routing**: `vercel.json` maps all paths matching `/api/*` to the function `api/index.py` (which imports `src.api.app`). All other paths serve the frontend index statically from `/public/index.html`.
2. **Database Setup**: Connect Vercel KV or Upstash Redis to your Vercel project. Vercel automatically populates the `KV_REST_API_URL` and `KV_REST_API_TOKEN` environment variables, routing analytics to your cloud database automatically.
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
2. Paste the contents of [scripts/apps_script.js](file:///Users/shouryatuhar/Downloads/docintel-ai-main/scripts/apps_script.js).
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

The Ops dashboard sheet is configured with the following reporting features:

1. **Most Missing Skills Report**: Place this formula in your Dashboard sheet to parse missing skills, count them, and sort by highest occurrence:
   ```formula
   =QUERY(ARRAYFORMULA(TRIM(FLATTEN(SPLIT(Submissions!H2:H, ",")))), "select Col1, count(Col1) where Col1 is not null group by Col1 order by count(Col1) desc label Col1 'Skill', count(Col1) 'Missing Count'")
   ```
2. **Conditional Formatting**: Apply a color scale to the `Match Score` column (Column I):
   * **Red** (< 40%): Background `#FEE2E2`, Text `#991B1B`
   * **Yellow** (40% - 70%): Background `#FEF3C7`, Text `#92400E`
   * **Green** (> 70%): Background `#DCFCE7`, Text `#166534`
