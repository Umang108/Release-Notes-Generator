# Release Notes Generator (JIRA + GitHub) 🚀

This project is a **Release Notes Generator** built using:

- **FastAPI** (Backend API)
- **MCP (FastMCP)** (Tool server)
- **LangChain + Groq LLM** (Query parsing + moderation)
- **Apache JIRA REST API** (JIRA issues)
- **GitHub REST API** (GitHub releases)
- **ReportLab** (PDF generation)
- **React** (Frontend UI)

It supports generating **professional PDF release notes** from:
Apache JIRA issues (project + fixVersion)  
 GitHub releases (owner/repo + tag/version)

## ✨ Features

- Single API endpoint: **POST `/query`**
- Automatically detects whether the query is for:
  - **JIRA** release notes
  - **GitHub** release notes
- Generates a **PDF** file in `generated_pdfs/`
- Provides **Preview + Download** PDF link
- Safety moderation using **Llama Guard style prompt**
- MCP tools exposed via **stdio transport**

## 📂 Project Structure

```bash
Release-Notes-Generator/
│
├── app/
│ ├── __init__.py
│ ├── jira_agent.py
│ ├── github_agent.py
│ └── app.py
│
├── chat-ui/
│
├── generated_pdfs/
│
├── mcp_server.py
├── requirements.txt
├── README.md
└── .env
```

## ⚙️ Environment Variables

Create a `.env` file in the root folder:

```env
GROQ_API_KEY=your_groq_api_key_here
```

## 📦 Installation

```bash
1. cd Release-Notes-Generator

2. Create virtual environment
    python -m venv .venv

3. Activate environment
Linux / Mac:
    source .venv/bin/activate
Windows
    .\.venv\Scripts\activate

4. Install dependencies
    pip install -r requirements.txt
```

## ▶️ Run Backend (FastAPI)

**Step 1: Start the FastAPI server**

```bash
    uvicorn app.app:app --host 0.0.0.0 --port 8507 --reload
```

## ▶️ Run Frontend (React)

```bash

1. cd chat-ui

2. Install node modules:
    npm install

3. Run React app:
    npm start

```

## Open in browser:

```bash
    http://localhost:3000

```

## Query Examples

**✅ JIRA Queries**

- Generate release notes for ZOOKEEPER version 3.9.0
- Create release notes PDF for HADOOP version 3.3.6
- ZOOKEEPER fixVersion 3.9.4 release notes

**✅ GitHub Queries**

- Generate GitHub release notes for facebook/react v18.2.0

## Response:

```bash
{
"message": "Release notes generated.",
"pdf_url": "/pdf/ZOOKEEPER_v3.9.0_release_notes.pdf"
}
```
