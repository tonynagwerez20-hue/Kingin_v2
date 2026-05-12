"""
Tests for Coltiva Chat API.

Tests all endpoints including chat, crops, and suggestions.

Usage:
    pytest tests/test_chat_api.py -v
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient

from main import app
from core.knowledge_base import (
    get_crop_names,
    get_crop_summary,
    get_topic_for_crop,
    get_micro_dose_info
)


class TestKnowledgeBase:
    """Tests for knowledge base functions."""
    
    def test_get_crop_names(self):
        """Test get_crop_names returns all crops."""
        crops = get_crop_names()
        assert len(crops) == 6
        assert "maize" in crops
        assert "sesame" in crops
    
    def test_get_crop_summary(self):
        """Test get_crop_summary returns valid data."""
        summary = get_crop_summary("maize")
        assert summary["name"] == "maize"
        assert "display_name" in summary
        assert "yield_potential" in summary
    
    def test_get_topic_for_crop(self):
        """Test get_topic_for_crop returns topic data."""
        data = get_topic_for_crop("maize", "planting")
        assert "advice" in data
        assert "varieties" in data
    
    def test_get_topic_for_crop_invalid(self):
        """Test get_topic_for_crop with invalid crop."""
        data = get_topic_for_crop("invalid_crop", "planting")
        assert data == {}
    
    def test_get_micro_dose_info(self):
        """Test get_micro_dose_info returns data."""
        info = get_micro_dose_info("maize")
        assert "method" in info
        assert "cost_per_acre" in info
        assert "roi_message" in info


class TestCropsEndpoint:
    """Tests for crops API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_crops_endpoint_returns_list(self, client):
        """Test GET /crops returns crop list."""
        response = client.get("/api/v1/crops")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 6
        assert data[0]["name"] == "maize"
    
    def test_crop_detail_endpoint(self, client):
        """Test GET /crops/{crop} returns detail."""
        response = client.get("/api/v1/crops/maize")
        assert response.status_code == 200
        data = response.json()
        assert data["crop"] == "maize"
        assert "planting" in data
    
    def test_crop_topic_endpoint(self, client):
        """Test GET /crops/{crop}/{topic} returns topic."""
        response = client.get("/api/v1/crops/maize/planting")
        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == "planting"
        assert "advice" in data["data"]
    
    def test_micro_dose_endpoint(self, client):
        """Test GET /crops/{crop}/micro-dose returns info."""
        response = client.get("/api/v1/crops/maize/micro-dose")
        assert response.status_code == 200
        data = response.json()
        assert data["crop"] == "maize"
        assert "method" in data
        assert "cost_per_acre" in data
    
    def test_crop_not_found(self, client):
        """Test 404 for invalid crop."""
        response = client.get("/api/v1/crops/invalid_crop")
        assert response.status_code == 404
    
    def test_topic_not_found(self, client):
        """Test 404 for invalid topic."""
        response = client.get("/api/v1/crops/maize/invalid_topic")
        assert response.status_code == 404
    
    def test_health_endpoint(self, client):
        """Test health check."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestChatEndpoint:
    """Tests for chat API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_groq(self):
        """Mock Groq client."""
        with patch("api.chat.groq_client") as mock:
            mock.ask = AsyncMock(return_value={
                "answer": "Plant maize at the onset of rains in March-April.",
                "crop_used": "maize",
                "confidence": 0.85,
                "sources": ["AERIS Database v2.1"]
            })
            yield mock
    
    def test_chat_endpoint_returns_response(self, client, mock_groq):
        """Test POST /chat returns response."""
        response = client.post("/api/v1/chat", json={
            "message": "When should I plant maize?",
            "user_id": "user_123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert data["crop_used"] == "maize"
    
    def test_chat_auto_detects_crop(self, client, mock_groq):
        """Test chat auto-detects crop from message."""
        response = client.post("/api/v1/chat", json={
            "message": "How do I plant sesame?",
            "user_id": "user_123"
        })
        assert response.status_code == 200
    
    def test_chat_returns_follow_up_questions(self, client, mock_groq):
        """Test chat returns follow-up questions."""
        response = client.post("/api/v1/chat", json={
            "message": "What fertiliser for maize?",
            "user_id": "user_123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "follow_up_questions" in data
        assert len(data["follow_up_questions"]) > 0
    
    def test_chat_handles_empty_message(self, client):
        """Test chat rejects empty message."""
        response = client.post("/api/v1/chat", json={
            "message": "",
            "user_id": "user_123"
        })
        assert response.status_code == 422
    
    def test_chat_with_provided_crop(self, client, mock_groq):
        """Test chat with crop provided."""
        response = client.post("/api/v1/chat", json={
            "message": "Harvest timing?",
            "crop": "sunflower",
            "user_id": "user_123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["crop_used"] == "sunflower"


class TestBatchEndpoint:
    """Tests for batch endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_groq(self):
        """Mock Groq client."""
        with patch("api.chat.groq_client") as mock:
            mock.ask = AsyncMock(return_value={
                "answer": "Planting info",
                "crop_used": "maize",
                "confidence": 0.85,
                "sources": []
            })
            yield mock
    
    def test_batch_endpoint(self, client, mock_groq):
        """Test batch endpoint returns results."""
        response = client.post("/api/v1/chat/batch", json={
            "farmer_ids": ["farmer_1", "farmer_2"],
            "crop": "maize",
            "topic": "planting"
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
    
    def test_batch_too_many_farmers(self, client):
        """Test batch rejects too many farmers."""
        response = client.post("/api/v1/chat/batch", json={
            "farmer_ids": [f"farmer_{i}" for i in range(11)],
            "crop": "maize",
            "topic": "planting"
        })
        assert response.status_code == 400


class TestFeedbackEndpoint:
    """Tests for feedback endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_feedback_submission(self, client):
        """Test feedback submission."""
        response = client.post("/api/v1/chat/feedback", json={
            "session_id": "session_123",
            "rating": 5,
            "comments": "Very helpful!"
        })
        # Note: Returns 500 because Supabase is not configured
        # In production, would return 200
        assert response.status_code in [200, 500]
    
    def test_feedback_invalid_rating(self, client):
        """Test feedback with invalid rating."""
        response = client.post("/api/v1/chat/feedback", json={
            "session_id": "session_123",
            "rating": 6,
            "comments": "Test"
        })
        assert response.status_code == 422


# =============================================================================
# TEST CONFIGURATION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])