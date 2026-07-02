import os
import json
import logging
import re
import hashlib
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from app.models.schemas import Message, ChatResponse, Recommendation
from app.rag.retriever import Retriever
from app.services.recommendation_service import RecommendationService
from app.prompts.system_prompt import SYSTEM_PROMPT
from app.utils.cache import MemoryCache
from app.utils.retry import retry_async

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, retriever: Retriever = None, recommendation_service: RecommendationService = None):
        self.retriever = retriever or Retriever()
        self.rec_service = recommendation_service or RecommendationService()
        self.cache = MemoryCache(ttl_seconds=int(os.environ.get("CACHE_EXPIRATION_SECONDS", "3600")))
        
        # Configure Gemini API
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            logger.info("Gemini API configured successfully.")
        else:
            logger.warning("GEMINI_API_KEY environment variable is not set.")

    def _get_model(self, system_instruction: str) -> genai.GenerativeModel:
        return genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_instruction
        )

    def _get_cache_key(self, messages: List[Message]) -> str:
        """
        Generates a unique md5 hash key for a list of messages.
        """
        serialized = "".join([f"{msg.role}:{msg.content}" for msg in messages])
        return hashlib.md5(serialized.encode("utf-8")).hexdigest()

    @retry_async(retries=3, delay=1.0, backoff=2.0)
    async def _generate_search_query_api(self, history_prompt: str) -> str:
        """
        Asynchronously calls Gemini to generate search query with retry logic.
        """
        model = genai.GenerativeModel("gemini-2.5-flash")
        # Run in executor to make it non-blocking if needed, but since it's synchronous SDK call:
        response = model.generate_content(
            history_prompt,
            generation_config=genai.types.GenerationConfig(max_output_tokens=30)
        )
        return response.text.strip()

    def _generate_search_query(self, messages: List[Message]) -> str:
        """
        Queries Gemini to construct a concise search query based on the conversation history.
        Falls back to the last message if API fails or is not configured.
        """
        if not messages:
            return ""
            
        last_message = messages[-1].content
        if len(messages) == 1:
            return last_message

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return last_message

        try:
            # Map roles to Gemini specifications
            history_prompt = "Based on the following chat history between a user and an assistant, generate a concise search query (maximum 5 words) to find the most relevant assessments in the SHL catalog. Highlight roles, programming languages, skills, or test types mentioned.\n\n"
            for msg in messages:
                history_prompt += f"{msg.role}: {msg.content}\n"
            history_prompt += "\nOutput ONLY the search query string, with no quotation marks or conversation."

            # Use a wrapper that runs synchronously inside this flow or uses event loop:
            # Since generating search query is quick, we run it synchronously but catching errors.
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(
                history_prompt,
                generation_config=genai.types.GenerationConfig(max_output_tokens=30)
            )
            query = response.text.strip()
            if query:
                query = re.sub(r'^["\']|["\']$', '', query)
                logger.info(f"Generated search query: '{query}'")
                return query
        except Exception as e:
            logger.error(f"Error generating search query with Gemini: {e}. Falling back to last message.")
            
        return last_message

    def _clean_json_response(self, text: str) -> str:
        text = text.strip()
        text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^```\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return text.strip()

    @retry_async(retries=3, delay=1.0, backoff=2.0)
    async def _call_gemini_api(self, model: genai.GenerativeModel, gemini_history: List[Dict[str, Any]], config: genai.types.GenerationConfig):
        """
        Call Gemini content generation with retries.
        """
        return model.generate_content(gemini_history, generation_config=config)

    async def process_chat(self, messages: List[Message]) -> ChatResponse:
        """
        Main entrypoint to process a chat request with caching and retries:
        1. Check cache first.
        2. Extract the search query from history.
        3. Perform similarity search in FAISS.
        4. Format retrieved catalog items.
        5. Call Gemini with system prompt and context to generate the structured answer.
        6. Validate recommended items against local catalog.json.
        7. Save to cache.
        """
        # 1. Check cache
        cache_key = self._get_cache_key(messages)
        cached_res = self.cache.get(cache_key)
        if cached_res:
            logger.info("Cache hit! Returning cached recommendation.")
            return cached_res

        # 2. Generate search query
        search_query = self._generate_search_query(messages)
        
        # 3. Retrieve context from FAISS
        context = ""
        try:
            context = self.retriever.retrieve_formatted_context(search_query, k=10)
        except Exception as e:
            logger.error(f"Error retrieving context from FAISS: {e}")
            context = "Error loading SHL product catalog."

        # 4. Formulate the system instruction with the context
        system_instruction = SYSTEM_PROMPT.format(retrieved_context=context)
        
        # Format conversation history for Gemini
        gemini_history = []
        for msg in messages:
            role = "user" if msg.role == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg.content]})

        # Call Gemini
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return ChatResponse(
                reply="API key is missing. Please set the GEMINI_API_KEY environment variable to enable recommendations.",
                recommendations=[],
                end_of_conversation=False
            )

        try:
            model = self._get_model(system_instruction)
            config = genai.types.GenerationConfig(
                response_mime_type="application/json"
            )
            
            logger.info("Calling Gemini for conversational recommendation...")
            response = await self._call_gemini_api(model, gemini_history, config)
            
            response_text = self._clean_json_response(response.text)
            logger.info(f"Gemini raw response: {response_text}")
            
            data = json.loads(response_text)
            
            reply = data.get("reply", "")
            raw_recs = data.get("recommendations", [])
            end_of_conversation = data.get("end_of_conversation", False)
            
            # 5. Validate recommendations against catalog
            validated_recs = self.rec_service.validate_recommendations(raw_recs)
            
            res = ChatResponse(
                reply=reply,
                recommendations=validated_recs,
                end_of_conversation=end_of_conversation
            )
            
            # 7. Store in cache
            self.cache.set(cache_key, res)
            return res
            
        except json.JSONDecodeError as jde:
            logger.error(f"JSON Decode Error from Gemini response: {jde}.")
            return ChatResponse(
                reply="I'm sorry, I encountered an issue parsing the response. Could you please rephrase your request?",
                recommendations=[],
                end_of_conversation=False
            )
        except Exception as e:
            logger.error(f"Error processing chat: {e}")
            return ChatResponse(
                reply="I encountered an internal error processing your request. Please try again later.",
                recommendations=[],
                end_of_conversation=False
            )
