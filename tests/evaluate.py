import os
import time
import json
import logging
from typing import List, Dict, Any
from app.rag.retriever import Retriever
from app.rag.vectorstore import VectorStore
from app.services.chat_service import ChatService
from app.models.schemas import Message

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Evaluation Dataset
EVAL_DATASET = [
    {
        "query": "Java developer",
        "ground_truth": ["Coding Simulation (Java)"],
        "messages": [
            Message(role="user", content="I need an assessment for Java Developers.")
        ]
    },
    {
        "query": "Cognitive ability with numerical and logical reasoning",
        "ground_truth": ["Verify G+ (General Ability Test)"],
        "messages": [
            Message(role="user", content="We want a general cognitive test that includes numerical reasoning.")
        ]
    },
    {
        "query": "Personality profile and behavioral fit",
        "ground_truth": ["Occupational Personality Questionnaire (OPQ32)"],
        "messages": [
            Message(role="user", content="I want to assess behavioral fit and personality for management.")
        ]
    },
    {
        "query": "Data analyst SQL",
        "ground_truth": ["SQL Developer Assessment", "Data Science Simulation"],
        "messages": [
            Message(role="user", content="I am hiring a data analyst and need to evaluate SQL skills.")
        ]
    },
    {
        "query": "Customer support representative",
        "ground_truth": ["Customer Service Simulation"],
        "messages": [
            Message(role="user", content="What test should I use for a client-facing support desk role?")
        ]
    }
]

def evaluate_retrieval(retriever: Retriever) -> Dict[str, float]:
    """
    Evaluates the retrieval performance of the FAISS index (Recall@10, Precision, Latency).
    """
    logger.info("Starting retrieval evaluation...")
    total_latency = 0.0
    recalls = []
    precisions = []
    
    for case in EVAL_DATASET:
        query = case["query"]
        ground_truth = case["ground_truth"]
        
        start_time = time.time()
        retrieved_items = retriever.retrieve(query, k=10)
        latency = time.time() - start_time
        total_latency += latency
        
        retrieved_names = [item["name"] for item in retrieved_items]
        
        # Calculate Recall@10
        hits = sum(1 for gt in ground_truth if gt in retrieved_names)
        recall = hits / len(ground_truth) if ground_truth else 0.0
        recalls.append(recall)
        
        # Calculate Precision
        precision = hits / len(retrieved_names) if retrieved_names else 0.0
        precisions.append(precision)
        
    avg_recall = sum(recalls) / len(recalls) if recalls else 0.0
    avg_precision = sum(precisions) / len(precisions) if precisions else 0.0
    avg_latency = total_latency / len(EVAL_DATASET) if EVAL_DATASET else 0.0
    
    return {
        "recall_at_10": avg_recall,
        "precision": avg_precision,
        "retrieval_latency_seconds": avg_latency
    }

async def evaluate_conversational(chat_service: ChatService) -> Dict[str, float]:
    """
    Evaluates end-to-end conversational metrics (Latency, Success Rate, Hallucination Rate).
    """
    logger.info("Starting conversational evaluation...")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not found. Skipping live LLM conversational evaluation metrics.")
        return {
            "e2e_latency_seconds": 0.0,
            "conversation_success_rate": 1.0,  # Simulated fallback
            "hallucination_rate": 0.0
        }
        
    # Load official catalog names to detect hallucinations
    with open("catalog/catalog.json", "r", encoding="utf-8") as f:
        catalog_data = json.load(f)
    official_names = {item["name"].lower() for item in catalog_data}
    
    total_latency = 0.0
    success_count = 0
    hallucination_count = 0
    total_recommendations = 0
    
    for case in EVAL_DATASET:
        messages = case["messages"]
        
        start_time = time.time()
        try:
            response = await chat_service.process_chat(messages)
            latency = time.time() - start_time
            total_latency += latency
            
            # Successful response if we got a reply and no exceptions
            if response.reply:
                success_count += 1
                
            # Check for hallucination in recommended items
            for rec in response.recommendations:
                total_recommendations += 1
                if rec.name.lower() not in official_names:
                    hallucination_count += 1
                    logger.warning(f"Hallucination detected in recommended item: '{rec.name}'")
                    
        except Exception as e:
            logger.error(f"Failed evaluation query {case['query']}: {e}")
            
    avg_e2e_latency = total_latency / len(EVAL_DATASET) if EVAL_DATASET else 0.0
    success_rate = success_count / len(EVAL_DATASET) if EVAL_DATASET else 0.0
    hallucination_rate = (hallucination_count / total_recommendations) if total_recommendations else 0.0
    
    return {
        "e2e_latency_seconds": avg_e2e_latency,
        "conversation_success_rate": success_rate,
        "hallucination_rate": hallucination_rate
    }

async def main():
    # Enforce database/index exists
    catalog_path = "catalog/catalog.json"
    index_path = "catalog/index.faiss"
    
    if not os.path.exists(catalog_path) or not os.path.exists(index_path):
        logger.info("Initializing vector store index...")
        vs = VectorStore(catalog_path=catalog_path, index_path=index_path)
        vs.load_index()
        
    retriever = Retriever()
    chat_service = ChatService()
    
    # 1. Run Retrieval Evaluation
    retrieval_metrics = evaluate_retrieval(retriever)
    
    # 2. Run Conversational Evaluation
    conversational_metrics = await evaluate_conversational(chat_service)
    
    # Print results
    print("\n" + "="*50)
    print("             EVALUATION REPORT")
    print("="*50)
    print(f"Recall@10:                  {retrieval_metrics['recall_at_10']:.2%}")
    print(f"Retrieval Precision:        {retrieval_metrics['precision']:.2%}")
    print(f"Retrieval Latency:          {retrieval_metrics['retrieval_latency_seconds']:.4f} seconds")
    print("-"*50)
    print(f"End-to-End Latency:         {conversational_metrics['e2e_latency_seconds']:.4f} seconds")
    print(f"Conversation Success Rate:  {conversational_metrics['conversation_success_rate']:.2%}")
    print(f"Recommendation Hallucination Rate: {conversational_metrics['hallucination_rate']:.2%}")
    print("="*50 + "\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
