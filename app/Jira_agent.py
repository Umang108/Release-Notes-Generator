import os
import re
import json
import uuid
import requests
from typing import Dict, Optional, Any

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib import colors

# ----------------------------
# ENV + LLM
# ----------------------------
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not found")

llm = ChatGroq(
    model="moonshotai/kimi-k2-instruct-0905",
    temperature=0,
    max_tokens=None,
    api_key=GROQ_API_KEY,
)

# -----------------------------
# A2A Metadata (NEW)
# -----------------------------
AGENT_ID = "jira-release-notes-agent"

A2A_META = {
    "agent_id": AGENT_ID,
    "name": "JIRA Release Notes Generator",
    "description": "Generates release notes PDF from Apache JIRA issues using project + version",
    "capabilities": ["jira_search", "summarize", "release_notes", "pdf_generate"]
}

# ----------------------------
# Extract project + version
# ----------------------------

def llm_extract_project_and_version(user_query: str) -> Optional[Dict[str, str]]:
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You extract structured data from user queries.\n"
         "Return ONLY valid JSON in this exact format:\n"
         "{{\n"
         '  "project": "<JIRA_PROJECT_KEY>",\n'
         '  "version": "<VERSION>"\n'
         "}}\n"
         "Rules:\n"
         "- Project must be uppercase\n"
         "- Version must match the user's query\n"
         "- NO extra text"),
        ("user", "{query}")
    ])

    chain = prompt | llm
    response = chain.invoke({"query": user_query})

    try:
        data = json.loads(response.content)
        if "project" in data and "version" in data:
            return {
                "project": str(data["project"]).strip().upper(),
                "version": str(data["version"]).strip()
            }
        return None
    except Exception:
        return None



