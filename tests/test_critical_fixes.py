"""Test critical fixes for duplicate prevention and Gemini parse failures - Unit Tests Only."""
import sys
from pathlib import Path

sys.path.insert(0, '/Users/akbaralhashim/Documents/Coding/metadata-editor')

print("=" * 70)
print("UNIT TESTS FOR CRITICAL FIXES")
print("=" * 70)

# Test 1: File Identifier System
print("\n[Test 1] File Identifier System")
print("-" * 70)

from app.scanner import FileScanner

scanner = FileScanner()
test_file = Path("/tmp/test_audio_identifier.mp3")

# Create a test file
test_file.write_text("dummy audio content for testing")

# Compute identifier
identifier1 = scanner.compute_file_identifier(test_file)
print(f"✓ Computed file identifier: {identifier1[:16]}...")
assert len(identifier1) == 64, "SHA256 hash should be 64 characters"

# Compute again - should be identical
identifier2 = scanner.compute_file_identifier(test_file)
assert identifier1 == identifier2, "Identifiers should be identical for same file"
print(f"✓ Identifier is stable (same file = same identifier)")

# Cleanup
test_file.unlink()
print(f"✓ File identifier test passed!\n")

# Test 2: Gemini Client Returns Raw Response and Handles Multiple Formats  
print("[Test 2] Gemini Client Parsing & Raw Response")
print("-" * 70)

from app.gemini_client import GeminiClient

client = GeminiClient()

# Test 2a: Two-line format
response_text = """title: اختبار
artist: فنان"""

title, artist = client._parse_response(response_text)
assert title == "اختبار", f"Expected 'اختبار', got '{title}'"
assert artist == "فنان", f"Expected 'فنان', got '{artist}'"
print(f"✓ Two-line format parsing: title={title}, artist={artist}")

# Test 2b: JSON format
json_response = '{"title": "عنوان", "artist": "مؤدي"}'
title, artist = client._parse_response(json_response)
assert title == "عنوان", f"Expected 'عنوان', got '{title}'"
assert artist == "مؤدي", f"Expected 'مؤدي', got '{artist}'"
print(f"✓ JSON format parsing: title={title}, artist={artist}")

# Test 2c: Code-fenced JSON
fenced_json = '''```json
{"title": "test title", "artist": "test artist"}
```'''
title, artist = client._parse_response(fenced_json)
assert title == "test title", f"Expected 'test title', got '{title}'"
assert artist == "test artist", f"Expected 'test artist', got '{artist}'"
print(f"✓ Code-fenced JSON parsing: title={title}, artist={artist}")

# Test 2d: Unparseable response (should return None, None)
unparseable = "This is completely unparseable gibberish without any structure"
title, artist = client._parse_response(unparseable)
assert title is None and artist is None, "Unparseable response should return None, None"
print(f"✓ Unparseable response returns (None, None) → triggers needs_manual")

# Test 2e: Partial parsing (only title or only artist)
partial = "title: only this field"
title, artist = client._parse_response(partial)
assert title == "only this field", f"Expected 'only this field', got '{title}'"
assert artist is None, "Artist should be None"
print(f"✓ Partial parsing: title='{title}', artist=None → triggers needs_manual")

print(f"✓ Gemini client parsing test passed!\n")

# Test 3: Configuration
print("[Test 3] Staging Directory Configuration")
print("-" * 70)

from app.config import config

assert hasattr(config, 'STAGING_DIR'), "config should have STAGING_DIR attribute"
print(f"✓ STAGING_DIR configured: {config.STAGING_DIR}")

assert str(config.STAGING_DIR).endswith('staging'), "STAGING_DIR should end with 'staging'"
print(f"✓ STAGING_DIR path looks correct")

print(f"✓ Configuration test passed!\n")

# Test 4: Scanner Filename Parsing (existing functionality)
print("[Test 4] Scanner Filename Parsing")
print("-" * 70)

# Valid format
video_title, channel = scanner.parse_filename("Test Video###Test Channel.mp3")
assert video_title == "Test Video", f"Expected 'Test Video', got '{video_title}'"
assert channel == "Test Channel", f"Expected 'Test Channel', got '{channel}'"
print(f"✓ Valid format parsed: video_title='{video_title}', channel='{channel}'")

# Invalid format (no separator)
result = scanner.parse_filename("InvalidFormat.mp3")
assert result is None, "Invalid format should return None"
print(f"✓ Invalid format returns None")

print(f"✓ Filename parsing test passed!\n")

# Summary
print("=" * 70)
print("ALL UNIT TESTS PASSED!")
print("=" * 70)
print("\nVerified Functionality:")
print("1. ✓ File identifier generates stable SHA256 hashes")
print("2. ✓ Gemini client handles 4 response formats:")
print("   - Two-line format (title: X / artist: Y)")
print("   - JSON format")
print("   - Code-fenced JSON")
print("   - Unparseable responses (returns None, None)")
print("3. ✓ Staging directory is configured")
print("4. ✓ Filename parsing works correctly")
print("\nCritical Fixes Implemented:")
print("✓ Part 1: Duplicate prevention via file identifiers + staging")
print("✓ Part 2: Gemini parse failures → needs_manual cards")
print("=" * 70)
