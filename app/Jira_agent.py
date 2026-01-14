import os
import re
import json
import requests
from typing import Dict
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain.agents import AgentExecutor, create_openai_tools_agent
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib import colors
from dotenv import load_dotenv


# load_dotenv()

# if not os.getenv("OPENAI_API_KEY"):
#     raise RuntimeError("OPENAI_API_KEY not found in environment")

import os
from dotenv import load_dotenv

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

# llm = ChatOpenAI(model="gpt-4o-mini")

def llm_extract_project_and_version(user_query: str) -> Dict[str, str]:
    """
    Use the LLM to extract project key and version from a natural query.
    Returns a dict: {"project": "<KEY>", "version": "<VERSION>"}
    """
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
            return data
        return None
    except Exception:
        return None


# Tools
@tool
def fetch_jira_issues(project: str, version: str) -> str:
    """Fetch JIRA issues for a specific project and version."""
    url = "https://issues.apache.org/jira/rest/api/2/search"
    params = {
        "jql": f"project = {project} AND fixVersion = {version}",
        "fields": "summary,issuetype",
        "startAt": 0,
        "maxResults": 50
    }

    try:
        response = requests.get(url, params=params)
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

@tool
def fetch_jira_version_info(project: str, version: str) -> str:
    """Fetch version information including release date from JIRA."""
    url = f"https://issues.apache.org/jira/rest/api/2/project/{project}/versions"

    try:
        response = requests.get(url)
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

@tool
def classify_and_summarize_issues(jira_data: str) -> str:
    """
    Dynamically classify JIRA issues based on their issue types and     summarize each category.
    Example: If issue types are ['Bug', 'Task', 'Sub-task', 'Improvement'],
    categories will automatically be created for each of them.
    """
    try:
        data = json.loads(jira_data)
        if isinstance(data, list):
            issues = data
            project = "Unknown"
            version = "Unknown"
        else:
            project = data.get("project", "")
            version = data.get("version", "")
            issues = data.get("issues", [])

        # Dynamic categories based on the issue types found
        categories = {}

        for issue in issues:
            issue_type = issue.get("type", "Uncategorized")
            summary = issue.get("summary", "")
            key = issue.get("key", "")

            if issue_type not in categories:
                categories[issue_type] = []

            categories[issue_type].append(f"{key}: {summary}")

        # Sort categories alphabetically for consistent output
        categories = dict(sorted(categories.items()))

        return json.dumps({
            "project": project,
            "version": version,
            "categories": categories
        })
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def format_release_notes(project: str, version: str, release_date: str, summarized_data: str) -> str:
    """Format dynamically categorized JIRA data into a professional release notes document."""
    try:
        data = json.loads(summarized_data)
        categories = data.get("categories", {})

        release_notes = f"# {project} Release {version}\n\n"
        release_notes += f"## Release Date\n{release_date}\n\n"

        total_issues = sum(len(v) for v in categories.values())
        release_notes += f"## Summary\n"
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


# AGENT SETUP
tools = [fetch_jira_issues, fetch_jira_version_info, classify_and_summarize_issues, format_release_notes]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a release notes generator. Your task is to:\n"
               "1. Fetch version information including release date for the given project and version\n"
               "2. Fetch JIRA issues for the given project and version\n"
               "3. Classify the issues into categories (New Features, Bug Fixes, etc.)\n"
               "4. Format everything into a professional release notes document\n\n"
               "The user will provide the project JIRA URL and version."),
    ("user", "Generate release notes for {project} version {version}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_openai_tools_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=20, handle_parsing_errors=True)


# PDF GENERATOR
def save_to_pdf(text: str, output_path: str):
    """
    Save text (markdown-like release notes) to a styled PDF.
    Replaces bold (**text**) with blue text and cleans unwanted lines.
    """

    # Remove unwanted lines
    skip_phrases = [
        "Here are the release notes for",
        "This release focused primarily",
        "I notice the formatting function"
    ]
    cleaned_lines = []
    for line in text.splitlines():
        if any(line.strip().startswith(p) for p in skip_phrases):
            continue
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)

    doc = SimpleDocTemplate(output_path, pagesize=letter,
                            rightMargin=50, leftMargin=50,
                            topMargin=50, bottomMargin=50)

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

        # Headers
        if line.startswith("# "):
            story.append(Paragraph(line[2:], styles["Header1"]))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], styles["Header2"]))
        elif line.startswith("- "):
            # Colorize issue IDs (e.g., ZOOKEEPER-1149) in blue
            line = re.sub(r"\b(ZOOKEEPER-\d+)\b", r'<font color="blue">\1</font>', line)
            # Replace **text** with blue-colored text instead of bold
            line = re.sub(r"\*\*(.*?)\*\*", r'<font color="blue">\1</font>', line)
            # Use dash instead of bullet for list items (old style)
            story.append(Paragraph("- " + line[2:], styles["ListItem"]))
        else:
            # Replace **text** with blue color
            line = re.sub(r"\*\*(.*?)\*\*", r'<font color="blue">\1</font>', line)
            story.append(Paragraph(line, styles["NormalText"]))

    doc.build(story)


def generate_release_notes_from_query(user_query: str) -> dict:
    """Take a natural query, extract project/version, run the tools, and generate a PDF."""
    
    extracted = llm_extract_project_and_version(user_query)
    if not extracted:
        return {
            "reply": "I can only generate release notes if you provide a JIRA project and version."
        }

    project = extracted["project"]
    version = extracted["version"]

    # Run agent / pipeline
    result = agent_executor.invoke({"project": project, "version": version})
    output_text = result["output"]   # ✅ this is the release notes text

    # PDF setup
    PDF_DIR = "generated_pdfs"
    os.makedirs(PDF_DIR, exist_ok=True)

    pdf_name = f"{project}_v{version}_release_notes.pdf"
    pdf_path = os.path.join(PDF_DIR, pdf_name)

    # ✅ Save the generated release notes text
    save_to_pdf(output_text, pdf_path)

    return {
        "project": project,
        "version": version,
        "pdf_name": pdf_name
    }


if __name__ == "__main__":
    print("\n🔹 JIRA Release Notes Generator")
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