# ----------------------------
# Tool-like functions (NO @tool)
# ----------------------------
def fetch_jira_issues(project: str, version: str) -> str:
    """
    Fetch all JIRA issues for the given project and fixVersion.
    """
    url = "https://issues.apache.org/jira/rest/api/2/search"
    params = {
        "jql": f"project = {project} AND fixVersion = {version}",
        "fields": "summary,issuetype",
        "startAt": 0,
        "maxResults": 50
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        issues = []
        for issue in data.get("issues", []):
            issues.append({
                "key": issue.get("key", ""),
                "summary": issue.get("fields", {}).get("summary", ""),
                "type": issue.get("fields", {}).get("issuetype", {}).get("name", "")
            })

        return json.dumps({
            "project": project,
            "version": version,
            "issues": issues
        })

    except Exception as e:
        return f"Error: {str(e)}"


def fetch_jira_version_info(project: str, version: str) -> str:
    """
    Fetch JIRA version metadata for the given project/version.
    """
    url = f"https://issues.apache.org/jira/rest/api/2/project/{project}/versions"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        versions = response.json()

        for v in versions:
            if v.get("name") == version:
                return json.dumps({
                    "release_date": v.get("releaseDate", "Unknown"),
                    "version": version,
                    "project": project
                })

        return json.dumps({
            "release_date": "Unknown",
            "version": version,
            "project": project
        })

    except Exception as e:
        return f"Error: {str(e)}"


def classify_and_summarize_issues(jira_data: str) -> str:
    """
    Dynamically classify JIRA issues by their issue type and summarize them.
    """
    try:
        data = json.loads(jira_data)

        project = data.get("project", "")
        version = data.get("version", "")
        issues = data.get("issues", [])

        categories = {}
        for issue in issues:
            issue_type = issue.get("type", "Uncategorized")
            summary = issue.get("summary", "")
            key = issue.get("key", "")

            categories.setdefault(issue_type, []).append(f"{key}: {summary}")

        categories = dict(sorted(categories.items()))

        return json.dumps({
            "project": project,
            "version": version,
            "categories": categories
        })

    except Exception as e:
        return f"Error: {str(e)}"


def format_release_notes(project: str, version: str, release_date: str, summarized_data: str) -> str:
    """
    Format dynamically categorized JIRA data into a professional release notes document.
    """
    try:
        data = json.loads(summarized_data)
        categories = data.get("categories", {})

        release_notes = f"# {project} Release {version}\n\n"
        release_notes += f"## Release Date\n{release_date}\n\n"

        total_issues = sum(len(v) for v in categories.values())
        release_notes += "## Summary\n"
        release_notes += f"- **Total Issues**: {total_issues}\n"
        for category, items in categories.items():
            release_notes += f"- **{category}**: {len(items)}\n"
        release_notes += "\n"

        for category, items in categories.items():
            if items:
                release_notes += f"## {category}\n"
                for item in items:
                    release_notes += f"- {item}\n"
                release_notes += "\n"

        return release_notes

    except Exception as e:
        return f"Error: {str(e)}"

# ----------------------------
# PDF generator
# ----------------------------
def save_to_pdf(text: str, output_path: str):
    """
    Convert release notes text into a styled PDF file.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Header1", fontSize=16, leading=18,
                              spaceAfter=8, textColor=colors.darkblue))
    styles.add(ParagraphStyle(name="Header2", fontSize=12, leading=14,
                              spaceAfter=6, textColor=colors.darkgreen))
    styles.add(ParagraphStyle(name="NormalText", fontSize=10, leading=12,
                              spaceAfter=4))
    styles.add(ParagraphStyle(name="ListItem", fontSize=10, leading=12,
                              leftIndent=10))

    story = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            story.append(Spacer(1, 4))
            continue

        if line.startswith("# "):
            story.append(Paragraph(line[2:], styles["Header1"]))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], styles["Header2"]))
        elif line.startswith("- "):
            line = re.sub(r"\*\*(.*?)\*\*", r'<font color="blue">\1</font>', line)
            story.append(Paragraph("- " + line[2:], styles["ListItem"]))
        else:
            line = re.sub(r"\*\*(.*?)\*\*", r'<font color="blue">\1</font>', line)
            story.append(Paragraph(line, styles["NormalText"]))

    doc.build(story)

# ----------------------------
# MAIN FUNCTION USED BY MCP TOOL
# ----------------------------
def generate_release_notes_from_query(user_query: str) -> dict:
    """
    End-to-end pipeline (WORKFLOW SAME):
    1) Extract project + version
    2) Fetch version info (release date)
    3) Fetch issues
    4) Classify issues
    5) Format release notes
    6) Save as PDF
    """
    extracted = llm_extract_project_and_version(user_query)
    if not extracted:
        return {"reply": "Please provide project and version. Example: ZOOKEEPER 3.9.0"}

    project = extracted["project"]
    version = extracted["version"]

    version_info_raw = fetch_jira_version_info(project, version)
    if isinstance(version_info_raw, str) and version_info_raw.startswith("Error:"):
        return {"reply": f"Error fetching version info: {version_info_raw}"}

    version_info = json.loads(version_info_raw)
    release_date = version_info.get("release_date", "Unknown")

    issues_raw = fetch_jira_issues(project, version)
    if isinstance(issues_raw, str) and issues_raw.startswith("Error:"):
        return {"reply": f"Error fetching issues: {issues_raw}"}

    summarized_raw = classify_and_summarize_issues(issues_raw)
    if isinstance(summarized_raw, str) and summarized_raw.startswith("Error:"):
        return {"reply": f"Error classifying issues: {summarized_raw}"}

    release_notes_text = format_release_notes(project, version, release_date, summarized_raw)
    if isinstance(release_notes_text, str) and release_notes_text.startswith("Error:"):
        return {"reply": f"Error formatting release notes: {release_notes_text}"}

    os.makedirs("generated_pdfs", exist_ok=True)
    pdf_name = f"{project}_v{version}_release_notes.pdf"
    pdf_path = os.path.join("generated_pdfs", pdf_name)

    save_to_pdf(release_notes_text, pdf_path)

    return {
        "reply": "Release notes generated.",
        "project": project,
        "version": version,
        "pdf_name": pdf_name
    }

# -----------------------------
# A2A Handler (NEW) - Added Only
# -----------------------------
def a2a_handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    A2A wrapper: accepts structured payload and returns structured response.
    Does NOT change your workflow.
    """
    task_id = payload.get("task_id") or str(uuid.uuid4())
    message = payload.get("message", "")

    try:
        result = generate_release_notes_from_query(message)

        # If failed
        if "pdf_name" not in result:
            return {
                "task_id": task_id,
                "status": "failed",
                "agent_id": AGENT_ID,
                "error": result.get("reply", "Unable to process request")
            }

        # If success
        return {
            "task_id": task_id,
            "status": "success",
            "agent_id": AGENT_ID,
            "data": result
        }

    except Exception as e:
        return {
            "task_id": task_id,
            "status": "failed",
            "agent_id": AGENT_ID,
            "error": str(e)
        }

# ----------------------------
# CLI Run
# ----------------------------
if __name__ == "__main__":
    print("\n🔹 JIRA Release Notes Generator (A2A Enabled)")
    print("Type 'exit' to quit\n")

    while True:
        query = input("Enter your query: ").strip()
        if query.lower() == "exit":
            break

        print("\n⏳ Processing...\n")
        try:
            # Normal direct run
            print(generate_release_notes_from_query(query))

            # Example A2A run (optional)
            # payload = {"message": query}
            # print(a2a_handle(payload))

        except Exception as e:
            print(f"❌ Error: {e}")
