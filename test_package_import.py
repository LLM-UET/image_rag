"""
Test script để demo workflow import gói cước
Workflow: PDF → Template → Edit → Validate → Import → Verify
"""
import os
import sys
from pathlib import Path
import pymysql

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Direct imports to avoid __init__.py issues
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from package_import_tool import PackageImportTool
from database import SessionLocal, Package, init_db


def print_section(title):
    """Print section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def ensure_database_exists():
    """Ensure database exists before running tests"""
    print("Checking database setup...")
    
    # Get database config from environment or use defaults
    mysql_user = os.getenv("MYSQL_USER", "root")
    mysql_password = os.getenv("MYSQL_PASSWORD", "")
    mysql_host = os.getenv("MYSQL_HOST", "localhost")
    mysql_port = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_database = os.getenv("MYSQL_DATABASE", "telco_db")
    
    try:
        # Connect to MySQL server (without database)
        connection = pymysql.connect(
            host=mysql_host,
            port=mysql_port,
            user=mysql_user,
            password=mysql_password
        )
        
        with connection.cursor() as cursor:
            # Create database if not exists
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {mysql_database} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print(f"✓ Database '{mysql_database}' ready")
        
        connection.close()
        
        # Initialize tables using SQLAlchemy
        print("Creating tables...")
        init_db()
        print("✓ Tables created/verified")
        
        return True
        
    except pymysql.err.OperationalError as e:
        print(f"\n✗ MySQL connection failed: {e}")
        print("\nPlease ensure:")
        print("1. MySQL server is running")
        print("2. Credentials are correct in .env file:")
        print(f"   MYSQL_USER={mysql_user}")
        print(f"   MYSQL_PASSWORD=<your-password>")
        print(f"   MYSQL_HOST={mysql_host}")
        print(f"   MYSQL_PORT={mysql_port}")
        print("\nOr set environment variables before running test")
        return False
    except Exception as e:
        print(f"\n✗ Database setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def ensure_database_exists():
    """Ensure database exists before running tests"""
    print("Checking database setup...")
    
    # Get database config from environment or use defaults
    mysql_user = os.getenv("MYSQL_USER", "root")
    mysql_password = os.getenv("MYSQL_PASSWORD", "")
    mysql_host = os.getenv("MYSQL_HOST", "localhost")
    mysql_port = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_database = os.getenv("MYSQL_DATABASE", "telco_db")
    
    try:
        # Connect to MySQL server (without database)
        connection = pymysql.connect(
            host=mysql_host,
            port=mysql_port,
            user=mysql_user,
            password=mysql_password
        )
        
        with connection.cursor() as cursor:
            # Create database if not exists
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {mysql_database} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print(f"✓ Database '{mysql_database}' ready")
        
        connection.close()
        
        # Initialize tables using SQLAlchemy
        print("Creating tables...")
        init_db()
        print("✓ Tables created/verified")
        
        return True
        
    except pymysql.err.OperationalError as e:
        print(f"\n✗ MySQL connection failed: {e}")
        print("\nPlease ensure:")
        print("1. MySQL server is running")
        print("2. Credentials are correct in .env file:")
        print(f"   MYSQL_USER={mysql_user}")
        print(f"   MYSQL_PASSWORD=<your-password>")
        print(f"   MYSQL_HOST={mysql_host}")
        print(f"   MYSQL_PORT={mysql_port}")
        print("\nOr set environment variables before running test")
        return False
    except Exception as e:
        print(f"\n✗ Database setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_workflow():
    """Test complete workflow"""
    
    print_section("PACKAGE IMPORT WORKFLOW TEST")
    
    # Ensure database is ready
    if not ensure_database_exists():
        print("\n✗ Test aborted - database not ready")
        return
    
    # Ensure database is ready
    if not ensure_database_exists():
        print("\n✗ Test aborted - database not ready")
        return
    
    tool = PackageImportTool()
    
    # Step 1: Extract từ PDF (hoặc tạo sample data)
    print("📄 Step 1: Creating sample template...")
    
    # Tạo sample template thay vì extract từ PDF
    sample_data = pd.DataFrame([
        {
            'name': 'TEST_SD50',
            'action': 'INSERT',
            'validation_status': '',
            'notes': 'Test package - giá rẻ',
            'metadata_price': '50000',
            'metadata_data_limit': '2',
            'metadata_data_unit': 'GB/day',
            'metadata_voice_minutes': 'unlimited',
            'metadata_validity_days': '30',
            'metadata_sms_count': '50',
            'metadata_description': 'Gói test 2GB/ngày giá 50k'
        },
        {
            'name': 'TEST_V100',
            'action': 'INSERT',
            'validation_status': '',
            'notes': 'Test package - combo',
            'metadata_price': '100000',
            'metadata_data_limit': '3',
            'metadata_data_unit': 'GB/day',
            'metadata_voice_minutes': 'unlimited',
            'metadata_validity_days': '30',
            'metadata_sms_count': '100',
            'metadata_description': 'Gói combo 3GB + gọi thoại'
        },
        {
            'name': 'TEST_MAX150',
            'action': 'INSERT',
            'validation_status': '',
            'notes': 'Test package - cao cấp',
            'metadata_price': '150000',
            'metadata_data_limit': '5',
            'metadata_data_unit': 'GB/day',
            'metadata_voice_minutes': 'unlimited',
            'metadata_validity_days': '30',
            'metadata_sms_count': '200',
            'metadata_special_features': 'Miễn phí gọi nội mạng',
            'metadata_description': 'Gói cao cấp 5GB + nhiều ưu đãi'
        }
    ])
    
    # Save to Excel
    template_path = "data/templates/test_packages_template.xlsx"
    Path("data/templates").mkdir(parents=True, exist_ok=True)
    sample_data.to_excel(template_path, index=False, sheet_name="Packages")
    
    print(f"✓ Template created: {template_path}")
    print(f"  Total packages: {len(sample_data)}")
    
    # Step 2: Preview template
    print_section("Step 2: Preview Template")
    
    preview = tool.preview_template(template_path, show_rows=5)
    print(preview.to_string())
    
    # Step 3: Validate template
    print_section("Step 3: Validate Template")
    
    validation = tool.validate_template(template_path)
    
    print(f"Status: {'✓ VALID' if validation['valid'] else '✗ INVALID'}")
    print(f"Total rows: {validation['total_rows']}")
    print(f"  - INSERT: {validation.get('insert_count', 0)}")
    print(f"  - UPDATE: {validation.get('update_count', 0)}")
    print(f"  - SKIP: {validation.get('skip_count', 0)}")
    
    if validation['errors']:
        print(f"\n✗ ERRORS:")
        for error in validation['errors']:
            print(f"  - {error}")
    
    if validation['warnings']:
        print(f"\n⚠ WARNINGS:")
        for warning in validation['warnings']:
            print(f"  - {warning}")
    
    if not validation['valid']:
        print("\n✗ Validation failed! Stopping test.")
        return
    
    # Step 4: Dry run import
    print_section("Step 4: Dry Run Import (test without committing)")
    
    dry_result = tool.import_from_template(template_path, dry_run=True)
    
    print(f"Dry run results:")
    print(f"  - Would insert: {dry_result['inserted']}")
    print(f"  - Would update: {dry_result['updated']}")
    print(f"  - Would skip: {dry_result['skipped']}")
    print(f"  - Would fail: {dry_result['failed']}")
    
    if dry_result['errors']:
        print(f"\n✗ Errors found in dry run:")
        for error in dry_result['errors']:
            print(f"  - {error}")
    
    # Step 5: Actual import
    print_section("Step 5: Actual Import to Database")
    
    response = input("Proceed with actual import? (y/n): ")
    if response.lower() != 'y':
        print("Import cancelled by user")
        return
    
    import_result = tool.import_from_template(template_path, dry_run=False)
    
    print(f"\nImport results:")
    print(f"  ✓ Inserted: {import_result['inserted']}")
    print(f"  ✓ Updated: {import_result['updated']}")
    print(f"  - Skipped: {import_result['skipped']}")
    print(f"  ✗ Failed: {import_result['failed']}")
    
    if import_result['errors']:
        print(f"\n✗ Errors:")
        for error in import_result['errors']:
            print(f"  - {error}")
    
    if import_result['failed'] == 0:
        print(f"\n✓ Import completed successfully!")
    
    # Step 6: Verify in database
    print_section("Step 6: Verify Packages in Database")
    
    db = SessionLocal()
    try:
        # Query test packages
        test_packages = db.query(Package).filter(
            Package.name.like('TEST_%')
        ).all()
        
        print(f"Found {len(test_packages)} test packages in database:\n")
        
        for pkg in test_packages:
            print(f"Package: {pkg.name}")
            print(f"  ID: {pkg.id}")
            print(f"  Created: {pkg.created_at}")
            print(f"  Metadata:")
            for key, value in pkg.package_data.items():
                print(f"    - {key}: {value}")
            print()
    
    finally:
        db.close()
    
    # Step 7: Export và update test
    print_section("Step 7: Export & Update Test")
    
    export_path = tool.export_current_packages(output_format='excel')
    print(f"✓ Exported current packages to: {export_path}")
    
    # Modify export file to test UPDATE
    print("\nModifying exported template to test UPDATE...")
    df = pd.read_excel(export_path, sheet_name='Packages')
    
    # Filter test packages only
    test_df = df[df['name'].str.startswith('TEST_')]
    
    if len(test_df) > 0:
        # Update prices
        test_df['metadata_price'] = test_df['metadata_price'].astype(str).str.replace(',', '').astype(float) + 10000
        test_df['action'] = 'UPDATE'
        test_df['notes'] = 'Updated: price +10k'
        
        # Save modified template
        update_template_path = "data/templates/test_packages_update.xlsx"
        test_df.to_excel(update_template_path, index=False, sheet_name="Packages")
        
        print(f"✓ Created update template: {update_template_path}")
        
        # Validate update template
        update_validation = tool.validate_template(update_template_path)
        print(f"\nUpdate template validation: {'✓ VALID' if update_validation['valid'] else '✗ INVALID'}")
        
        # Import updates
        response = input("\nProceed with UPDATE import? (y/n): ")
        if response.lower() == 'y':
            update_result = tool.import_from_template(update_template_path, dry_run=False)
            print(f"\nUpdate results:")
            print(f"  ✓ Updated: {update_result['updated']}")
            print(f"  ✗ Failed: {update_result['failed']}")
            
            # Verify updates
            db = SessionLocal()
            try:
                updated_packages = db.query(Package).filter(
                    Package.name.like('TEST_%')
                ).all()
                
                print(f"\nVerifying updated packages:")
                for pkg in updated_packages:
                    print(f"  {pkg.name}: price = {pkg.package_data.get('price', 'N/A')}")
            finally:
                db.close()
    
    # Step 8: Cleanup
    print_section("Step 8: Cleanup")
    
    response = input("Delete test packages from database? (y/n): ")
    if response.lower() == 'y':
        db = SessionLocal()
        try:
            deleted = db.query(Package).filter(
                Package.name.like('TEST_%')
            ).delete()
            db.commit()
            print(f"✓ Deleted {deleted} test packages")
        finally:
            db.close()
    
    tool.close()
    
    print_section("TEST COMPLETED")
    print("Files created:")
    print(f"  - {template_path}")
    print(f"  - {export_path}")
    if 'update_template_path' in locals():
        print(f"  - {update_template_path}")


def test_error_handling():
    """Test error cases"""
    
    print_section("ERROR HANDLING TEST")
    
    # Ensure database is ready
    if not ensure_database_exists():
        print("\n✗ Test aborted - database not ready")
        return
    
    tool = PackageImportTool()
    
    # Create invalid template
    invalid_data = pd.DataFrame([
        {
            'name': '',  # Empty name - should fail
            'action': 'INSERT',
            'metadata_price': 'invalid_price',  # Invalid format
            'metadata_data_unit': 'WRONG_UNIT'  # Invalid unit
        },
        {
            'name': 'TEST_DUP',
            'action': 'INVALID_ACTION',  # Invalid action
            'metadata_price': '50000'
        },
        {
            'name': 'TEST_DUP',  # Duplicate
            'action': 'INSERT',
            'metadata_price': '60000'
        }
    ])
    
    invalid_path = "data/templates/test_invalid_template.xlsx"
    Path("data/templates").mkdir(parents=True, exist_ok=True)
    invalid_data.to_excel(invalid_path, index=False, sheet_name="Packages")
    
    print(f"Created invalid template: {invalid_path}\n")
    
    # Validate - should find errors
    validation = tool.validate_template(invalid_path)
    
    print(f"Validation status: {'✓ VALID' if validation['valid'] else '✗ INVALID'}")
    print(f"\nErrors found ({len(validation['errors'])}):")
    for error in validation['errors']:
        print(f"  ✗ {error}")
    
    print(f"\nWarnings found ({len(validation['warnings'])}):")
    for warning in validation['warnings']:
        print(f"  ⚠ {warning}")
    
    tool.close()
    
    print_section("ERROR HANDLING TEST COMPLETED")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test package import workflow")
    parser.add_argument('--test', choices=['full', 'errors', 'all'], default='full',
                       help='Test type to run')
    
    args = parser.parse_args()
    
    try:
        if args.test in ['full', 'all']:
            test_full_workflow()
        
        if args.test in ['errors', 'all']:
            test_error_handling()
    
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
