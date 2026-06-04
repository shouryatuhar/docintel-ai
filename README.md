# DocIntel AI

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Offline, CPU-only PDF intelligence — heading extraction and persona-driven section ranking**

DocIntel AI turns PDF collections into structured JSON: hierarchical outlines for navigation, or ranked sections tailored to a user persona and task. It runs fully on CPU with no network calls—ideal for air-gapped environments, batch pipelines, and reproducible document workflows.

Live app: [https://docintel-ae3ewvnlr-shouryatuhars-projects.vercel.app](https://docintel-ae3ewvnlr-shouryatuhars-projects.vercel.app)

---

## How it works

Two modes share the same font-analysis core; persona mode adds TF-IDF ranking.

```
                    ┌─────────────────────────────────────┐
                    │           DocIntel AI CLI           │
                    │     --mode outline | persona        │
                    └─────────────────┬───────────────────┘
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
    ┌──────────────────┐                          ┌──────────────────┐
    │  OUTLINE MODE    │                          │  PERSONA MODE    │
    │  PDFs in /input  │                          │  PDFs + manifest │
    └────────┬─────────┘                          └────────┬─────────┘
             │                                             │
             ▼                                             ▼
    ┌──────────────────┐                          ┌──────────────────┐
    │ outline_extractor│                          │ pdf_reader         │
    │ font thresholds  │                          │ section_splitter   │
    │ heading merge    │                          │ relevance_scorer   │
    └────────┬─────────┘                          │ output_formatter   │
             │                                    └────────┬─────────┘
             ▼                                             ▼
    ┌──────────────────┐                          ┌──────────────────┐
    │  per-PDF JSON      │                          │ challenge1b_     │
    │  title + outline   │                          │ output.json      │
    └──────────────────┘                          └──────────────────┘
```

---

## Quick start

```bash
git clone <your-repo-url> docintel-ai && cd docintel-ai
docker build -t docintel-ai .
docker run --rm -v "$(pwd)/samples/input:/data/input" -v "$(pwd)/samples/output:/data/output" \
  docintel-ai --mode outline --input /data/input --output /data/output
```

Persona mode (collection folder must include `challenge1b_input.json`):

```bash
docker run --rm -v "$(pwd)/samples/persona:/data/input" -v "$(pwd)/samples/persona/output:/data/output" \
  docintel-ai --mode persona --input /data/input --output /data/output
```

Or use Compose:

```bash
docker compose run --rm outline
docker compose run --rm persona
```

---

## Architecture

| Module | Role |
|--------|------|
| `src/main.py` | CLI entrypoint, logging, error handling |
| `src/heading_logic.py` | Font profiling, thresholds, heading merge helpers |
| `src/outline_extractor.py` | Outline extraction and classified line iteration |
| `src/pdf_reader.py` | Page-level text extraction |
| `src/section_splitter.py` | Sections via shared heading logic |
| `src/relevance_scorer.py` | TF-IDF + cosine similarity ranking |
| `src/output_formatter.py` | Schema-aligned persona output JSON |

See [docs/approach.md](docs/approach.md) for the full technical narrative.

---

## Why this works

**Font analysis beats regex for structure.** PDFs encode hierarchy in font size and weight, not markdown syntax. DocIntel learns each document’s size distribution, then labels lines as H1–H3 using thresholds, bold cues, and common section keywords—so outlines stay accurate across flyers, manuals, and reports without hand-tuned rules per template.

**Persona mode is search without a search engine.** The persona and job description form a query; each section becomes a document in a tiny corpus. TF-IDF highlights distinctive terms (e.g. “gluten-free”, “onboarding forms”) while down-weighting boilerplate. Cosine similarity ranks sections by intent alignment—fast, interpretable, and small enough to ship in a single container.

**Production-minded defaults.** One Dockerfile, one requirements file, graceful skips for corrupt PDFs, and timestamped logs make the tool easy to demo, test in CI, and drop into existing ETL jobs.

---

## Project layout

```
docintel-ai/
├── README.md
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── src/
│   ├── main.py
│   ├── outline_extractor.py
│   ├── pdf_reader.py
│   ├── section_splitter.py
│   ├── relevance_scorer.py
│   └── output_formatter.py
├── samples/
│   ├── input/          # outline mode PDFs
│   ├── output/         # outline JSON results
│   └── persona/        # persona mode collection
└── docs/
    └── approach.md
```

---

## Local development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install fpdf2  # optional: regenerate sample PDFs
python scripts/generate_sample_pdfs.py

export PYTHONPATH=src
python src/main.py --mode outline --input samples/input --output samples/output
python src/main.py --mode persona --input samples/persona --output samples/persona/output
```

---

## License

MIT — see [LICENSE](LICENSE).
