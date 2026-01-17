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

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # Optional (recommended)

llm = ChatGroq(
    model="moonshotai/kimi-k2-instruct-0905",
    temperature=0,
    max_tokens=None,
    api_key=GROQ_API_KEY,
)

# -----------------------------
# A2A Metadata
# -----------------------------
AGENT_ID = "github-release-notes-agent"

A2A_META = {
    "agent_id": AGENT_ID,
    "name": "GitHub Release Notes Generator",
    "description": "Generates release notes PDF from GitHub releases using repo + version/tag",
    "capabilities": ["github_release_fetch", "summarize", "release_notes", "pdf_generate"]
}

# ----------------------------
# Extract owner/repo/version
# ----------------------------
def llm_extract_repo_and_version(user_query: str) -> Optional[Dict[str, str]]:
    """
    Extract GitHub repo owner, repo name and tag/version from natural query.

    Example:
      "Generate release notes for apache/zookeeper version 3.9.0"
    Output:
      {"owner":"apache","repo":"zookeeper","version":"3.9.0"}
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You extract structured data from user queries.\n"
         "Return ONLY valid JSON in this exact format:\n"
         "{{\n"
         '  "owner": "<GITHUB_OWNER>",\n'
         '  "repo": "<GITHUB_REPO>",\n'
         '  "version": "<TAG_OR_VERSION>"\n'
         "}}\n"
         "Rules:\n"
         "- owner and repo must be lowercase if possible\n"
         "- version must match user query (example: 3.9.0 or v3.9.0)\n"
         "- NO extra text"),
        ("user", "{query}")
    ])

    chain = prompt | llm
    response = chain.invoke({"query": user_query})

    try:
        data = json.loads(response.content)
        if "owner" in data and "repo" in data and "version" in data:
            return {
                "owner": str(data["owner"]).strip(),
                "repo": str(data["repo"]).strip(),
                "version": str(data["version"]).strip()
            }
        return None
    except Exception:
        return None

# ----------------------------
# Fetch GitHub release info
# ----------------------------
def fetch_github_release(owner: str, repo: str, version: str) -> str:
    """
    Fetch GitHub release details for a repo + version/tag.

    Tries:
      1) /releases/tags/{version}
      2) if version doesn't start with v -> try v{version}
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "github-release-notes-agent"
    }

    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    base_url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{version}"

    try:
        r = requests.get(base_url, headers=headers, timeout=30)

        # If not found, try adding "v"
        if r.status_code == 404 and not version.startswith("v"):
            alt_version = "v" + version
            alt_url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{alt_version}"
            r = requests.get(alt_url, headers=headers, timeout=30)

        r.raise_for_status()
        data = r.json()

        return json.dumps({
            "owner": owner,
            "repo": repo,
            "version": version,
            "tag_name": data.get("tag_name", version),
            "name": data.get("name", ""),
            "published_at": data.get("published_at", "Unknown"),
            "body": data.get("body", "")
        })

    except Exception as e:
        return f"Error: {str(e)}"

# ----------------------------
# Classify release body
# ----------------------------
def classify_and_summarize_release(release_json: str) -> str:
    """
    Classify GitHub release body into categories like Features, Fixes, Others.
    """
    try:
        data = json.loads(release_json)

        body = data.get("body", "") or ""
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]

        categories = {
            "Features": [],
            "Bug Fixes": [],
            "Improvements": [],
            "Others": []
        }

        for ln in lines:
            low = ln.lower()

            # basic classification
            if "fix" in low or "bug" in low:
                categories["Bug Fixes"].append(ln)
            elif "feature" in low or "add" in low or "new" in low:
                categories["Features"].append(ln)
            elif "improve" in low or "update" in low or "enhance" in low:
                categories["Improvements"].append(ln)
            else:
                categories["Others"].append(ln)

        # remove empty categories
        categories = {k: v for k, v in categories.items() if v}

        return json.dumps({
            "owner": data.get("owner", ""),
            "repo": data.get("repo", ""),
            "version": data.get("version", ""),
            "tag_name": data.get("tag_name", ""),
            "published_at": data.get("published_at", "Unknown"),
            "release_title": data.get("name", ""),
            "categories": categories
        })

    except Exception as e:
        return f"Error: {str(e)}"

# ----------------------------
# Format release notes
# ----------------------------


def clean_github_line(line: str) -> str:
    # remove markdown links: [text](url) -> text
    line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", line)

    # remove backticks
    line = line.replace("`", "")

    # remove leading bullets like "*", "-", "+"
    line = re.sub(r"^[\*\-\+]\s*", "", line)

    # remove extra spaces
    line = re.sub(r"\s+", " ", line).strip()

    return line


