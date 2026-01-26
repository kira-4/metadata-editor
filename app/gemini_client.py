"""Gemini API client for metadata inference."""
import re
import logging
from typing import Optional, Tuple
import google.generativeai as genai

from app.config import config

logger = logging.getLogger(__name__)

# ============================================================================
# GEMINI SYSTEM INSTRUCTIONS PLACEHOLDER
# ============================================================================
# PASTE YOUR CUSTOM SYSTEM INSTRUCTIONS HERE
# The instructions will be used when creating the GenerativeModel below.
# 
# Example format:
# SYSTEM_INSTRUCTIONS = """
# You are an AI that extracts Arabic audio metadata.
# Given video_title and channel, return:
# title: <Arabic title>
# artist: <Arabic artist>
# """
# ============================================================================

SYSTEM_INSTRUCTIONS = """
You are an AI assistant that extracts accurate Arabic audio metadata.

Given the video title and channel name from a downloaded audio file, 
you must infer the proper title and artist for the audio track.

Response format (exactly two lines):
title: <Arabic title>
artist: <Arabic artist>

Be accurate and preserve Arabic text correctly.
"""

# ============================================================================


class GeminiClient:
    """Client for Gemini API to infer metadata."""
    
    def __init__(self):
        """Initialize Gemini client."""
        if not config.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set. Gemini inference will fail.")
        
        genai.configure(api_key=config.GEMINI_API_KEY)
        
        # Note: system_instruction is available in newer versions
        # For google-generativeai 0.3.2, we'll prepend system instructions to the prompt instead
        self.model = genai.GenerativeModel(model_name=config.GEMINI_MODEL)
    
    def infer_metadata(self, video_title: str, channel: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Infer title and artist from video_title and channel.
        
        Args:
            video_title: The video title from filename
            channel: The channel name from filename
            
        Returns:
            Tuple of (title, artist, error_message)
            If successful, error_message is None
            If failed, title and artist are None, error_message contains the error
        """
        try:
            # Format the prompt with system instructions prepended
            # (since older SDK version doesn't support system_instruction parameter)
            prompt = f"{SYSTEM_INSTRUCTIONS}\n\n---\n\nvideo_title: {video_title}\nchannel: {channel}"
            
            logger.info(f"Sending to Gemini - video_title: {video_title}, channel: {channel}")
            
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            logger.info(f"Gemini response: {response_text}")
            
            # Parse the response
            title, artist = self._parse_response(response_text)
            
            if not title or not artist:
                error_msg = f"Failed to parse Gemini response: {response_text}"
                logger.error(error_msg)
                return None, None, error_msg
            
            return title, artist, None
            
        except Exception as e:
            error_msg = f"Gemini API error: {str(e)}"
            logger.error(error_msg)
            return None, None, error_msg
    
    def _parse_response(self, response_text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse the response to extract title and artist.
        
        Expected format:
        title: <title>
        artist: <artist>
        
        Args:
            response_text: The raw response from Gemini
            
        Returns:
            Tuple of (title, artist) or (None, None) if parsing fails
        """
        title = None
        artist = None
        
        # Try to extract title and artist using regex
        # Match lines like "title: something" (case-insensitive, flexible whitespace)
        title_match = re.search(r'^\s*title\s*:\s*(.+?)\s*$', response_text, re.MULTILINE | re.IGNORECASE)
        artist_match = re.search(r'^\s*artist\s*:\s*(.+?)\s*$', response_text, re.MULTILINE | re.IGNORECASE)
        
        if title_match:
            title = title_match.group(1).strip()
        
        if artist_match:
            artist = artist_match.group(1).strip()
        
        return title, artist


# Global instance
gemini_client = GeminiClient()
