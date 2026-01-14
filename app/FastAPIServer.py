from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from Jira_agent import generate_release_notes_from_query
import os
import uvicorn

app = FastAPI(title="JIRA Release Notes Chat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    pdf_url: str = None

@app.post("/query", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    try:
        result = generate_release_notes_from_query(request.message)

        if "pdf_name" not in result:
            # Normal greeting or unrecognized query
            return ChatResponse(reply=result["reply"])

        pdf_name = result["pdf_name"]
        pdf_url = f"http://10.138.77.129:9050/pdf/{pdf_name}"

        return ChatResponse(
            reply=f"Release notes for {result['project']} version {result['version']} generated successfully.",
            pdf_url=pdf_url
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pdf/{pdf_name}")
def get_pdf(pdf_name:str):
    if not os.path.exists(pdf_name):
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(pdf_name, media_type="application/pdf")

@app.get("/health")
def health():
    return {"status":"ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8507)