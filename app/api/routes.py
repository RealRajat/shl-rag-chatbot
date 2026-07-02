import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)
router = APIRouter()

# Dependency injection for chat service
def get_chat_service() -> ChatService:
    return ChatService()

@router.get("/")
async def root():
    """
    Redirect root to API documentation.
    """
    return RedirectResponse(url="/docs")

@router.get("/health")
async def health():
    """
    Health check endpoint.
    """
    return {"status": "ok"}

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, chat_service: ChatService = Depends(get_chat_service)):
    """
    Chat endpoint for conversational SHL recommendations.
    Accepts full chat history and generates state-aware, RAG-grounded recommendations.
    """
    logger.info(f"Received chat request with {len(request.messages)} messages.")
    try:
        response = await chat_service.process_chat(request.messages)
        return response
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing the recommendation request: {str(e)}"
        )
