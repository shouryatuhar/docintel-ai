"""Resume fit checker logic for comparing resumes against job descriptions."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from .output_formatter import trim_at_sentence_boundary
from .pdf_reader import extract_text_by_page
from .relevance_scorer import rank_sections
from .section_splitter import split_sections

# Global mappings to transfer state between extraction and analysis
_CASING_MAP: dict[str, str] = {}
_WEIGHTS_MAP: dict[str, float] = {}

# Pre-defined Skill Categories for Lexicon Matching
SKILL_CATEGORIES = {
    "Languages": {
        "python", "java", "javascript", "typescript", "go", "golang", "c", "c++", "c#", 
        "ruby", "php", "rust", "swift", "kotlin", "scala", "r", "html", "css", "sql", 
        "shell", "bash", "powershell"
    },
    "Frameworks": {
        "react", "reactjs", "angular", "vue", "svelte", "django", "flask", "fastapi", 
        "spring", "spring boot", "express", "next.js", "nextjs", "node.js", "nodejs", 
        "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "keras", "spark", 
        "hadoop"
    },
    "Databases": {
        "postgresql", "postgres", "mysql", "mongodb", "redis", "oracle", "sql server", 
        "sqlite", "cassandra", "dynamodb", "mariadb", "elasticsearch"
    },
    "Cloud": {
        "aws", "azure", "gcp", "google cloud", "heroku", "vercel", "netlify", "cloudflare", 
        "terraform", "ansible", "docker", "kubernetes", "k8s"
    },
    "Security": {
        "siem", "splunk", "owasp", "burp suite", "burpsuite", "wireshark", "metasploit", 
        "nmap", "cissp", "ceh", "cism", "oscp", "threat hunting", "penetration testing", 
        "pentesting", "vulnerability assessment", "threat modeling", "incident response", 
        "cryptography"
    },
    "Data": {
        "tableau", "power bi", "powerbi", "pandas", "spark", "numpy", "hadoop", 
        "data visualization", "data warehousing", "etl", "data pipelines", 
        "machine learning", "deep learning", "nlp", "computer vision", "statistics"
    },
    "Methodologies": {
        "agile", "scrum", "kanban", "devops", "devsecops", "ci/cd", "cicd", "tdd", 
        "bdd", "microservices", "rest", "restful", "graphql", "soa", "saas"
    }
}

# Consolidate all whitelist skills
ALL_SKILLS: set[str] = set()
for skills in SKILL_CATEGORIES.values():
    ALL_SKILLS.update(skills)

# Synonym mappings to resolve spelling differences
SYNONYM_MAP = {
    "postgres": ["postgresql", "postgres", "pgsql"],
    "postgresql": ["postgresql", "postgres", "pgsql"],
    "react": ["react", "reactjs", "react.js"],
    "reactjs": ["react", "reactjs", "react.js"],
    "node": ["nodejs", "node.js", "node"],
    "nodejs": ["nodejs", "node.js", "node"],
    "k8s": ["kubernetes", "k8s"],
    "kubernetes": ["kubernetes", "k8s"],
    "powerbi": ["power bi", "powerbi"],
    "power bi": ["power bi", "powerbi"],
    "typescript": ["typescript", "ts"],
    "javascript": ["javascript", "js"],
    "golang": ["go", "golang"],
    "go": ["go", "golang"]
}

# Acronym mapping for standard industry terms
ACRONYM_MAP = {
    "siem": ["security information and event management", "siem"],
    "owasp": ["open web application security project", "owasp"],
    "aws": ["amazon web services", "aws"],
    "api": ["application programming interface", "api", "apis"],
    "ml": ["machine learning", "ml"],
    "soc": ["security operations center", "soc"],
    "ci/cd": ["continuous integration", "continuous deployment", "ci/cd", "cicd"],
    "saas": ["software as a service", "saas"]
}

# Expanded blacklist of generic recruitment terms
GENERIC_WORDS = {
    "experience", "resume", "job", "work", "responsibilities", "requirements",
    "candidate", "role", "team", "skills", "ability", "successful", "opportunity",
    "year", "years", "working", "using", "knowledge", "design", "development",
    "developer", "engineer", "build", "support", "create", "manage", "lead",
    "deliver", "highly", "strong", "excellent", "written", "verbal", "communication",
    "degree", "computer", "science", "software", "applications", "systems",
    "project", "projects", "business", "technology", "technologies", "environment",
    "related", "field", "position", "preferred", "minimum", "required", "qualification",
    "qualifications", "duties", "roles", "candidates", "teams", "skill", "abilities",
    "join", "part", "company", "organization", "task", "tasks", "provide", "maintain",
    "implement", "collaborate", "industry", "practice", "practices", "standard",
    "standards", "professional", "professionals", "etc", "e.g.", "i.e.", "etc.",
    "new", "product", "products", "service", "services", "solution", "solutions",
    "client", "clients", "customer", "customers", "user", "users", "process",
    "processes", "method", "methods", "framework", "frameworks", "tool", "tools",
    "platform", "platforms", "architecture", "architectures", "infrastructure",
    "infrastructures", "data", "information", "key", "success", "goal", "goals",
    "result", "results", "value", "values", "growth", "learn", "learning", "grow",
    "career", "personal", "apply", "application", "cv", "resumes", "cover",
    "letter", "letters", "attach", "attachment", "upload", "submit", "submission",
    "link", "url", "email", "phone", "number", "address", "contact", "name",
    "profile", "summary", "objective", "education", "school", "university", "college",
    "diploma", "certificate", "certification", "course", "courses", "training",
    "trainings", "workshop", "workshops", "bootcamp", "bootcamps", "portfolio",
    "website", "github", "linkedin", "twitter", "facebook", "instagram", "social", "media",
    "looking", "seeking", "motivated", "passionate", "ideal", "plus", "track", 
    "record", "proven", "hands-on", "detail-oriented",
    # Added during implementation audit to aggressively screen false positives
    "expertise", "execution", "intelligence", "pdf", "expert", "quality", "integrity",
    "efficiency", "efficient", "optimization", "optimize", "implementation", "compliance",
    "policy", "policies", "reporting", "report", "reports", "operations", "operational",
    "strategy", "strategic", "planning", "plan", "plans", "stakeholder", "stakeholders",
    "excellence", "innovative", "innovation", "understanding", "capability", "capabilities",
    "concept", "concepts", "focus", "focused", "flexible", "flexibility", "ad-hoc", "ad hoc",
    "various", "day-to-day", "day to day", "high-quality", "high quality", "best-practice",
    "best practices", "best practice", "hands-on experience", "track record of",
    "proven track", "proven track record", "fast-paced", "fast paced", "dynamic",
    "collaborative", "cross-functional", "interpersonal", "written and verbal",
    "written communication", "verbal communication", "problem-solving", "problem solving",
    "analytical", "analysis", "analytics", "self-motivated", "proactive", "detail oriented",
    "results-oriented", "results oriented", "delivery", "management", "manager", "leadership",
    "member", "members", "staff", "associate", "analyst", "specialist", "advisor",
    "consultant", "director", "vp", "executive", "senior", "junior", "mid-level",
    "entry-level", "expert level", "domain", "domains", "area", "areas", "aspect",
    "aspects", "scope", "scopes", "level", "levels", "scale", "scales", "size",
    "sizes", "type", "types", "form", "forms", "format", "formats", "mode", "modes",
    "phase", "phases", "stage", "stages", "step", "steps", "activity", "activities"
}


def extract_keywords_from_job_desc(job_desc: str) -> list[str]:
    """Extract and prioritize specific technical role keywords using a hybrid strategy."""
    global _CASING_MAP, _WEIGHTS_MAP
    _CASING_MAP.clear()
    _WEIGHTS_MAP.clear()

    # 1. Exact whitelist scan (finds multi-word skills first, case-insensitively)
    text_lower = job_desc.lower()
    extracted_lexicon = set()
    for skill in ALL_SKILLS:
        if re.search(r"[\+#\-]", skill) or skill.startswith("."):
            pattern = re.escape(skill)
        else:
            pattern = rf"\b{re.escape(skill)}\b"

        if re.search(pattern, text_lower):
            extracted_lexicon.add(skill)

    # 2. Tokenize preserving case structure
    raw_tokens = job_desc.split()
    cleaned_tokens = []
    for token in raw_tokens:
        t = token
        # Strip outer punctuation, but preserve inner chars like dot, slash, plus, and hash
        t = re.sub(r'^[^a-zA-Z0-9.#+]+', '', t)
        t = re.sub(r'[^a-zA-Z0-9#+]+$', '', t)
        if t:
            cleaned_tokens.append(t)

    candidates: dict[str, float] = {}
    frequencies: dict[str, int] = {}
    casing_map: dict[str, str] = {}

    # Helper to clean token formatting for blacklist check
    def clean_lower(tok: str) -> str:
        return tok.lower().strip(".-")

    # Process unigrams
    for token in cleaned_tokens:
        tok_lower = clean_lower(token)
        if tok_lower in ENGLISH_STOP_WORDS or tok_lower in GENERIC_WORDS:
            continue
        if len(tok_lower) < 2 and tok_lower not in {"c", "r"}:
            continue
        if tok_lower.isdigit():
            continue

        confidence = 0.0
        if tok_lower in extracted_lexicon:
            confidence = 10.0
        else:
            # Check technical heuristics for unknown terms
            # A. Versioned technologies (e.g. Python3, React18, JUnit5)
            if re.match(r'^[a-zA-Z]+[-.]?\d+(\.\d+)*$', token):
                confidence = 5.0
            # B. Dot/slash technologies (e.g. Node.js, CI/CD, .NET)
            elif re.match(r'^\.?[a-zA-Z0-9]+[./][a-zA-Z0-9]+$', token) or re.match(r'^\.[a-zA-Z0-9]+$', token):
                confidence = 5.0
            # C. ALLCAPS acronyms (e.g. SIEM, AWS, SOC)
            elif re.match(r'^[A-Z]{2,6}$', token):
                confidence = 5.0
            # D. CamelCase/PascalCase (e.g. TypeScript, JavaScript)
            elif re.match(r'^[A-Z][a-z]+[A-Z][a-zA-Z0-9]*$', token):
                confidence = 5.0
            # E. General capitalized nouns (e.g. Docker, Splunk)
            elif re.match(r'^[A-Z][a-z0-9]+$', token):
                confidence = 3.0

        if confidence > 0.0:
            candidates[tok_lower] = max(candidates.get(tok_lower, 0.0), confidence)
            frequencies[tok_lower] = frequencies.get(tok_lower, 0) + 1
            
            # Save casing with highest capitalization complexity
            if tok_lower not in casing_map or sum(1 for c in token if c.isupper()) > sum(1 for c in casing_map[tok_lower] if c.isupper()):
                casing_map[tok_lower] = token

    # Process bigrams
    for i in range(len(cleaned_tokens) - 1):
        t1, t2 = cleaned_tokens[i], cleaned_tokens[i+1]
        bigram = f"{t1} {t2}"
        bigram_lower = bigram.lower()

        t1_lower, t2_lower = clean_lower(t1), clean_lower(t2)
        if t1_lower in ENGLISH_STOP_WORDS or t1_lower in GENERIC_WORDS:
            continue
        if t2_lower in ENGLISH_STOP_WORDS or t2_lower in GENERIC_WORDS:
            continue

        confidence = 0.0
        if bigram_lower in extracted_lexicon:
            confidence = 10.0
        else:
            # Heuristic for capitalized multi-word phrases (e.g. Threat Hunting, Burp Suite)
            if t1[0].isupper() and t2[0].isupper():
                confidence = 5.0
            # Versioned bigrams (e.g. Python 3.11, React 18)
            elif re.match(r'^[a-zA-Z]+$', t1) and re.match(r'^\d+(\.\d+)*$', t2):
                confidence = 5.0

        if confidence > 0.0:
            candidates[bigram_lower] = max(candidates.get(bigram_lower, 0.0), confidence)
            frequencies[bigram_lower] = frequencies.get(bigram_lower, 0) + 1
            if bigram_lower not in casing_map or sum(1 for c in bigram if c.isupper()) > sum(1 for c in casing_map[bigram_lower] if c.isupper()):
                casing_map[bigram_lower] = bigram

    # Ensure whitelisted terms caught via exact scan are included
    for skill in extracted_lexicon:
        if skill not in candidates:
            candidates[skill] = 10.0
            frequencies[skill] = text_lower.count(skill)
            match_casing = re.search(rf"\b{re.escape(skill)}\b", job_desc, re.IGNORECASE)
            casing_map[skill] = match_casing.group(0) if match_casing else skill.title()

    # Calculate final weights: weight = confidence * min(frequency, 3)
    scored_candidates = []
    for token, confidence in candidates.items():
        freq = frequencies.get(token, 1)
        weight = confidence * min(freq, 3)
        scored_candidates.append((token, weight))

    # Sort descending by weight
    scored_candidates.sort(key=lambda x: x[1], reverse=True)

    # De-duplicate unigrams that are parts of selected bigrams
    selected_keywords: list[str] = []
    for token, _ in scored_candidates:
        if len(selected_keywords) >= 20:
            break

        is_redundant = False
        if " " not in token:
            for selected in selected_keywords:
                if " " in selected and token in selected.split():
                    is_redundant = True
                    break
        if not is_redundant:
            selected_keywords.append(token)

    # Save state to global mapping variables
    for token, weight in scored_candidates:
        if token in selected_keywords:
            _WEIGHTS_MAP[token] = weight
            _CASING_MAP[token] = casing_map.get(token, token.title())

    return selected_keywords


def check_keyword_in_text(keyword: str, text: str) -> bool:
    """Case-insensitive synonym-aware check for keyword presence in text."""
    keyword_lower = keyword.lower()
    variants = [keyword_lower]

    if keyword_lower in SYNONYM_MAP:
        variants.extend([v.lower() for v in SYNONYM_MAP[keyword_lower]])
    if keyword_lower in ACRONYM_MAP:
        variants.extend([v.lower() for v in ACRONYM_MAP[keyword_lower]])

    variants = list(set(variants))
    text_lower = text.lower()

    for variant in variants:
        if " " in variant:
            if variant in text_lower:
                return True
        else:
            if re.search(r"[\+#\-]", variant) or variant.startswith("."):
                if variant in text_lower:
                    return True
            else:
                pattern = rf"\b{re.escape(variant)}\b"
                if re.search(pattern, text_lower):
                    return True
    return False


def generate_suggestions(
    missing_keywords_with_weights: list[tuple[str, float]], 
    casing_map: dict[str, str]
) -> list[str]:
    """Generate constructive resume improvement suggestions for missing keywords."""
    suggestions = []
    sorted_missing = sorted(missing_keywords_with_weights, key=lambda x: x[1], reverse=True)

    for kw_lower, _ in sorted_missing[:5]:
        display_name = casing_map.get(kw_lower, kw_lower.title())

        # Exact overrides based on user examples
        if kw_lower == "docker":
            suggestions.append("Highlight Docker deployment experience.")
            continue
        elif kw_lower in ("postgresql", "postgres"):
            suggestions.append("Add PostgreSQL projects if applicable.")
            continue
        elif kw_lower == "kubernetes":
            suggestions.append("Mention Kubernetes exposure if relevant.")
            continue

        # Look up categories
        categories = []
        for cat, skills in SKILL_CATEGORIES.items():
            if kw_lower in skills:
                categories.append(cat)

        if "Languages" in categories:
            suggestions.append(f"Detail your experience with {display_name} programming.")
        elif "Frameworks" in categories:
            suggestions.append(f"Highlight projects built with the {display_name} framework.")
        elif "Databases" in categories:
            suggestions.append(f"Add {display_name} database projects if applicable.")
        elif "Cloud" in categories:
            suggestions.append(f"Mention {display_name} cloud deployment or orchestration experience if relevant.")
        elif "Security" in categories:
            suggestions.append(f"Incorporate certifications or hands-on experience with {display_name}.")
        elif "Methodologies" in categories:
            suggestions.append(f"Reference your exposure to {display_name} methodologies.")
        elif "Data" in categories:
            suggestions.append(f"Showcase your analytics or visualization skills using {display_name}.")
        else:
            suggestions.append(f"Highlight your experience with {display_name} if applicable.")

    return suggestions


def generate_explanation(
    category: str,
    matched: list[str],
    missing: list[str],
    relevant_sections: list[dict[str, Any]]
) -> str:
    """Generate a cohesive, human-friendly explanation of why the resume matches."""
    if not matched and not missing:
        return "We couldn't identify any clear keywords to compare your resume against the role requirements."

    matched_title = [m for m in matched[:3]]
    missing_title = [m for m in missing[:3]]

    sections_str = ""
    if relevant_sections:
        top_sec = relevant_sections[0]["section_title"]
        if not top_sec.lower().startswith("page"):
            sections_str = f"Your resume has relevant information in the '{top_sec}' section."
        else:
            sections_str = f"Your resume contains highly aligned experience on Page {relevant_sections[0]['page_number']}."

    if category == "Strong Match":
        explanation = (
            f"Your resume shows exceptional alignment with this position. You demonstrate strong experience in key skill "
            f"areas like {', '.join(matched_title)}. {sections_str} "
        )
        if missing:
            explanation += f"To stand out even further, you might want to clarify your experience with {', '.join(missing_title)}."
        else:
            explanation += "Your background covers all critical requirements of the role."
    elif category == "Moderate Match":
        explanation = (
            f"Your resume shows moderate alignment. You match well on skills like {', '.join(matched_title)}. "
            f"However, the role strongly emphasizes skills like {', '.join(missing_title)}, which are currently missing "
            f"from your resume. {sections_str} We suggest emphasizing these missing skills if you have them."
        )
    else:
        explanation = (
            f"Your resume currently has low alignment with this position. "
        )
        if missing:
            explanation += (
                f"The job description highlights requirements like {', '.join(missing_title)} which aren't mentioned. "
            )
        explanation += (
            f"{sections_str} We recommend tailoring your resume to address these core skills if they correspond to your experiences."
        )

    return explanation


def analyze_resume_fit(
    resume_name: str,
    resume_path: Path,
    job_description: str
) -> dict[str, Any]:
    """Execute the complete resume fit checker pipeline with weighted matching."""
    # 1. Read entire text and split into sections
    pages = extract_text_by_page(resume_path)
    resume_text = " ".join(pages)

    # 2. Extract sections using font/heading logic
    sections = split_sections(resume_name, resume_path)
    if not sections:
        for idx, page_text in enumerate(pages, start=1):
            if page_text.strip():
                sections.append({
                    "document": resume_name,
                    "page": idx,
                    "section_title": f"Page {idx}",
                    "text": page_text
                })

    # 3. Match sections by relevance
    ranked_sections = rank_sections(sections, persona="", job=job_description, top_n=5)
    relevant_sections = []
    for sec in ranked_sections:
        relevant_sections.append({
            "section_title": sec["section_title"],
            "page_number": sec["page"],
            "refined_text": trim_at_sentence_boundary(sec["text"]),
        })

    # 4. Extract and check keywords
    keywords = extract_keywords_from_job_desc(job_description)
    matched_keywords = []
    missing_keywords = []

    for kw in keywords:
        if check_keyword_in_text(kw, resume_text):
            matched_keywords.append(kw)
        else:
            missing_keywords.append(kw)

    # 5. Score using weighted scoring
    def get_kw_weight(kw: str) -> float:
        if kw in _WEIGHTS_MAP:
            return _WEIGHTS_MAP[kw]
        # Fallback weight
        is_lexicon = kw in ALL_SKILLS
        max_w = 0.0
        if is_lexicon:
            for cat, skills in SKILL_CATEGORIES.items():
                if kw in skills:
                    if cat in ["Languages", "Frameworks", "Databases", "Cloud", "Security"]:
                        max_w = max(max_w, 3.0)
                    elif cat in ["Data", "Methodologies"]:
                        max_w = max(max_w, 2.0)
            if max_w == 0.0:
                max_w = 2.0
        else:
            max_w = 1.5
        return max_w

    sum_matched = sum(get_kw_weight(kw) for kw in matched_keywords)
    sum_missing = sum(get_kw_weight(kw) for kw in missing_keywords)
    total_weights = sum_matched + sum_missing
    score_pct = (sum_matched / total_weights) * 100 if total_weights > 0 else 0.0

    if score_pct >= 70.0:
        match_category = "Strong Match"
    elif score_pct >= 40.0:
        match_category = "Moderate Match"
    else:
        match_category = "Weak Match"

    # 6. Generate improvement suggestions
    missing_keywords_with_weights = [(kw, get_kw_weight(kw)) for kw in missing_keywords]
    improvement_suggestions = generate_suggestions(missing_keywords_with_weights, _CASING_MAP)

    # 7. Formulate nicely cased output lists
    matched_display = [_CASING_MAP.get(kw, kw.title()) for kw in matched_keywords]
    missing_display = [_CASING_MAP.get(kw, kw.title()) for kw in missing_keywords]

    # 8. Generate human description explanation
    explanation = generate_explanation(match_category, matched_display, missing_display, relevant_sections)

    return {
        "analysis_id": None,
        "match_category": match_category,
        "match_score": score_pct,
        "explanation": explanation,
        "matched_keywords": matched_display,
        "missing_keywords": missing_display,
        "relevant_sections": relevant_sections,
        "improvement_suggestions": improvement_suggestions
    }
