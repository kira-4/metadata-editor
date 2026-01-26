"""Quick smoke test to verify basic functionality."""
import sys
sys.path.insert(0, '/Users/akbaralhashim/Documents/Coding/metadata-editor')

print("Testing imports...")

# Test config
from app.config import config
print(f"✓ Config loaded: DATA_DIR={config.DATA_DIR}")

# Test scanner
from app.scanner import FileScanner
scanner = FileScanner()

# Test filename parsing
test_cases = [
    ("زواج الغالي###ملا حاتم العبدالله.mp3", ("زواج الغالي", "ملا حاتم العبدالله")),
    ("Title###Channel.m4a", ("Title", "Channel")),
    ("invalid_filename.mp3", None),
]

print("\nTesting filename parser...")
for filename, expected in test_cases:
    result = scanner.parse_filename(filename)
    if result == expected:
        print(f"✓ {filename}: {result}")
    else:
        print(f"✗ {filename}: got {result}, expected {expected}")

# Test metadata processor
from app.metadata_processor import MetadataProcessor
processor = MetadataProcessor()

print("\nTesting filename sanitization...")
sanitize_cases = [
    ("Test: Invalid/Name", "Test Invalid Name"),
    ("زواج الغالي", "زواج الغالي"),
    ("Name with < and >", "Name with  and"),
]

for input_name, _ in sanitize_cases:
    result = processor.sanitize_filename(input_name)
    print(f"✓ '{input_name}' -> '{result}'")

print("\n✓ All basic tests passed!")
