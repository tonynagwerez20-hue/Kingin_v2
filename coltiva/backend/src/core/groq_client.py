"""
Groq LLM Client for Coltiva Recommendation Chatbot.

Wraps Groq API (llama-3.1-8b-instant) for generating recommendation responses.
Uses hardcoded knowledge base as context.

Usage:
    from core.groq_client import groq_client
    
    answer = await groq_client.ask("maize", "When should I plant?", "planting", farmer_context)
"""

import os
import logging
from typing import Dict, Any, Optional

try:
    import groq
except ImportError:
    groq = None

from core.knowledge_base import (
    KNOWLEDGE_BASE,
    get_crop_summary,
    get_topic_for_crop,
    get_design_rules,
    DESIGN_RULES
)

logger = logging.getLogger(__name__)


class GroqClient:
    """Singleton Groq client for Coltiva."""
    
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def _initialize(self) -> bool:
        """Initialize the Groq client with API key."""
        global _client
        
        if groq is None:
            logger.warning("groq package not installed")
            return False
        
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            logger.warning("GROQ_API_KEY not set")
            return False
        
        try:
            self._client = groq.Groq(api_key=api_key)
            logger.info("Groq client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
            return False
    
    def _build_system_prompt(self, crop: str) -> str:
        """Build system prompt with crop context and design rules."""
        rules_text = "\n".join([f"{k}. {v}" for k, v in DESIGN_RULES.items()])
        
        crop_summary = get_crop_summary(crop)
        
        system_prompt = f"""You are an agricultural extension advisor for AERIS Group's Coltiva platform in the Lango Sub-Region of Uganda.

You provide practical farming advice for smallholder farmers under 2 acres.
Your responses must follow these RULES:
{rules_text}

Target crop: {crop.upper()}
Crop summary: {crop_summary.get('display_name', crop)}
Planting season: {crop_summary.get('planting_season', 'N/A')}
Yield potential: {crop_summary.get('yield_potential', 'N/A')}
Micro-dose cost: {crop_summary.get('micro_dose_cost', 'N/A')}

IMPORTANT:
1. NEVER use kg/ha — always use bottle caps, bags/acre, or UGX
2. DEFAULT to micro-dose method for farmers under 2 acres
3. ALWAYS show ROI (Spend UGX X → Earn UGX Y extra)
4. Keep responses under 250 characters
5. Use simple language (Farmer-level)

You have access to detailed crop information from the AERIS Crop Intelligence Database v2.1.
"""
        return system_prompt
    
    def _build_topic_context(self, crop: str, topic: str) -> str:
        """Build detailed context for a specific topic."""
        if crop not in KNOWLEDGE_BASE:
            return ""
        
        topic_data = get_topic_for_crop(crop, topic)
        if not topic_data:
            return ""
        
        # Format as structured text
        lines = [f"\n## {topic.upper()}"]
        
        if topic == "planting":
            for key, value in topic_data.items():
                lines.append(f"- {key}: {value}")
        elif topic == "fertiliser":
            for key, value in topic_data.items():
                lines.append(f"- {key}: {value}")
        elif topic in ["pest", "disease"]:
            for pest_name, pest_data in topic_data.items():
                lines.append(f"\n### {pest_name}")
                for key, value in pest_data.items():
                    lines.append(f"  - {key}: {value}")
        elif topic == "varieties":
            for var_name, var_data in topic_data.items():
                lines.append(f"\n### {var_name}")
                for key, value in var_data.items():
                    lines.append(f"  - {key}: {value}")
        elif topic == "harvest":
            for key, value in topic_data.items():
                lines.append(f"- {key}: {value}")
        
        return "\n".join(lines)
    
    async def ask(
        self,
        crop: str,
        question: str,
        topic: str,
        farmer_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Ask a question and get a recommendation response.
        
        Args:
            crop: Target crop name (maize, sesame, sunflower, sorghum, soybeans, cassava)
            question: User's question
            topic: Topic area (planting, fertiliser, pest, disease, harvest, varieties, general)
            farmer_context: Optional farmer profile data
            
        Returns:
            Dict with 'answer', 'crop_used', 'confidence', 'sources'
        """
        # Validate crop
        if crop not in KNOWLEDGE_BASE:
            return {
                "answer": "I don't have information about that crop. Available: maize, sesame, sunflower, sorghum, soybeans, cassava.",
                "crop_used": crop,
                "confidence": 0.0,
                "sources": [],
                "requires_follow_up": True
            }
        
        # Build context from knowledge base
        topic_context = self._build_topic_context(crop, topic)
        
        # Build farmer context if available
        farmer_text = ""
        if farmer_context:
            fc = farmer_context
            farmer_text = f"""
Farmer profile context:
- District: {fc.get('district', 'Unknown')}
- Farm size: {fc.get('farm_size_acres', 'Unknown')} acres
- Soil pH: {fc.get('soil_ph', 'Unknown')}
- Primary crop: {fc.get('primary_crop', 'Unknown')}
"""
        
        # Build user prompt
        user_prompt = f"""{topic_context}

Farmer question: {question}
{farmer_text}

Based on the crop data above, provide a helpful, practical answer.
Follow the design rules: show ROI in UGX, use bottle caps, keep under 250 characters.
"""
        
        # If Groq client is available, use it
        if self._client is None:
            self._initialize()
        
        if self._client is not None:
            try:
                system_prompt = self._build_system_prompt(crop)
                
                response = self._client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=200
                )
                
                answer = response.choices[0].message.content
                
                # Truncate to 250 characters if needed
                if len(answer) > 250:
                    answer = answer[:247] + "..."
                
                return {
                    "answer": answer,
                    "crop_used": crop,
                    "confidence": 0.85,
                    "sources": [f"AERIS Crop Intelligence Database v2.1"],
                    "requires_follow_up": True
                }
            except Exception as e:
                logger.error(f"Groq API error: {e}")
                # Fall through to fallback
        
        # Fallback: use hardcoded data directly
        return self._fallback_answer(crop, question, topic)
    
    def _fallback_answer(
        self,
        crop: str,
        question: str,
        topic: str
    ) -> Dict[str, Any]:
        """Generate fallback answer from hardcoded knowledge base."""
        # Get topic data
        topic_data = get_topic_for_crop(crop, topic)
        
        if not topic_data:
            return {
                "answer": f"Please specify your question about {crop}. Topics: planting, fertiliser, pest, disease, harvest, varieties.",
                "crop_used": crop,
                "confidence": 0.5,
                "sources": ["AERIS Crop Intelligence Database v2.1"],
                "requires_follow_up": True
            }
        
        # Generate a basic answer based on topic
        if topic == "planting":
            advice = topic_data.get("advice", "Follow recommended practices.")
            season = topic_data.get("season", "")
            seed_rate = topic_data.get("seed_rate", "")
            
            answer = f"{advice} Season: {season}. Seed rate: {seed_rate}"
        
        elif topic == "fertiliser":
            method = topic_data.get("method", "")
            roi = topic_data.get("roi_message", "")
            cost = topic_data.get("cost_per_acre", "")
            
            answer = f"{method} Cost: {cost}. {roi}"
        
        elif topic == "harvest":
            timing = topic_data.get("timing", "")
            yield_pot = topic_data.get("yield_potential", "")
            
            answer = f"Harvest: {timing}. Yield: {yield_pot}"
        
        elif topic in ["pest", "disease"]:
            # List first pest/disease as fallback
            items = list(topic_data.items())
            if items:
                name, data = items[0]
                symptoms = data.get("symptoms", "")
                answer = f"{name}: {symptoms}"
            else:
                answer = "No data available."
        
        elif topic == "varieties":
            varieties = topic_data
            if varieties:
                var_list = ", ".join(list(varieties.keys())[:3])
                answer = f"Recommended: {var_list}"
            else:
                answer = "No varieties available."
        
        else:
            answer = f"See {topic} information for {crop}."
        
        # Truncate to 250 characters
        if len(answer) > 250:
            answer = answer[:247] + "..."
        
        return {
            "answer": answer,
            "crop_used": crop,
            "confidence": 0.7,
            "sources": ["AERIS Crop Intelligence Database v2.1"],
            "requires_follow_up": True
        }
    
    def is_available(self) -> bool:
        """Check if Groq client is available."""
        return self._client is not None
    
    def get_client(self):
        """Get the Groq client instance."""
        if self._client is None:
            self._initialize()
        return self._client


# Singleton instance
groq_client = GroqClient()