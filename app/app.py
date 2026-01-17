from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import base64
import json
import time
import re
from typing import Any, Dict

from langchain_mcp_adapters.client import MultiServerMCPClient

# ------------------------
# Constants & paths
# ------------------------
PDF_DIR = os.path.join(os.getcwd(), "generated_pdfs")
# BASE_URL = os.getenv("BASE_URL", "http://localhost:8507")
os.makedirs(PDF_DIR, exist_ok=True)

# ------------------------
# FastAPI app
# ------------------------
app = FastAPI(title="Release Notes Chat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

# ------------------------
# Models
# ------------------------
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    message: str
    pdf_url: str | None = None

# ------------------------
# MCP client (stdio)
# ------------------------
mcp_client = MultiServerMCPClient({
    "release_notes": {
        "transport": "stdio",
        "command": "python",
        "args": ["-u", "mcp_server.py"],  # same MCP server (JIRA + GitHub tools)
    }
})

# ------------------------
# Helper: Normalize tools (list or dict)
# ------------------------
def normalize_tools(raw_tools) -> Dict[str, Any]:
    normalized = {}

    if isinstance(raw_tools, dict):
        for k, v in raw_tools.items():
            short = k.split(".")[-1]
            normalized[short] = v
        return normalized

    if isinstance(raw_tools, list):
        for t in raw_tools:
            name = getattr(t, "name", None)
            if name:
                normalized[name.split(".")[-1]] = t
        return normalized

    raise RuntimeError(f"Unexpected tools type from get_tools(): {type(raw_tools)}")

# ------------------------
# Helper: unwrap MCP tool output
# ------------------------
def unwrap_mcp_result(result: Any) -> Any:
    """
    MCP tool may return:
      - dict
      - bool
      - list of content blocks [{"type":"text","text":"{...json...}"}]
      - string containing json
    Convert to dict if possible.
    """
    if isinstance(result, (dict, bool)):
        return result

    if isinstance(result, list) and len(result) > 0:
        first = result[0]
        if isinstance(first, dict) and "text" in first:
            text = first["text"]
            try:
                return json.loads(text)
            except Exception:
                return {"reply": text}

    if isinstance(result, str):
        try:
            return json.loads(result)
        except Exception:
            return {"reply": result}

    return {"reply": str(result)}

# ------------------------
# Helper: Decide which tool to call
# ------------------------
def decide_tool(user_message: str) -> str:
    """
    Decide whether query is for JIRA or GitHub.
    Rule-based (simple + reliable).
    """

    msg = user_message.lower().strip()

    # If user mentions github explicitly
    if "github" in msg:
        return "generate_github_release_notes"

    # If message contains owner/repo format like apache/zookeeper
    if re.search(r"\b[a-z0-9_.-]+\/[a-z0-9_.-]+\b", msg):
        return "generate_github_release_notes"

    # If user mentions jira explicitly
    if "jira" in msg or "fixversion" in msg or "project =" in msg:
        return "generate_release_notes"

    # Default fallback = JIRA
    return "generate_release_notes"

# ------------------------
# Startup: cache tools once
# ------------------------
@app.on_event("startup")
async def startup_event():
    try:
        app.state.mcp_tools = await mcp_client.get_tools()
        normalized = normalize_tools(app.state.mcp_tools)
        print("✅ MCP tools loaded:", list(normalized.keys()))
    except Exception as e:
        print("⚠️ Warning: failed to load MCP tools at startup:", repr(e))
        app.state.mcp_tools = None

# ------------------------
# Routes
# ------------------------
@app.post("/query", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # ----------------------------
        # Load cached tools or fetch again
        # ----------------------------
        raw_tools = getattr(app.state, "mcp_tools", None)
        if raw_tools is None:
            raw_tools = await mcp_client.get_tools()
            app.state.mcp_tools = raw_tools

        tools = normalize_tools(raw_tools)

        # Validate guard tool
        if "llama_guard_check" not in tools:
            raise HTTPException(status_code=500, detail="Required MCP tool llama_guard_check not available")

        # ----------------------------
        # Guardrail check
        # ----------------------------
        guard_tool = tools["llama_guard_check"]
        is_safe = await guard_tool.ainvoke({"text": request.message})
        is_safe = unwrap_mcp_result(is_safe)

        if isinstance(is_safe, dict):
            is_safe_bool = bool(is_safe.get("reply", False))
        else:
            is_safe_bool = bool(is_safe)

        if not is_safe_bool:
            raise HTTPException(
                status_code=400,
                detail="Your request violates usage policies. Please modify your input."
            )

        # ----------------------------
        # Auto decide which tool to call
        # ----------------------------
        selected_tool_name = decide_tool(request.message)

        if selected_tool_name not in tools:
            raise HTTPException(
                status_code=500,
                detail=f"Tool not available: {selected_tool_name}"
            )

        selected_tool = tools[selected_tool_name]

        # ----------------------------
        # Invoke selected tool
        # ----------------------------
        result = await selected_tool.ainvoke({"query": request.message})
        result = unwrap_mcp_result(result)

        if not isinstance(result, dict):
            return ChatResponse(message=str(result), pdf_url=None)

        # If tool returns error
        if "error" in result:
            return ChatResponse(message=result["error"], pdf_url=None)

        # ----------------------------
        # Handle response
        # ----------------------------
        if "pdf_bytes" in result:
            b64 = result["pdf_bytes"]
            pdf_name = result.get("pdf_name") or f"release_notes_{int(time.time())}.pdf"

            try:
                pdf_data = base64.b64decode(b64)
            except Exception:
                raise HTTPException(status_code=500, detail="Invalid base64 PDF data from tool")

            pdf_path = os.path.join(PDF_DIR, pdf_name)
            with open(pdf_path, "wb") as f:
                f.write(pdf_data)

            return ChatResponse(
                message=result.get("reply", "Release notes generated."),
                pdf_url=f"/pdf/{pdf_name}"
            )

        if "pdf_name" in result:
            pdf_name = result["pdf_name"]
            pdf_path = os.path.join(PDF_DIR, pdf_name)

            if not os.path.isfile(pdf_path):
                # if tool returned absolute path
                if os.path.isabs(pdf_name) and os.path.isfile(pdf_name):
                    pdf_path = pdf_name
                    pdf_name = os.path.basename(pdf_path)
                else:
                    raise HTTPException(status_code=500, detail="PDF generation failed")

            return ChatResponse(
                message=result.get("reply", "Release notes generated."),
                pdf_url=f"/pdf/{pdf_name}"
            )

        return ChatResponse(
            message=result.get("reply", "Unable to process request"),
            pdf_url=None
        )

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR in /query:", repr(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/pdf/{pdf_name}")
def get_pdf(pdf_name: str):
    file_path = os.path.join(PDF_DIR, pdf_name)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(file_path, media_type="application/pdf", filename=pdf_name)


@app.get("/health")
def health():
    return {"status": "ok"}

