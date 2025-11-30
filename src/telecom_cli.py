#!/usr/bin/env python
"""
Telecom Package Extraction CLI - Command-line interface for the ETL pipeline.

Commands:
    extract     Extract packages from a document
    batch       Process multiple documents
    validate    Validate extraction results

Usage:
    python telecom_cli.py extract --input <file> --output <file>
    python telecom_cli.py batch --input-dir <dir> --output <file>
    python telecom_cli.py validate --input <file>
"""
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src directory to path for imports
project_root = Path(__file__).resolve().parent.parent
src_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_dir))

from services.telecom_service import process_document, process_multiple_documents
from core.models import TelecomPackage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_command(args):
    """
    Extract packages from a single document.
    
    Args:
        args: Parsed command line arguments
    """
    input_path = Path(args.input)
    
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)
    
    logger.info(f"Extracting packages from: {input_path}")
    
    try:
        # Process document
        packages = process_document(str(input_path), model_name=args.model)
        
        if not packages:
            logger.warning("No packages extracted from document")
            return
        
        logger.info(f"Extracted {len(packages)} packages")
        
        # Prepare output
        output_data = {
            "source_file": str(input_path),
            "total_packages": len(packages),
            "packages": packages
        }
        
        # Save or print results
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Results saved to: {output_path}")
        else:
            # Print to stdout
            print(json.dumps(output_data, ensure_ascii=False, indent=2))
        
        # Print summary
        if args.verbose:
            print_summary(packages)
            
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def batch_command(args):
    """
    Process multiple documents from a directory.
    
    Args:
        args: Parsed command line arguments
    """
    input_dir = Path(args.input_dir)
    
    if not input_dir.exists() or not input_dir.is_dir():
        logger.error(f"Input directory not found: {input_dir}")
        sys.exit(1)
    
    # Find all supported files
    supported_extensions = {'.pdf', '.json', '.txt'}
    files = [
        f for f in input_dir.iterdir() 
        if f.is_file() and f.suffix.lower() in supported_extensions
    ]
    
    # Filter by pattern if specified
    if args.pattern:
        import fnmatch
        files = [f for f in files if fnmatch.fnmatch(f.name, args.pattern)]
    
    if not files:
        logger.warning(f"No supported files found in: {input_dir}")
        return
    
    logger.info(f"Processing {len(files)} files from: {input_dir}")
    
    try:
        # Process all files
        all_packages = process_multiple_documents(
            [str(f) for f in files],
            model_name=args.model
        )
        
        logger.info(f"Total packages extracted: {len(all_packages)}")
        
        # Prepare output
        output_data = {
            "source_directory": str(input_dir),
            "files_processed": len(files),
            "total_packages": len(all_packages),
            "packages": all_packages
        }
        
        # Save results
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Results saved to: {output_path}")
        else:
            print(json.dumps(output_data, ensure_ascii=False, indent=2))
            
    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        sys.exit(1)


def validate_command(args):
    """
    Validate extraction results against schema.
    
    Args:
        args: Parsed command line arguments
    """
    input_path = Path(args.input)
    
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)
    
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        packages = data.get('packages', data) if isinstance(data, dict) else data
        
        if not isinstance(packages, list):
            packages = [packages]
        
        valid_count = 0
        invalid_count = 0
        errors = []
        
        for i, pkg_data in enumerate(packages):
            try:
                # Remove metadata if present
                if '_metadata' in pkg_data:
                    pkg_data = {k: v for k, v in pkg_data.items() if k != '_metadata'}
                
                # Validate against schema
                pkg = TelecomPackage(**pkg_data)
                valid_count += 1
                
            except Exception as e:
                invalid_count += 1
                errors.append({
                    "index": i,
                    "data": pkg_data,
                    "error": str(e)
                })
        
        # Print results
        print(f"\n{'='*60}")
        print("VALIDATION RESULTS")
        print(f"{'='*60}")
        print(f"Total packages: {len(packages)}")
        print(f"Valid: {valid_count}")
        print(f"Invalid: {invalid_count}")
        
        if errors and args.verbose:
            print(f"\n{'='*60}")
            print("VALIDATION ERRORS")
            print(f"{'='*60}")
            for err in errors:
                print(f"\nPackage {err['index']}:")
                print(f"  Data: {json.dumps(err['data'], ensure_ascii=False)[:200]}")
                print(f"  Error: {err['error']}")
        
        # Exit with error if invalid packages found
        if invalid_count > 0:
            sys.exit(1)
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        sys.exit(1)


def print_summary(packages: List[Dict[str, Any]]):
    """Print a summary of extracted packages."""
    print(f"\n{'='*60}")
    print(f"EXTRACTION SUMMARY")
    print(f"{'='*60}\n")
    
    # Group by partner
    by_partner = {}
    for pkg in packages:
        partner = pkg.get('partner_name', 'Unknown')
        if partner not in by_partner:
            by_partner[partner] = []
        by_partner[partner].append(pkg)
    
    for partner, pkgs in by_partner.items():
        print(f"Partner: {partner}")
        print(f"  Packages: {len(pkgs)}")
        
        # Group by service type
        by_type = {}
        for pkg in pkgs:
            stype = pkg.get('service_type', 'Unknown')
            if stype not in by_type:
                by_type[stype] = 0
            by_type[stype] += 1
        
        for stype, count in by_type.items():
            print(f"    - {stype}: {count}")
        
        print()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Telecom Package Extraction CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Extract from a single file:
    python telecom_cli.py extract --input data/processed/tv360-01_readable.txt --output results.json

  Process all files in a directory:
    python telecom_cli.py batch --input-dir data/processed --output all_packages.json

  Validate extraction results:
    python telecom_cli.py validate --input results.json --verbose
        """
    )
    
    # Global arguments
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--model',
        default='gpt-4o-mini',
        help='LLM model for extraction (default: gpt-4o-mini)'
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract packages from a document')
    extract_parser.add_argument(
        '--input', '-i',
        required=True,
        help='Input file path (PDF, JSON, or TXT)'
    )
    extract_parser.add_argument(
        '--output', '-o',
        help='Output JSON file path (prints to stdout if not specified)'
    )
    extract_parser.set_defaults(func=extract_command)
    
    # Batch command
    batch_parser = subparsers.add_parser('batch', help='Process multiple documents')
    batch_parser.add_argument(
        '--input-dir', '-d',
        required=True,
        help='Input directory containing documents'
    )
    batch_parser.add_argument(
        '--output', '-o',
        help='Output JSON file path'
    )
    batch_parser.add_argument(
        '--pattern', '-p',
        help='File name pattern (e.g., "*_readable.txt")'
    )
    batch_parser.set_defaults(func=batch_command)
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate extraction results')
    validate_parser.add_argument(
        '--input', '-i',
        required=True,
        help='JSON file with extraction results'
    )
    validate_parser.set_defaults(func=validate_command)
    
    # Parse and execute
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute the command
    args.func(args)


if __name__ == "__main__":
    main()
