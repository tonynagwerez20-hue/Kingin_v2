"""
Recommendation Service for Coltiva Chatbot.

Business logic for recommendation generation, topic detection,
and conversation logging.

Usage:
    from services.recommendation import RecommendationService
    
    service = RecommendationService()
    topic = service.detect_topic("my maize has yellow leaves")
"""

import logging
from typing import Dict, List, Optional, Any

from datetime import datetime

logger = logging.getLogger(__name__)


class RecommendationService:
    """Service for recommendation generation and management."""
    
    # Topic keywords for auto-detection
    TOPIC_KEYWORDS = {
        "planting": [
            "plant", "sow", "seed", "planting", "season", "when", "planted",
            "spacing", "depth", "row", "prepare", "land", "timing"
        ],
        "fertiliser": [
            "fertilizer", "fertiliser", "dap", "urea", "manure", "npk",
            "apply", "feeding", "nutrient", "micro-dose", "bottle cap", "cost",
            "price", "buy", "money", "roi"
        ],
        "pest": [
            "pest", "insect", "worm", "borer", "aphid", "bug", "weevil",
            "termite", "beetle", "caterpillar", "damage", "attack"
        ],
        "disease": [
            "disease", "sick", "illness", "blight", "rust", "mildew",
            " mosaic", "wilt", "rot", "virus", "bacterial", "fungi",
            "symptoms", "yellow", "spots", "lesion", "dying"
        ],
        "harvest": [
            "harvest", "harvesting", "yield", "storage", "dry", "moisture",
            "ready", "collect", "bag", "sell", "market", "price"
        ],
        "varieties": [
            "variety", "varieties", "seed", "type", "which", "recommend",
            "best", "sc627", "longe", "sesame", "cassava", "cm d"
        ]
    }
    
    # Crop keywords for auto-detection
    CROP_KEYWORDS = {
        "maize": ["maize", "corn", "wimbi", "ekitoobero"],
        "sesame": ["sesame", "simsim", "sesame"],
        "sunflower": ["sunflower", "ekigagi"],
        "sorghum": ["sorghum", "wimbi", "sorghum"],
        "soybeans": ["soybeans", "soy", " soybeans", "gilikansi"],
        "cassava": ["cassava", "kasuli", "ekibun", "cassava"]
    }
    
    # Follow-up questions by topic
    FOLLOW_UP_TEMPLATES = {
        "planting": [
            "What is the best fertiliser for {crop}?",
            "How do I prepare the land for {crop}?",
            "What pests affect {crop} at planting?"
        ],
        "fertiliser": [
            "What is the best variety for {crop}?",
            "How and when should I harvest {crop}?",
            "What is the expected yield for {crop}?"
        ],
        "pest": [
            "How do I prevent {pest} in {crop}?",
            "What is the threshold for {pest}?",
            "What organic options for {pest} control?"
        ],
        "disease": [
            "Which {crop} varieties are disease resistant?",
            "How do I identify {disease}?",
            "What causes {disease} in {crop}?"
        ],
        "harvest": [
            "What is the current market price for {crop}?",
            "How do I store {crop} after harvest?",
            "What is the best time to sell {crop}?"
        ],
        "varieties": [
            "Which variety is best for my district?",
            "What is the yield potential of variety X?",
            "Where can I buy certified {crop} seed?"
        ]
    }
    
    def __init__(self):
        """Initialize the recommendation service."""
        self._supabase_client = None
        logger.info("RecommendationService initialized")
    
    def set_supabase_client(self, client) -> None:
        """Set Supabase client for logging."""
        self._supabase_client = client
    
    def detect_topic(self, message: str) -> str:
        """Detect the topic from a message.
        
        Args:
            message: User's message
            
        Returns:
            Topic name or 'general' if unknown
        """
        message_lower = message.lower()
        
        # Score each topic by keyword matches
        topic_scores = {}
        
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in message_lower)
            if score > 0:
                topic_scores[topic] = score
        
        if topic_scores:
            # Return the topic with highest score
            return max(topic_scores.items(), key=lambda x: x[1])[0]
        
        return "general"
    
    def detect_crop(self, message: str, provided_crop: Optional[str] = None) -> Optional[str]:
        """Detect crop from message or use provided.
        
        Args:
            message: User's message
            provided_crop: Crop provided in request
            
        Returns:
            Crop name or None if not detected
        """
        # Use provided crop if valid
        if provided_crop:
            return provided_crop
        
        # Try to detect from message
        message_lower = message.lower()
        
        crop_scores = {}
        for crop, keywords in self.CROP_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in message_lower)
            if score > 0:
                crop_scores[crop] = score
        
        if crop_scores:
            return max(crop_scores.items(), key=lambda x: x[1])[0]
        
        return None
    
    def generate_follow_ups(
        self,
        crop: str,
        topic: str,
        count: int = 3
    ) -> List[str]:
        """Generate follow-up questions.
        
        Args:
            crop: Crop name
            topic: Current topic
            count: Number of questions to generate
            
        Returns:
            List of follow-up questions
        """
        templates = self.FOLLOW_UP_TEMPLATES.get(topic, [])
        
        if not templates:
            # Use general follow-ups
            templates = [
                f"What is the best fertiliser for {crop}?",
                f"How do I control pests in {crop}?",
                f"What is the expected yield for {crop}?"
            ]
        
        # Format and return limited questions
        questions = []
        for template in templates[:count]:
            questions.append(template.format(crop=crop, topic=topic))
        
        return questions
    
    async def get_farmer_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch farmer context from Supabase.
        
        Args:
            user_id: User identifier
            
        Returns:
            Farmer profile dict or None
        """
        # Note: This is a placeholder. In production, fetch from Supabase.
        if not self._supabase_client:
            return None
        
        try:
            # Placeholder - would query Supabase here
            # response = self._supabase_client.table("farmers").select("*").eq("phone_hash", user_id).execute()
            return None
        except Exception as e:
            logger.error(f"Failed to fetch farmer context: {e}")
            return None
    
    async def log_conversation(
        self,
        session_id: str,
        user_id: str,
        crop: str,
        question: str,
        answer: str
    ) -> bool:
        """Log conversation to Supabase.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            crop: Crop that was used
            question: User's question
            answer: Assistant's answer
            
        Returns:
            Success status
        """
        if not self._supabase_client:
            logger.warning("Supabase client not available - conversation not logged")
            return False
        
        try:
            # Placeholder - would insert to Supabase here
            # self._supabase_client.table("conversations").insert({
            #     "session_id": session_id,
            #     "user_id": user_id,
            #     "crop": crop,
            #     "question": question,
            #     "answer": answer,
            #     "timestamp": datetime.utcnow().isoformat()
            # }).execute()
            logger.info(f"Conversation logged: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to log conversation: {e}")
            return False
    
    async def save_feedback(
        self,
        session_id: str,
        rating: int,
        comments: Optional[str] = None
    ) -> bool:
        """Save feedback for a session.
        
        Args:
            session_id: Session identifier
            rating: Rating 1-5
            comments: Optional comments
            
        Returns:
            Success status
        """
        if not self._supabase_client:
            logger.warning("Supabase client not available - feedback not saved")
            return False
        
        try:
            # Placeholder - would insert to Supabase here
            # self._supabase_client.table("feedback").insert({
            #     "session_id": session_id,
            #     "rating": rating,
            #     "comments": comments,
            #     "timestamp": datetime.utcnow().isoformat()
            # }).execute()
            logger.info(f"Feedback saved: {session_id} rating={rating}")
            return True
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")
            return False


# Singleton instance
recommendation_service = RecommendationService()