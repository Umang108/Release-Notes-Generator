from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os
from mcp.server.fastmcp import FastMCP

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not found")

mcp = FastMCP("release-notes-agent")

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0,
    api_key=GROQ_API_KEY
)

@mcp.tool()
def llama_guard_check(text: str) -> bool:
    system_prompt = """
You are a safety moderation system for a DEVELOPER TOOL that generates software release notes (JIRA + GitHub).

Your task:
- Classify the user's input as SAFE or UNSAFE.
- Reply with ONLY ONE word: SAFE or UNSAFE.
- Do NOT include any explanation.

This application is used for:
- Software release notes
- JIRA issues, changelogs, fixVersions
- GitHub repositories, tags, releases
- Open-source projects (Apache, React, Kubernetes, etc.)
- Versioning, deployments, CI/CD
- Technical debugging and developer discussions

Mark input as UNSAFE ONLY if it clearly contains or requests:
1) Self-harm or suicide content (intent, encouragement, instructions)
2) Sexual / explicit content
3) Hate or harassment targeting protected groups
4) Real-world violence, weapons, terrorism, extremist content
5) Illegal wrongdoing instructions (fraud, stealing, hacking, malware, credential theft, bypassing security)

Always mark SAFE for:
- Software/project names (Spark, Kafka, Hadoop, Zookeeper, React, etc.)
- JIRA project keys and version numbers (e.g., ZOOKEEPER 3.9.0)
- GitHub repo formats (e.g., apache/zookeeper, facebook/react)
- GitHub tags/versions (e.g., v18.2.0, 3.9.4)
- Bug fixes, improvements, tasks, changelogs, release notes
- Programming, DevOps, APIs, logs, system debugging
- General technical questions

Important:
- If the request is technical and does NOT ask for illegal harm or hacking, it is SAFE.

Reply with ONLY ONE word:
SAFE or UNSAFE
"""


    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text}
    ])

    return response.content.strip().upper() == "SAFE"



@mcp.tool()
def generate_release_notes(query: str) -> dict:
    if not llama_guard_check(query):
        return {
            "error": "Your request violates usage policies. Please modify your input."
        }

    from app.jira_agent import generate_release_notes_from_query
    return generate_release_notes_from_query(query)


@mcp.tool()
def generate_github_release_notes(query: str) -> dict:
    if not llama_guard_check(query):
        return {
            "error": "Your request violates usage policies. Please modify your input."
        }

    from app.github_agent import generate_release_notes_from_query
    return generate_release_notes_from_query(query)



if __name__ == "__main__":
    mcp.run(transport="stdio")
