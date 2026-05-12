"""
Chat API Routes for Coltiva Recommendation Chatbot.

Endpoints:
- POST /chat - Main recommendation endpoint
- POST /chat/batch - Batch recommendations for extension officers
- GET /chat/suggestions/{crop} - Get suggested questions
- POST /chat/feedback - Submit feedback
"""

import logging
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException

from core.groq_client import groq_client
from core.knowledge_base import get_crop_names, get_topic_for_crop
from models.schemas import (
    ChatRequest,
    ChatResponse,
    BatchRecommendationRequest,
    FeedbackRequest,
    FarmerProfile,
    SuggestionsResponse
)
from services.recommendation import recommendation_service

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_current_farmer(user_id: str) -> FarmerProfile:
    """Get farmer profile (placeholder - would fetch from Supabase)."""
    return FarmerProfile(
        id=user_id,
        phone_hash=user_id,
        primary_crop="maize",
        district="Apac",
        farm_size_acres=1.5
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Main recommendation chat endpoint."""
    try:
        if not request.message or len(request.message.strip()) < 2:
            raise HTTPException(status_code=400, detail="Message must be at least 2 characters")
        
        crop = recommendation_service.detect_crop(request.message, request.crop)
        
        if not crop and request.include_farmer_context:
            try:
                farmer = await get_current_farmer(request.user_id)
                crop = farmer.primary_crop
            except Exception:
                pass
        
        if not crop:
            crop = "maize"
        
        topic = recommendation_service.detect_topic(request.message)
        
        farmer_context = None
        if request.include_farmer_context:
            try:
                farmer_context = await recommendation_service.get_farmer_context(request.user_id)
            except Exception as e:
                logger.warning(f"Failed to get farmer context: {e}")
        
        result = await groq_client.ask(
            crop=crop,
            question=request.message,
            topic=topic,
            farmer_context=farmer_context
        )
        
        follow_ups = recommendation_service.generate_follow_ups(crop, topic, 3)
        session_id = request.session_id or str(uuid.uuid4())
        
        try:
            await recommendation_service.log_conversation(
                session_id=session_id,
                user_id=request.user_id,
                crop=crop,
                question=request.message,
                answer=result.get("answer", "")
            )
        except Exception as e:
            logger.warning(f"Failed to log conversation: {e}")
        
        return ChatResponse(
            answer=result.get("answer", "Sorry, I couldn't generate a response."),
            crop_used=crop,
            sources=result.get("sources", []),
            confidence=result.get("confidence", 0.5),
            session_id=session_id,
            timestamp=datetime.utcnow(),
            follow_up_questions=follow_ups,
            farmer_context=farmer_context
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate response")


@router.post("/chat/batch", response_model=List[ChatResponse])
async def batch_recommendations(request: BatchRecommendationRequest) -> List[ChatResponse]:
    """Batch recommendation endpoint for extension officers."""
    try:
        if len(request.farmer_ids) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 farmers per batch")
        
        topic_data = get_topic_for_crop(request.crop, request.topic)
        
        if not topic_data:
            raise HTTPException(
                status_code=404,
                detail=f"Topic '{request.topic}' not found for crop '{request.crop}'"
            )
        
        question = f"Tell me about {request.topic} for {request.crop}"
        responses = []
        
        for farmer_id in request.farmer_ids:
            session_id = str(uuid.uuid4())
            
            result = await groq_client.ask(
                crop=request.crop,
                question=question,
                topic=request.topic,
                farmer_context=None
            )
            
            follow_ups = recommendation_service.generate_follow_ups(request.crop, request.topic, 2)
            
            responses.append(ChatResponse(
                answer=result.get("answer", "No response available."),
                crop_used=request.crop,
                sources=result.get("sources", []),
                confidence=result.get("confidence", 0.5),
                session_id=session_id,
                timestamp=datetime.utcnow(),
                follow_up_questions=follow_ups,
                farmer_context=None
            ))
        
        return responses
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch recommendation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate batch recommendations")


@router.get("/chat/suggestions/{crop}", response_model=SuggestionsResponse)
async def get_suggestions(crop: str) -> SuggestionsResponse:
    """Get suggested questions for a crop."""
    if crop not in get_crop_names():
        raise HTTPException(status_code=404, detail=f"Crop '{crop}' not found")
    
    suggestions = [
        f"When should I plant {crop}?",
        f"What is the best fertiliser for {crop}?",
        f"What are common pests for {crop}?",
        f"How do I control diseases in {crop}?",
        f"When is {crop} ready for harvest?",
        f"What varieties of {crop} are best?",
        f"How much does micro-dose fertiliser cost for {crop}?",
        f"What is the expected yield for {crop}?"
    ]
    
    return SuggestionsResponse(crop=crop, suggestions=suggestions)


@router.post("/chat/feedback")
async def submit_feedback(request: FeedbackRequest) -> dict:
    """Submit feedback for a chat session."""
    try:
        if not 1 <= request.rating <= 5:
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        
        success = await recommendation_service.save_feedback(
            session_id=request.session_id,
            rating=request.rating,
            comments=request.comments
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save feedback")
        
        return {
            "status": "success",
            "message": "Feedback saved successfully",
            "session_id": request.session_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail="Failed to save feedback")