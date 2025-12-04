import services.controller.chatbotController as chatbotController
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/chatbot")

# ---------- Models ----------
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    category: Optional[str] = None
    score: float = 0.0

# ---------- Route ----------
@router.post("/", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        result = await chatbotController.process_chat(req.message)
        return ChatResponse(**result)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        # Log error if needed
        print(f"[CHAT ERROR] {e}")
        return ChatResponse(
            response="Maaf, ada gangguan sistem sebentar.",
            score=0.0
        )

@router.get("/health")
async def health():
    return chatbotController.get_health_status()

# ---------- Startup ----------
@router.on_event("startup")
async def startup():
    chatbotController.startup_chatbot()