def classify_and_summarize_release(release_json: str) -> str:
    """
    Clean + classify GitHub release body into categories like Features, Bug Fixes, Others.
    """
    try:
        data = json.loads(release_json)

        body = data.get("body", "") or ""
        raw_lines = body.splitlines()

        # Clean lines + remove empty
        lines = []
        for ln in raw_lines:
            ln = ln.strip()
            if not ln:
                continue
            ln = clean_github_line(ln)
            if ln:
                lines.append(ln)

        categories = {
            "Features": [],
            "Bug Fixes": [],
            "Improvements": [],
            "Others": []
        }

        for ln in lines:
            low = ln.lower()

            if "fix" in low or "bug" in low:
                categories["Bug Fixes"].append(ln)
            elif "feature" in low or "add" in low or "new" in low:
                categories["Features"].append(ln)
            elif "improve" in low or "update" in low or "enhance" in low:
                categories["Improvements"].append(ln)
            else:
                categories["Others"].append(ln)

        # remove empty categories
        categories = {k: v for k, v in categories.items() if v}

        return json.dumps({
            "owner": data.get("owner", ""),
            "repo": data.get("repo", ""),
            "version": data.get("version", ""),
            "tag_name": data.get("tag_name", ""),
            "published_at": data.get("published_at", "Unknown"),
            "release_title": data.get("name", ""),
            "categories": categories
        })

    except Exception as e:
        return f"Error: {str(e)}"




def format_release_notes(owner: str, repo: str, version: str, summarized_data: str) -> str:
    """
    Format GitHub release notes like JIRA format (clean + professional).
    """
    try:
        data = json.loads(summarized_data)

        tag_name = data.get("tag_name", version)
        release_date = data.get("published_at", "Unknown")
        categories = data.get("categories", {})

        release_notes = f"# {repo.upper()} Release {tag_name}\n\n"
        release_notes += f"## Release Date\n{release_date}\n\n"

        total_items = sum(len(v) for v in categories.values())
        release_notes += "## Summary\n"
        release_notes += f"- **Total Items**: {total_items}\n"
        for cat, items in categories.items():
            release_notes += f"- **{cat}**: {len(items)}\n"
        release_notes += "\n"

        for cat, items in categories.items():
            if items:
                release_notes += f"## {cat}\n"
                for it in items:
                    release_notes += f"- {it}\n"
                release_notes += "\n"

        return release_notes

    except Exception as e:
        return f"Error: {str(e)}"


# ----------------------------
# PDF generator (same as JIRA)
# ----------------------------
def save_to_pdf(text: str, output_path: str):
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
# MAIN FUNCTION
# ----------------------------
def generate_release_notes_from_query(user_query: str) -> dict:
    extracted = llm_extract_repo_and_version(user_query)
    if not extracted:
        return {"reply": "Please provide owner/repo and version. Example: apache/zookeeper 3.9.0"}

    owner = extracted["owner"]
    repo = extracted["repo"]
    version = extracted["version"]

    release_raw = fetch_github_release(owner, repo, version)
    if isinstance(release_raw, str) and release_raw.startswith("Error:"):
        return {"reply": f"Error fetching GitHub release: {release_raw}"}

    summarized_raw = classify_and_summarize_release(release_raw)
    if isinstance(summarized_raw, str) and summarized_raw.startswith("Error:"):
        return {"reply": f"Error classifying release: {summarized_raw}"}

    release_notes_text = format_release_notes(owner, repo, version, summarized_raw)
    if isinstance(release_notes_text, str) and release_notes_text.startswith("Error:"):
        return {"reply": f"Error formatting release notes: {release_notes_text}"}

    os.makedirs("generated_pdfs", exist_ok=True)
    safe_repo = repo.replace("/", "_")
    pdf_name = f"{owner}_{safe_repo}_v{version}_release_notes.pdf"
    pdf_path = os.path.join("generated_pdfs", pdf_name)

    save_to_pdf(release_notes_text, pdf_path)

    return {
        "reply": "GitHub release notes generated.",
        "owner": owner,
        "repo": repo,
        "version": version,
        "pdf_name": pdf_name
    }

# -----------------------------
# A2A Handler
# -----------------------------
def a2a_handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    task_id = payload.get("task_id") or str(uuid.uuid4())
    message = payload.get("message", "")

    try:
        result = generate_release_notes_from_query(message)

        if "pdf_name" not in result:
            return {
                "task_id": task_id,
                "status": "failed",
                "agent_id": AGENT_ID,
                "error": result.get("reply", "Unable to process request")
            }

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
    print("\n🔹 GitHub Release Notes Generator (A2A Enabled)")
    print("Type 'exit' to quit\n")

    while True:
        query = input("Enter your query: ").strip()
        if query.lower() == "exit":
            break

        print("\n⏳ Processing...\n")
        try:
            print(generate_release_notes_from_query(query))
        except Exception as e:
            print(f"❌ Error: {e}")
