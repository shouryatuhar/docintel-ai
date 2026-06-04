# Technical Approach

DocIntel AI is an offline, CPU-only pipeline for structured PDF understanding. It combines layout-aware font analysis with lightweight statistical ranking—no cloud APIs, no GPU, and no large language models.

## Outline mode

1. **Font profiling** — Walk every text line with pdfminer and count `(font name, size)` pairs to learn the document’s typographic scale.
2. **Thresholding** — Map the three most frequent body sizes to dynamic H1/H2/H3 thresholds per document.
3. **Line classification** — Score each candidate line using font size, bold weight, and generic heading keywords (e.g. “Introduction”, “Summary”).
4. **Multi-line merge** — Combine consecutive lines that share size and bold styling when the merged title stays under 120 characters.
5. **JSON export** — Emit `title` plus an `outline` array with level, text, and page number.

## Persona mode

1. **Ingest** — Read `challenge1b_input.json` (persona, job, optional document list) and parse each PDF page with `pdf_reader`.
2. **Sectioning** — Reuse the same font-based heading detector to split documents into sections with titles and body text.
3. **Ranking** — Build TF-IDF vectors for the persona + job query and each section body; rank by cosine similarity.
4. **Output** — Select the top five sections and write `challenge1b_output.json` with metadata, ranked section headers, and sentence-trimmed `refined_text` excerpts.

## Design constraints

| Constraint | How it is met |
|------------|----------------|
| Offline | pdfminer + scikit-learn only; no network calls |
| CPU-only | No CUDA or neural inference |
| Small footprint | Dependencies stay under typical container limits |
| Graceful degradation | Corrupt PDFs are skipped with logged errors |

## Extensibility

Embedding models (e.g. sentence-transformers) can replace TF-IDF ranking behind the same `relevance_scorer` interface. Heading detection can be augmented with column or margin heuristics without changing the CLI contract.
