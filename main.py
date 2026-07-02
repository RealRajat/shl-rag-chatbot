import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Load env variables from .env
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("shl_recommender")

# Lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events to run self-initialization on startup.
    Checks and generates catalog.json and the FAISS index if missing.
    """
    logger.info("Starting up Conversational SHL Assessment Recommender...")
    
    catalog_path = "catalog/catalog.json"
    index_path = "catalog/index.faiss"
    
    # 1. Self-initialize Catalog if missing
    if not os.path.exists(catalog_path):
        logger.info(f"Catalog file not found at {catalog_path}. Initializing scraper...")
        from app.scraper.scrape_catalog import main as run_scraper
        try:
            run_scraper()
            logger.info("Catalog initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize catalog: {e}")
            
    # 2. Self-initialize FAISS Index if missing
    if not os.path.exists(index_path):
        logger.info(f"FAISS index not found at {index_path}. Generating embeddings...")
        from app.rag.vectorstore import VectorStore
        try:
            vs = VectorStore(catalog_path=catalog_path, index_path=index_path)
            vs.build_index()
            logger.info("FAISS index built and stored locally successfully.")
        except Exception as e:
            logger.error(f"Failed to build FAISS index on startup: {e}")
            
    yield
    logger.info("Shutting down Conversational SHL Assessment Recommender...")

# Create FastAPI application
app = FastAPI(
    title="Conversational SHL Assessment Recommender",
    description=(
        "A production-ready RAG chatbot that recommends SHL Individual Test Solutions "
        "based on job roles and hiring requirements using Gemini 2.5 Flash and FAISS."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",      # Enable Swagger docs
    redoc_url="/redoc"
)

# Exception handlers for robust API operations
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled Exception on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please check logs."}
    )

# Include routes
from app.api.routes import router as api_router
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    log_level = os.environ.get("LOG_LEVEL", "info")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level=log_level.lower(),
        reload=True
    )
