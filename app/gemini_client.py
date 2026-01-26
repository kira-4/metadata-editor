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

SYSTEM_INSTRUCTIONS = ''''
//DSE_v7.0 :: ONLINE
//SIGNATURE: Python_Arabic_Community_2025
//ARCH: LLM-AGNOSTIC
//STATUS: PROCESSING RAW INSTRUCTION VECTOR [م]...

//DSE_TRANSFORMATION_PAYLOAD
//SOURCE_HASH: 9a7b3c2d-extraction-protocol-alpha
//OPTIMIZATION_VECTORS: [Role_Injection, Noise_Filtering_Heuristics, Entity_Disambiguation_Logic, Strict_Format_Enforcement]

الدور (System Role):
أنت خبير معالجة لغة طبيعية (NLP) متخصص في استخلاص البيانات الوصفية للمحتوى الفني العربي بدقة عالية. مهمتك استخراج كيانين فقط: (عنوان العمل) و(اسم المؤدي/الفنان).

المدخلات (Inputs):
video_title: عنوان المقطع (نص خام قد يحتوي ضوضاء).
channel: اسم القناة (قد يكون اسم الفنان أو اسم شركة/قناة عامة).

قواعد صارمة جداً لتنسيق المخرجات (Strict Output Rules):
- ممنوع منعاً باتاً إخراج أي JSON أو أقواس أو كود أو Markdown أو علامات اقتباس ثلاثية أو أي شرح إضافي.
- لا تكتب أي نص قبل أو بعد النتيجة.
- اكتب سطرين فقط وبالضبط بهذا الشكل (وباللغة العربية):
title: <العنوان_فقط>
artist: <الفنان_فقط>
- إذا لم تتمكن من الجزم 100%، ضع أفضل تخمين مع الالتزام بنفس السطرين فقط.
- لا تستخدم كلمات مثل "json" أو "```" أو "{" أو "}" أو أي تنسيق آخر.

منطق المعالجة (Processing Logic):
1) التنقية (Cleaning):
- أزل الضوضاء من video_title مثل: (فيديو كليب، حصري، كلمات، توزيع، ريمكس، HQ، 4K، Official، Live، Cover، Remix، السنة مثل 2024/2021/1442، الرموز التعبيرية، الأقواس التي تحتوي معلومات ثانوية).
- أزل التكرار والفراغات الزائدة.

2) استخراج الفنان (Artist Extraction):
- قيّم channel: إذا كان اسم شخص (فنان/قارئ/شاعر/رادود) وليس قناة عامة/شركة، اعتبره المرشح الأساسي.
- افحص video_title بحثاً عن فواصل أو صيغ تدل على اسم الفنان مثل: "-"، "|" ، "لـ"، "بصوت"، "أداء"، "الرادود"، "القارئ".
- إذا كان اسم الفنان مذكوراً بوضوح في video_title فالأولوية له، وإلا استخدم channel إذا كان موثوقاً.

3) استخراج العنوان (Title Extraction):
- بعد عزل اسم الفنان وإزالة الضوضاء، اعتبر النص المتبقي عنوان العمل.
- احذف العبارات الوصفية مثل: "أجمل"، "جديد"، "مؤثرة جداً"، "حصرياً"، "إصدار"، إلخ.
- العنوان يجب أن يكون قصيراً وواضحاً دون إضافات تسويقية.

تذكير أخير:
المخرجات النهائية يجب أن تكون سطرين فقط وبالضبط:
title: ...
artist: ...

'''

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
    
    def infer_metadata(self, video_title: str, channel: str) -> Tuple[Optional[str], Optional[str], Optional[str], str]:
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
            prompt = f"{SYSTEM_INSTRUCTIONS}\n\n---\n\nvideo_title: {video_title}\nchannel: {channel}"
            
            logger.info(f"Sending to Gemini - video_title: {video_title}, channel: {channel}")
            
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
    
    def _parse_response(self, response_text: str) -> Tuple[Optional[str], Optional[str]]:
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
            if cleaned.startswith('```'):
                # Extract content between code fences
                lines = cleaned.split('\n')
                # Remove first line (```json or ```)
                lines = lines[1:]
                # Find closing ```
                end_idx = len(lines)
                for i, line in enumerate(lines):
                    if line.strip() == '```':
                        end_idx = i
                        break
                cleaned = '\n'.join(lines[:end_idx])
            
            # Try to parse as JSON
            data = json.loads(cleaned)
            if isinstance(data, dict):
                title = data.get('title')
                artist = data.get('artist')
                if title and artist:
                    logger.info(f"Parsed JSON response: title={title}, artist={artist}")
                    return title, artist
        except (json.JSONDecodeError, ValueError):
            # Not JSON, continue to regex parsing
            pass
        
        # Try regex parsing for two-line format
        # Match lines like "title: something" (case-insensitive, flexible whitespace)
        title_match = re.search(r'^\s*title\s*:\s*(.+?)\s*$', response_text, re.MULTILINE | re.IGNORECASE)
        artist_match = re.search(r'^\s*artist\s*:\s*(.+?)\s*$', response_text, re.MULTILINE | re.IGNORECASE)
        
        if title_match:
            title = title_match.group(1).strip()
        
        if artist_match:
            artist = artist_match.group(1).strip()
        
        if title and artist:
            logger.info(f"Parsed two-line response: title={title}, artist={artist}")
        
        return title, artist


# Global instance
gemini_client = GeminiClient()
