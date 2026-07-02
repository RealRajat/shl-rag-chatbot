import pytest
import os
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.models.schemas import Message, ChatResponse, Recommendation
from app.services.chat_service import ChatService

# Dummy data matching schemas for testing
MOCK_RETRIEVED_ASSESSMENTS = [
    {
        "name": "Verify G+ (General Ability Test)",
        "url": "https://www.shl.com/en/assessments/cognitive-ability/verify-g-plus/",
        "test_type": "Cognitive"
    },
    {
        "name": "Occupational Personality Questionnaire (OPQ32)",
        "url": "https://www.shl.com/en/assessments/personality-behavior/occupational-personality-questionnaire/",
        "test_type": "Personality"
    }
]

@pytest.fixture
def mock_retriever():
    retriever = MagicMock()
    retriever.retrieve_formatted_context.return_value = "Mocked Context for SHL catalog."
    return retriever

@pytest.fixture
def mock_rec_service():
    service = MagicMock()
    # Mock validate_recommendations to return Recommendation objects
    def side_effect(raw_recs):
        res = []
        catalog = {
            "verify g+ (general ability test)": {
                "name": "Verify G+ (General Ability Test)",
                "url": "https://www.shl.com/en/assessments/cognitive-ability/verify-g-plus/",
                "test_type": "Cognitive"
            },
            "occupational personality questionnaire (opq32)": {
                "name": "Occupational Personality Questionnaire (OPQ32)",
                "url": "https://www.shl.com/en/assessments/personality-behavior/occupational-personality-questionnaire/",
                "test_type": "Personality"
            }
        }
        for rec in raw_recs:
            n = rec.get("name", "").strip().lower()
            if n in catalog:
                res.append(
                    Recommendation(
                        name=catalog[n]["name"],
                        url=catalog[n]["url"],
                        test_type=catalog[n]["test_type"]
                    )
                )
        return res
    service.validate_recommendations.side_effect = side_effect
    return service

@pytest.mark.asyncio
async def test_clarification(mock_retriever, mock_rec_service):
    """
    Test that recommendations are empty when the bot asks for clarification.
    """
    chat_service = ChatService(retriever=mock_retriever, recommendation_service=mock_rec_service)
    
    # Mock search query extraction
    chat_service._generate_search_query = MagicMock(return_value="Need assessment")
    
    # Mock Gemini response returning clarification response in JSON
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "reply": "Which role are you hiring for and what specific skills do you need to assess?",
        "recommendations": [],
        "end_of_conversation": False
    })
    
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
        with patch.object(chat_service, "_call_gemini_api", AsyncMock(return_value=mock_response)):
            messages = [Message(role="user", content="Need assessment")]
            response = await chat_service.process_chat(messages)
            
            assert response.reply == "Which role are you hiring for and what specific skills do you need to assess?"
            assert len(response.recommendations) == 0
            assert response.end_of_conversation is False

@pytest.mark.asyncio
async def test_recommendation(mock_retriever, mock_rec_service):
    """
    Test that valid recommendations are returned when enough context is provided.
    """
    chat_service = ChatService(retriever=mock_retriever, recommendation_service=mock_rec_service)
    
    chat_service._generate_search_query = MagicMock(return_value="Java developer coding test")
    
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "reply": "I recommend the Verify G+ for general cognitive evaluation.",
        "recommendations": [
            {"name": "Verify G+ (General Ability Test)", "url": "https://www.shl.com/en/assessments/cognitive-ability/verify-g-plus/", "test_type": "Cognitive"}
        ],
        "end_of_conversation": False
    })
    
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
        with patch.object(chat_service, "_call_gemini_api", AsyncMock(return_value=mock_response)):
            messages = [Message(role="user", content="I need an assessment for a Java Developer.")]
            response = await chat_service.process_chat(messages)
            
            assert "Verify G+" in response.reply
            assert len(response.recommendations) == 1
            assert response.recommendations[0].name == "Verify G+ (General Ability Test)"
            assert response.recommendations[0].test_type == "Cognitive"

@pytest.mark.asyncio
async def test_comparison(mock_retriever, mock_rec_service):
    """
    Test comparing two assessments based on catalog data.
    """
    chat_service = ChatService(retriever=mock_retriever, recommendation_service=mock_rec_service)
    
    chat_service._generate_search_query = MagicMock(return_value="Compare OPQ and Verify G+")
    
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "reply": "Verify G+ measures general mental ability (cognitive), whereas OPQ32 measures personality and work styles.",
        "recommendations": [],
        "end_of_conversation": False
    })
    
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
        with patch.object(chat_service, "_call_gemini_api", AsyncMock(return_value=mock_response)):
            messages = [Message(role="user", content="What is the difference between Verify G+ and OPQ32?")]
            response = await chat_service.process_chat(messages)
            
            assert "measures personality" in response.reply
            assert len(response.recommendations) == 0

@pytest.mark.asyncio
async def test_refinement(mock_retriever, mock_rec_service):
    """
    Test refinement where recommendations update based on new requirements.
    """
    chat_service = ChatService(retriever=mock_retriever, recommendation_service=mock_rec_service)
    
    chat_service._generate_search_query = MagicMock(return_value="Java developer and personality assessment")
    
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "reply": "Based on your added preference for personality evaluation, I have updated the recommendation to include OPQ32.",
        "recommendations": [
            {"name": "Verify G+ (General Ability Test)", "url": "https://www.shl.com/en/assessments/cognitive-ability/verify-g-plus/", "test_type": "Cognitive"},
            {"name": "Occupational Personality Questionnaire (OPQ32)", "url": "https://www.shl.com/en/assessments/personality-behavior/occupational-personality-questionnaire/", "test_type": "Personality"}
        ],
        "end_of_conversation": False
    })
    
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
        with patch.object(chat_service, "_call_gemini_api", AsyncMock(return_value=mock_response)):
            messages = [
                Message(role="user", content="I need an assessment for a Java Developer."),
                Message(role="assistant", content="I suggest the Verify G+ test."),
                Message(role="user", content="Actually, include personality tests too.")
            ]
            response = await chat_service.process_chat(messages)
            
            assert "include OPQ32" in response.reply
            assert len(response.recommendations) == 2
            assert response.recommendations[1].name == "Occupational Personality Questionnaire (OPQ32)"

@pytest.mark.asyncio
async def test_refusal(mock_retriever, mock_rec_service):
    """
    Test refusal of out-of-scope requests.
    """
    chat_service = ChatService(retriever=mock_retriever, recommendation_service=mock_rec_service)
    
    chat_service._generate_search_query = MagicMock(return_value="How to fire an employee legally?")
    
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "reply": "I can only assist with recommending and comparing SHL assessments from the product catalog.",
        "recommendations": [],
        "end_of_conversation": False
    })
    
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
        with patch.object(chat_service, "_call_gemini_api", AsyncMock(return_value=mock_response)):
            messages = [Message(role="user", content="How to fire an employee legally?")]
            response = await chat_service.process_chat(messages)
            
            assert "I can only assist with recommending" in response.reply
            assert len(response.recommendations) == 0
