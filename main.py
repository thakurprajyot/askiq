# main.py
# Simple single-file FastAPI app that serves a minimal frontend and provides /api/ask and /api/history.
# Usage (local): pip install -r requirements.txt ; export OPENAI_API_KEY=sk-... ; python main.py

from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import os, json, datetime
import httpx
from sqlalchemy import create_engine, Column, Integer, Text, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./askiq.db")

# DB setup (SQLite)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    model = Column(String(100), default="openai")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI(title="AskIQ")

# Static & templates
if not os.path.exists("static"):
    os.makedirs("static", exist_ok=True)
if not os.path.exists("templates"):
    os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Pydantic
class AskRequest(BaseModel):
    prompt: str

class AskResponse(BaseModel):
    id: int
    prompt: str
    response: str

@app.get("/", response_class=HTMLResponse)
def homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/ask", response_model=AskResponse)
async def api_ask(req: AskRequest):
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt required")

    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured on server")

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": OPENAI_MODEL,
        "messages": [{"role":"user","content": prompt}],
        "max_tokens": 800,
        "temperature": 0.2
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(OPENAI_API_URL, headers=headers, json=payload)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"LLM error: {r.text}")

    data = r.json()
    # extract text defensively
    response_text = ""
    try:
        choices = data.get("choices") or []
        if choices and "message" in choices[0]:
            response_text = choices[0]["message"]["content"]
        elif choices and "text" in choices[0]:
            response_text = choices[0]["text"]
        else:
            response_text = json.dumps(data)[:2000]
    except Exception:
        response_text = json.dumps(data)[:2000]

    db = SessionLocal()
    conv = Conversation(prompt=prompt, response=response_text, model=OPENAI_MODEL)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    db.close()

    return AskResponse(id=conv.id, prompt=conv.prompt, response=conv.response)

@app.get("/api/history")
def api_history(limit: int = 20):
    db = SessionLocal()
    rows = db.query(Conversation).order_by(Conversation.id.desc()).limit(limit).all()
    db.close()
    return [{"id": r.id, "prompt": r.prompt, "response": r.response, "created_at": r.created_at.isoformat()} for r in rows]

@app.get("/api/health")
def health():
    return {"status":"ok"}

# If run directly: start uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
