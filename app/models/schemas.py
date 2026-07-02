from pydantic import BaseModel, Field
from typing import List, Optional

class Message(BaseModel):
    role: str = Field(..., description="Role of the sender, either 'user' or 'assistant'.")
    content: str = Field(..., description="The content of the message.")

class ChatRequest(BaseModel):
    messages: List[Message] = Field(..., description="The full conversation history.")

class Recommendation(BaseModel):
    name: str = Field(..., description="The name of the assessment.")
    url: str = Field(..., description="The official product URL of the assessment.")
    test_type: str = Field(..., description="The type of the test (e.g., Cognitive, Personality, Coding, Simulation).")

class ChatResponse(BaseModel):
    reply: str = Field(..., description="The conversational reply from the assistant.")
    recommendations: List[Recommendation] = Field(default_factory=list, description="List of recommended assessments.")
    end_of_conversation: bool = Field(default=False, description="Whether the conversation has ended.")
