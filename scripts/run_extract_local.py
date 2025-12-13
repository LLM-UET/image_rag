import sys
from pathlib import Path
import json

# Ensure repo src is on path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / 'src'))

from services.telecom_service import TelecomDocumentService

INPUT = repo_root / 'data' / 'processed' / 'vinaphone-01_readable.txt'
OUTPUT = repo_root / 'data' / 'structured' / 'vinaphone-01_packages.json'

if not INPUT.exists():
    print(f"Input file not found: {INPUT}")
    raise SystemExit(1)

print(f"Processing: {INPUT}")
service = TelecomDocumentService(model_name="gpt-4o-mini")
packages = service.process_document(str(INPUT))

# Save output
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT, 'w', encoding='utf-8') as f:
    json.dump({"packages": packages}, f, ensure_ascii=False, indent=2)

print(f"Saved {len(packages)} packages to: {OUTPUT}")
