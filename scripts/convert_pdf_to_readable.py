"""Convert PDF -> readable text using pymupdf4llm (no LLM calls).

Usage:
  python scripts/convert_pdf_to_readable.py --input data/raw/document.pdf
  python scripts/convert_pdf_to_readable.py --input data/raw/document.pdf --output data/processed/document_readable.txt

This script uses the project's `PDFProcessor` wrapper.
"""
import argparse
import sys
from pathlib import Path

# Ensure src is on path
repo_root = Path(__file__).parent.parent
# Ensure both project root and src/ are on sys.path so imports like `config.settings`
# and `processors.*` resolve regardless of how modules construct relative paths.
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / 'src'))

from processors.pdf_processor import PDFProcessor


def main():
    p = argparse.ArgumentParser(description="Convert PDF to readable text using pymupdf4llm (no LLM)")
    p.add_argument('--input', '-i', required=True, help='Path to input PDF')
    p.add_argument('--output', '-o', required=False, help='Output readable text path (optional)')
    p.add_argument('--write-images', action='store_true', help='Save images found in PDF')
    p.add_argument('--dpi', type=int, default=None, help='DPI for image extraction (optional)')
    args = p.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input PDF not found: {input_path}")
        raise SystemExit(1)

    # Default output file
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = repo_root / 'data' / 'processed' / f"{input_path.stem}_readable.txt"

    print(f"Converting: {input_path} -> {out_path}")

    proc = PDFProcessor(str(input_path))
    pages = proc.extract_text_to_markdown(
        page_chunks=True,
        show_progress=True,
        write_images=args.write_images,
        embed_images=False,
        dpi=args.dpi,
    )

    # Build readable text (simple merge of pages)
    lines = []
    for i, page in enumerate(pages):
        lines.append(f"## Page {i+1}")
        lines.append("")
        # page is dict; prefer 'text' key
        text = page.get('text') if isinstance(page, dict) else str(page)
        lines.append(text or "")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding='utf-8')

    print(f"Saved readable text to: {out_path}")


if __name__ == '__main__':
    main()
