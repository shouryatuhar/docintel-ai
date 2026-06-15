import urllib.request
import urllib.parse
import json
import os
from pathlib import Path

BASE_URL = "http://127.0.0.1:8080"
PDF_PATH = "/Users/shouryatuhar/Downloads/docintel-ai-main/samples/input/demo_guide.pdf"

def make_request(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    req = urllib.request.Request(url, method=method, headers=headers)
    if data:
        req.data = data
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, res.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as e:
        return 0, str(e)

# Helper to construct multipart form data
def build_multipart_form(fields, files):
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = []
    
    for key, value in fields.items():
        body.append(f"--{boundary}")
        body.append(f'Content-Disposition: form-data; name="{key}"')
        body.append("")
        body.append(str(value))
        
    for key, file_path in files.items():
        file_path = Path(file_path)
        body.append(f"--{boundary}")
        body.append(f'Content-Disposition: form-data; name="{key}"; filename="{file_path.name}"')
        body.append("Content-Type: application/pdf")
        body.append("")
        with open(file_path, "rb") as f:
            body.append(f.read())
            
    body.append(f"--{boundary}--")
    body.append("")
    
    # Flatten the body list into bytes
    flat_body = b""
    for part in body:
        if isinstance(part, str):
            flat_body += part.encode("utf-8") + b"\r\n"
        else:
            flat_body += part + b"\r\n"
            
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    }
    return flat_body, headers

print("Starting verification audit against local server at " + BASE_URL)

# 1. GET /api/metrics (Baseline)
print("\n--- 1. Verification of GET /api/metrics (Baseline) ---")
status, response = make_request(f"{BASE_URL}/api/metrics")
print("HTTP Status Code:", status)
print("Response Payload:")
print(json.dumps(json.loads(response), indent=2))

baseline_metrics = json.loads(response)
baseline_docs = baseline_metrics.get("documents_analyzed", 0)
baseline_helped = baseline_metrics.get("users_helped", 0)

# 2. POST /api/outline
print("\n--- 2. Verification of POST /api/outline ---")
data, headers = build_multipart_form({}, {"file": PDF_PATH})
status, response = make_request(f"{BASE_URL}/api/outline", method="POST", data=data, headers=headers)
print("HTTP Status Code:", status)
print("Response Payload:")
print(json.dumps(json.loads(response), indent=2))

# 3. POST /api/persona
print("\n--- 3. Verification of POST /api/persona ---")
fields = {
    "persona": "Developer",
    "job": "Offline CPU execution and heading extraction."
}
data, headers = build_multipart_form(fields, {"files": PDF_PATH})
status, response = make_request(f"{BASE_URL}/api/persona", method="POST", data=data, headers=headers)
print("HTTP Status Code:", status)
print("Response Payload:")
print(json.dumps(json.loads(response), indent=2))

# 4. POST /api/resume-fit
print("\n--- 4. Verification of POST /api/resume-fit ---")
job_desc = "Looking for a software engineer with expertise in offline CPU execution, heading extraction, and PDF intelligence. Experience in Python is a plus."
fields = {
    "job_description": job_desc
}
data, headers = build_multipart_form(fields, {"resume": PDF_PATH})
status, response = make_request(f"{BASE_URL}/api/resume-fit", method="POST", data=data, headers=headers)
print("HTTP Status Code:", status)
print("Response Payload:")
fit_response = json.loads(response)
print(json.dumps(fit_response, indent=2))

analysis_id = fit_response.get("analysis_id")

# 5. POST /api/feedback (Thumbs Up)
print("\n--- 5. Verification of POST /api/feedback (Thumbs Up) ---")
payload = {
    "analysis_id": analysis_id,
    "useful": True
}
data = json.dumps(payload).encode("utf-8")
headers = {
    "Content-Type": "application/json"
}
status, response = make_request(f"{BASE_URL}/api/feedback", method="POST", data=data, headers=headers)
print("HTTP Status Code:", status)
print("Response Payload:")
print(json.dumps(json.loads(response), indent=2))

# 6. GET /api/metrics (Post-run checks)
print("\n--- 6. Verification of GET /api/metrics (Post-run checks) ---")
status, response = make_request(f"{BASE_URL}/api/metrics")
print("HTTP Status Code:", status)
print("Response Payload:")
new_metrics = json.loads(response)
print(json.dumps(new_metrics, indent=2))

new_docs = new_metrics.get("documents_analyzed", 0)
new_helped = new_metrics.get("users_helped", 0)

print("\n--- Verification Comparison ---")
print(f"Documents analyzed: Baseline={baseline_docs} -> New={new_docs} (Change = +{new_docs - baseline_docs})")
print(f"Users helped: Baseline={baseline_helped} -> New={new_helped} (Change = +{new_helped - baseline_helped})")

if new_docs > baseline_docs and new_helped > baseline_helped:
    print("\nVERIFICATION AUDIT COMPLETED SUCCESSFULLY: ALL CHECKS PASSED")
else:
    print("\nVERIFICATION AUDIT FAILED: Metrics did not increment correctly.")
