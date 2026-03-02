"""Gemini API client for metadata inference."""

import re
import json
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
You are a metadata extractor for Shia Islamic media (لطميات، جلوات، قرآن، أدعية، etc.).

Given a YouTube video title and channel name, extract the Arabic **title** and **artist**.

**Rules:**

1. Extract only the recitation/track title and the performer's name — ignore anything else (quality tags like 4K, locations, years, channel branding, etc.)
2. If no artist is found in the video title, use the channel name as the artist (in Arabic).
3. For artist names, apply prefix normalization:
   - Keep **السيد** and **الشيخ** (and normalize variants: `سيد` → `السيد`, `شيخ` → `الشيخ`)
   - Remove ALL other prefixes such as: `الملا`, `الملة`, `ملا`, `الحاج`, `حاج`, `الشاعر`, `المنشد`, `الرادود`, etc.
4. Return ONLY the two fields below — no explanation, no extra text.

**Output format (strict):**
```
title: <Arabic title>
artist: <Arabic artist>
```

**Examples:**

```
video_title: ملا باسم الكربلائي | يا حسين | جلسة خاصة 4K 2024
channel: قناة الولاء

title: يا حسين
artist: باسم الكربلائي
```

```
video_title: دعاء كميل | الشيخ حسين الأكرف | ليلة الجمعة
channel: Shia Media

title: دعاء كميل
artist: الشيخ حسين الأكرف
```

```
video_title: لطمية رائعة - يا أبا الفضل | تصوير: النجف الأشرف
channel: قناة الإمامين

title: يا أبا الفضل
artist: قناة الإمامين
```

```
video_title: سيد وائل السلامي - من كربلاء | حسين يا مظلوم
channel: كربلاء لايف

title: حسين يا مظلوم
artist: السيد وائل السلامي
```

Now process:

```
video_title: <video_title>
channel: <channel>
```
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

    def infer_metadata(
        self, video_title: str, channel: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str], str]:
        """
        Infer title and artist from video_title and channel.

        Args:
            video_title: The video title from filename
            channel: The channel name from filename

        Returns:
            Tuple of (title, artist, error_message, raw_response)
            - If successful, error_message is None
            - If failed, title and artist may be None or partial
            - raw_response always contains the raw text from Gemini
        """
        try:
            # Format the prompt with system instructions prepended
            # (since older SDK version doesn't support system_instruction parameter)
            prompt = SYSTEM_INSTRUCTIONS.replace("<video_title>", video_title).replace(
                "<channel>", channel
            )

            logger.info(
                f"Sending to Gemini - video_title: {video_title}, channel: {channel}"
            )

            response = self.model.generate_content(prompt)
            response_text = response.text.strip()

            logger.info(f"Gemini response: {response_text}")

            # Parse the response
            title, artist = self._parse_response(response_text)

            if not title or not artist:
                error_msg = f"Failed to parse Gemini response"
                logger.error(f"{error_msg}: {response_text}")
                return title, artist, error_msg, response_text

            return title, artist, None, response_text

        except Exception as e:
            error_msg = f"Gemini API error: {str(e)}"
            logger.error(error_msg)
            return None, None, error_msg, ""

    def _parse_response(
        self, response_text: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse the response to extract title and artist.

        Handles multiple formats:
        1. Two-line format:
           title: <title>
           artist: <artist>
        2. JSON format:
           {"title": "...", "artist": "..."}
        3. JSON in code fences:
           ```json
           {"title": "...", "artist": "..."}
           ```

        Args:
            response_text: The raw response from Gemini

        Returns:
            Tuple of (title, artist) or (None, None) if parsing fails
        """
        title = None
        artist = None

        # Try JSON parsing first (Gemini sometimes returns JSON despite instructions)
        try:
            # Remove code fences if present
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                # Extract content between code fences
                lines = cleaned.split("\n")
                # Remove first line (```json or ```)
                lines = lines[1:]
                # Find closing ```
                end_idx = len(lines)
                for i, line in enumerate(lines):
                    if line.strip() == "```":
                        end_idx = i
                        break
                cleaned = "\n".join(lines[:end_idx])

            # Try to parse as JSON
            data = json.loads(cleaned)
            if isinstance(data, dict):
                title = data.get("title")
                artist = data.get("artist")
                if title and artist:
                    logger.info(f"Parsed JSON response: title={title}, artist={artist}")
                    return title, artist
        except (json.JSONDecodeError, ValueError):
            # Not JSON, continue to regex parsing
            pass

        # Try regex parsing for two-line format
        # Match lines like "title: something" (case-insensitive, flexible whitespace)
        title_match = re.search(
            r"^\s*title\s*:\s*(.+?)\s*$", response_text, re.MULTILINE | re.IGNORECASE
        )
        artist_match = re.search(
            r"^\s*artist\s*:\s*(.+?)\s*$", response_text, re.MULTILINE | re.IGNORECASE
        )

        if title_match:
            title = title_match.group(1).strip()

        if artist_match:
            artist = artist_match.group(1).strip()

        if title and artist:
            logger.info(f"Parsed two-line response: title={title}, artist={artist}")

        return title, artist


# Global instance
gemini_client = GeminiClient()
