import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.Jira_agent import generate_release_notes_from_query
from app.guardrails import llama_guard_check

import uvicorn

# ------------------------
# App initialization
# ------------------------
app = FastAPI(
    title="JIRA Release Notes Chat API",
    version="1.0.0",
    description="Generate JIRA release notes and downloadable PDFs using natural language"
)

# ------------------------
# CORS (adjust in prod)
# ------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------
# Models
# ------------------------
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    pdf_url: str | None = None

# ------------------------
# Constants
# ------------------------
PDF_DIR = "generated_pdfs"
BASE_URL = os.getenv("BASE_URL", "http://localhost:8507")

os.makedirs(PDF_DIR, exist_ok=True)

# ------------------------
# Routes
# ------------------------
@app.post("/query", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    try:
        # 🔐 GUARDRAIL CHECK
        is_safe = llama_guard_check(request.message)

        if not is_safe:
            raise HTTPException(
                status_code=400,
                detail="Your request violates usage policies. Please modify your input."
            )

        # ✅ SAFE → continue processing
        result = generate_release_notes_from_query(request.message)

        if "pdf_name" not in result:
            return ChatResponse(
                reply=result.get(
                    "reply",
                    "Unable to process request"
                )
            )

        pdf_name = result["pdf_name"]
        pdf_path = os.path.join(PDF_DIR, pdf_name)

        if not os.path.isfile(pdf_path):
            raise HTTPException(
                status_code=500,
                detail="PDF generation failed"
            )

        return ChatResponse(
            reply=(
                f"Release notes for {result['project']} "
                f"version {result['version']} generated successfully."
            ),
            pdf_url=f"{BASE_URL}/pdf/{pdf_name}"
        )

    except HTTPException:
        raise

    except Exception as e:
        print("ERROR:", e)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@app.get("/pdf/{pdf_name}")
def get_pdf(pdf_name: str):
    file_path = os.path.join(PDF_DIR, pdf_name)

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="PDF not found")

    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=pdf_name
    )

@app.get("/health")
def health():
    return {"status": "ok"}

# ------------------------
# Local run
# ------------------------
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8507, reload=True)
