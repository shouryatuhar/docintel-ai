# Technical Approach

The CLI analysis pipeline is offline and CPU-only. The web app can optionally use Upstash Redis for analytics; PDF extraction and ranking themselves use local libraries and do not call cloud AI APIs.

## Outline mode

1. **Font profiling** — Walk every text line with pdfminer and count `(font name, size)` pairs to learn the document’s typographic scale.
2. **Thresholding** — Use the three most frequent font styles (font name and size) as dynamic H1/H2/H3 thresholds per document. This is a heuristic and can misclassify documents whose body font styles are unusually varied.
3. **Line classification** — Score each candidate line using font size, bold weight, and generic heading keywords (e.g. “Introduction”, “Summary”).
4. **Multi-line merge** — Combine consecutive lines that share size and bold styling when the merged title stays under 120 characters.
5. **Document map** — Return page-indexed section names and short excerpts. The browser pairs these references with a local PDF preview so users can jump to cited pages.

## Persona mode

1. **Ingest** — Read `challenge1b_input.json` (persona, job, optional document list) and parse each PDF page with `pdf_reader`.
2. **Sectioning** — Reuse the same font-based heading detector to split documents into sections with titles and body text.
3. **Ranking** — Build TF-IDF vectors for the persona + job query and each section body; rank by cosine similarity.
4. **Output** — Select the top five sections and write `challenge1b_output.json` with metadata, ranked section headers, and sentence-trimmed `refined_text` excerpts.

## Invoice review

The prototype extracts explicitly labeled invoice and purchase-order header fields, labeled totals, tax, and line-item rows from selectable PDF text. It compares vendor and PO identifiers, checks invoice amounts against the PO ceiling, and compares line-item quantities and unit prices. Each result retains the source snippet and PDF page. Missing or unsupported values become `needs_review`; the extractor does not guess values or approve payment. It currently targets a known, labeled text format and does not perform OCR.

## Design constraints

| Constraint | How it is met |
|------------|----------------|
| Offline analysis | CLI extraction and ranking use pdfminer + scikit-learn locally; optional web analytics can call Upstash Redis |
| CPU-only | No CUDA or neural inference |
| Small footprint | Dependencies stay under typical container limits |
| Graceful degradation | CLI skips corrupt PDFs with logged errors; web requests return an error for an invalid or unprocessable PDF |

## Extensibility

Embedding models (e.g. sentence-transformers) can replace TF-IDF ranking behind the same `relevance_scorer` interface. Heading detection can be augmented with column or margin heuristics without changing the CLI contract.
