"""Test script for verifying improved Resume Fit checker logic."""

import sys
from pathlib import Path

# Add project root to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import src.resume_fit as rf

# Mock resume texts for the three roles
SWE_RESUME = """
John Doe - Senior Developer
EXPERIENCE:
- Built web applications using ReactJS and state management.
- Backend systems engineered in Python and Golang.
- Managed container deployment using Postgres database.
- Designed CI/CD pipelines for automated deployments.
- Exposed to Kubernetes orchestration and Docker containers.
"""

CYBER_RESUME = """
Jane Smith - Cybersecurity Analyst
EXPERIENCE:
- Monitored network security logs using Security Information and Event Management (SIEM) solutions.
- Conducted penetration testing and threat hunting across enterprise systems.
- Handled vulnerability scanning with Splunk.
- Followed OWASP guidelines for web security testing.
CERTIFICATIONS:
- CISSP, Security+
"""

DATA_RESUME = """
Bob Johnson - Data Analyst
EXPERIENCE:
- Wrote complex SQL queries to extract insights.
- Designed dashboards in PowerBI and Tableau.
- Processed large datasets using Pandas and NumPy.
- Built machine learning models for forecasting.
"""

# Monkeypatch extract_text_by_page and split_sections to use our mock text
current_mock_text = ""

def mock_extract_text_by_page(path):
    return [current_mock_text]

def mock_split_sections(name, path):
    return [{
        "document": name,
        "page": 1,
        "section_title": "Work Experience",
        "text": current_mock_text
    }]

def mock_rank_sections(sections, persona, job, top_n):
    return sections[:top_n]

rf.extract_text_by_page = mock_extract_text_by_page
rf.split_sections = mock_split_sections
rf.rank_sections = mock_rank_sections

# Define JDs
SWE_JD = """
Looking for a Senior Software Engineer. The candidate must have extensive experience in Python, Docker, and Kubernetes.
You will work on frontend systems using React and design database structures in PostgreSQL.
Familiarity with Node.js and CI/CD tools is a plus. PDF resume required.
"""

CYBER_JD = """
Looking for a Cybersecurity Specialist. Essential skills include SIEM tools (especially Splunk), OWASP, Burp Suite, and Threat Hunting.
Certifications such as CISSP, CEH, or OSCP are highly desired. Strong understanding of cryptography is required.
"""

DATA_JD = """
Seeking a Data Analyst to join our team. You must have advanced SQL query skills, experience with Tableau and Power BI for data visualization,
and the ability to process data using Pandas and NumPy. Exposure to machine learning algorithms and ETL data pipelines is beneficial.
"""

def test_scenario(name, jd, resume_text):
    global current_mock_text
    current_mock_text = resume_text
    
    print(f"=== TEST CASE: {name} ===")
    print(f"Job Description Sample:\n{jd.strip()}")
    print("-" * 40)
    
    # Run fit analyzer
    result = rf.analyze_resume_fit("mock_resume.pdf", Path("mock_resume.pdf"), jd)
    
    print(f"Match Category: {result['match_category']}")
    print(f"Match Score: {result['match_score']:.2f}%")
    print(f"Extracted Keywords: {result['matched_keywords'] + result['missing_keywords']}")
    print(f"Matched Keywords: {result['matched_keywords']}")
    print(f"Missing Keywords: {result['missing_keywords']}")
    print(f"Explanation: {result['explanation']}")
    print("Improvement Suggestions:")
    for sug in result['improvement_suggestions']:
        print(f"  * {sug}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    test_scenario("Software Engineering", SWE_JD, SWE_RESUME)
    test_scenario("Cybersecurity", CYBER_JD, CYBER_RESUME)
    test_scenario("Data Analytics", DATA_JD, DATA_RESUME)
