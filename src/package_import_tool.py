"""
Package Import Tool - Xuất mẫu Excel/CSV, cho phép chỉnh sửa và import vào MySQL
Workflow: Extract PDF → Export template → Edit → Import to DB
"""
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import pandas as pd
from datetime import datetime

from sqlalchemy.orm import Session
from database import SessionLocal, Package, PackageMetadataInterpretation
from package_extractor import PackageExtractor, TelcoPackage
from pdf_processor import PDFProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PackageImportTool:
    """Tool để quản lý workflow import gói cước"""
    
    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session or SessionLocal()
        self.extractor = PackageExtractor()
    
    def extract_to_template(
        self,
        pdf_path: str,
        output_format: str = "excel",  # "excel" or "csv"
        output_dir: str = "data/templates"
    ) -> str:
        """
        Bước 1: Extract packages từ PDF và xuất ra template Excel/CSV để chỉnh sửa
        
        Args:
            pdf_path: Đường dẫn file PDF
            output_format: "excel" hoặc "csv"
            output_dir: Thư mục lưu template
            
        Returns:
            Đường dẫn file template đã tạo
        """
        logger.info(f"Extracting packages from: {pdf_path}")
        
        # Extract packages từ PDF
        processor = PDFProcessor(pdf_path)
        md_text = processor.extract_text_to_markdown(page_chunks=True, show_progress=True)
        packages = self.extractor.extract_packages_from_pages(md_text)
        
        if not packages:
            logger.warning("No packages found in PDF")
            return None
        
        # Convert to DataFrame
        df = self._packages_to_dataframe(packages)
        
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_name = Path(pdf_path).stem
        
        if output_format.lower() == "excel":
            output_path = f"{output_dir}/{pdf_name}_template_{timestamp}.xlsx"
            df.to_excel(output_path, index=False, sheet_name="Packages")
            
            # Add instructions sheet
            self._add_excel_instructions(output_path)
            
        else:  # CSV
            output_path = f"{output_dir}/{pdf_name}_template_{timestamp}.csv"
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        logger.info(f"Template created: {output_path}")
        logger.info(f"Total packages: {len(packages)}")
        
        return output_path
    
    def _packages_to_dataframe(self, packages: List[TelcoPackage]) -> pd.DataFrame:
        """Convert packages to pandas DataFrame với các cột chuẩn"""
        
        # Lấy tất cả các metadata keys
        all_keys = set()
        for pkg in packages:
            all_keys.update(pkg.metadata.keys())
        
        # Tạo rows
        rows = []
        for pkg in packages:
            row = {
                'name': pkg.name,
                'action': 'INSERT',  # INSERT, UPDATE, SKIP
                'validation_status': '',  # Để trống, user có thể check
                'notes': ''  # Ghi chú của user
            }
            
            # Add metadata fields
            for key in sorted(all_keys):
                row[f'metadata_{key}'] = pkg.metadata.get(key, '')
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        # Reorder columns
        fixed_cols = ['name', 'action', 'validation_status', 'notes']
        metadata_cols = [col for col in df.columns if col.startswith('metadata_')]
        df = df[fixed_cols + metadata_cols]
        
        return df
    
    def _add_excel_instructions(self, excel_path: str):
        """Thêm sheet hướng dẫn vào Excel file"""
        
        instructions = pd.DataFrame({
            'Field': [
                'name',
                'action',
                'validation_status',
                'notes',
                'metadata_*'
            ],
            'Description': [
                'Tên gói cước (bắt buộc, unique)',
                'Hành động: INSERT (thêm mới), UPDATE (cập nhật), SKIP (bỏ qua)',
                'Trạng thái kiểm tra (để trống hoặc ghi chú lỗi)',
                'Ghi chú riêng của bạn',
                'Các trường thông tin gói cước (price, data_limit, v.v.)'
            ],
            'Example': [
                'SD70',
                'INSERT',
                'OK',
                'Đã kiểm tra với Marketing',
                '70000'
            ]
        })
        
        tips = pd.DataFrame({
            'Tips': [
                '1. Kiểm tra lại tất cả giá trị price (số, không có dấu)',
                '2. data_unit phải là: GB/day, GB/month, MB/day',
                '3. voice_minutes: số hoặc "unlimited"',
                '4. validity_days: thường là 30 (tháng) hoặc 365 (năm)',
                '5. Đổi action thành SKIP nếu không muốn import gói đó',
                '6. Đổi action thành UPDATE nếu gói đã tồn tại và muốn cập nhật',
                '7. Sau khi chỉnh sửa xong, lưu file và chạy import'
            ]
        })
        
        # Write to Excel with multiple sheets
        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
            instructions.to_excel(writer, sheet_name='Instructions', index=False)
            tips.to_excel(writer, sheet_name='Tips', index=False)
    
    def preview_template(
        self,
        template_path: str,
        show_rows: int = 10
    ) -> pd.DataFrame:
        """
        Xem trước nội dung template
        
        Args:
            template_path: Đường dẫn file template
            show_rows: Số dòng hiển thị
            
        Returns:
            DataFrame preview
        """
        if template_path.endswith('.xlsx'):
            df = pd.read_excel(template_path, sheet_name='Packages')
        else:
            df = pd.read_csv(template_path, encoding='utf-8-sig')
        
        logger.info(f"Template loaded: {len(df)} packages")
        logger.info(f"Columns: {', '.join(df.columns)}")
        
        return df.head(show_rows)
    
    def validate_template(
        self,
        template_path: str
    ) -> Dict[str, Any]:
        """
        Kiểm tra tính hợp lệ của template trước khi import
        
        Returns:
            Dict với validation results
        """
        logger.info("Validating template...")
        
        # Load template
        if template_path.endswith('.xlsx'):
            df = pd.read_excel(template_path, sheet_name='Packages')
        else:
            df = pd.read_csv(template_path, encoding='utf-8-sig')
        
        errors = []
        warnings = []
        
        # Check required columns
        required_cols = ['name', 'action']
        for col in required_cols:
            if col not in df.columns:
                errors.append(f"Missing required column: {col}")
        
        if errors:
            return {
                'valid': False,
                'errors': errors,
                'warnings': warnings,
                'total_rows': len(df)
            }
        
        # Validate each row
        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel row (1-indexed + header)
            
            # Check name
            if pd.isna(row['name']) or str(row['name']).strip() == '':
                errors.append(f"Row {row_num}: Package name is required")
            
            # Check action
            action = str(row['action']).upper()
            if action not in ['INSERT', 'UPDATE', 'SKIP']:
                warnings.append(f"Row {row_num}: Invalid action '{action}', should be INSERT/UPDATE/SKIP")
            
            # Check price format
            if 'metadata_price' in df.columns and not pd.isna(row.get('metadata_price')):
                try:
                    price = str(row['metadata_price']).replace(',', '').replace('.', '')
                    int(price)
                except:
                    warnings.append(f"Row {row_num}: Invalid price format")
            
            # Check data_unit
            if 'metadata_data_unit' in df.columns and not pd.isna(row.get('metadata_data_unit')):
                unit = str(row['metadata_data_unit']).strip()
                valid_units = ['GB/day', 'GB/month', 'MB/day', 'MB/month']
                if unit not in valid_units:
                    warnings.append(f"Row {row_num}: data_unit should be one of {valid_units}")
        
        # Check for duplicates
        if 'name' in df.columns:
            duplicates = df[df['name'].duplicated()]['name'].tolist()
            if duplicates:
                warnings.append(f"Duplicate package names: {', '.join(map(str, duplicates))}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'total_rows': len(df),
            'insert_count': len(df[df['action'].str.upper() == 'INSERT']),
            'update_count': len(df[df['action'].str.upper() == 'UPDATE']),
            'skip_count': len(df[df['action'].str.upper() == 'SKIP'])
        }
    
    def import_from_template(
        self,
        template_path: str,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Bước 2: Import packages từ template đã chỉnh sửa vào database
        
        Args:
            template_path: Đường dẫn file template
            dry_run: Nếu True, chỉ kiểm tra không thực hiện import
            
        Returns:
            Import results
        """
        logger.info(f"Importing from template: {template_path}")
        
        # Validate first
        validation = self.validate_template(template_path)
        if not validation['valid']:
            logger.error("Template validation failed!")
            return validation
        
        # Load template
        if template_path.endswith('.xlsx'):
            df = pd.read_excel(template_path, sheet_name='Packages')
        else:
            df = pd.read_csv(template_path, encoding='utf-8-sig')
        
        # Process each row
        results = {
            'success': True,
            'inserted': 0,
            'updated': 0,
            'skipped': 0,
            'failed': 0,
            'errors': [],
            'dry_run': dry_run
        }
        
        for idx, row in df.iterrows():
            try:
                action = str(row['action']).upper()
                
                if action == 'SKIP':
                    results['skipped'] += 1
                    continue
                
                # Extract metadata fields
                metadata = {}
                for col in df.columns:
                    if col.startswith('metadata_'):
                        key = col.replace('metadata_', '')
                        value = row[col]
                        if not pd.isna(value) and str(value).strip() != '':
                            metadata[key] = str(value).strip()
                
                # Create/update package
                package_name = str(row['name']).strip()
                
                if action == 'INSERT':
                    if not dry_run:
                        # Check if exists
                        existing = self.db.query(Package).filter(
                            Package.name == package_name
                        ).first()
                        
                        if existing:
                            results['errors'].append(f"Package {package_name} already exists")
                            results['failed'] += 1
                            continue
                        
                        # Insert new
                        new_pkg = Package(
                            name=package_name,
                            package_data=metadata
                        )
                        self.db.add(new_pkg)
                    
                    results['inserted'] += 1
                    logger.info(f"INSERT: {package_name}")
                
                elif action == 'UPDATE':
                    if not dry_run:
                        # Find existing
                        existing = self.db.query(Package).filter(
                            Package.name == package_name
                        ).first()
                        
                        if not existing:
                            results['errors'].append(f"Package {package_name} not found for update")
                            results['failed'] += 1
                            continue
                        
                        # Update package_data
                        existing.package_data = metadata
                    
                    results['updated'] += 1
                    logger.info(f"UPDATE: {package_name}")
                
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"Row {idx+2}: {str(e)}")
                logger.error(f"Failed to process row {idx+2}: {e}")
        
        # Commit if not dry run
        if not dry_run and results['failed'] == 0:
            self.db.commit()
            logger.info("Database committed successfully")
        else:
            self.db.rollback()
            if dry_run:
                logger.info("Dry run completed - no changes made")
        
        return results
    
    def export_current_packages(
        self,
        output_format: str = "excel",
        output_dir: str = "data/exports"
    ) -> str:
        """
        Export gói cước hiện có trong database ra template để chỉnh sửa
        
        Returns:
            Đường dẫn file export
        """
        logger.info("Exporting current packages from database...")
        
        # Query all packages
        packages = self.db.query(Package).all()
        
        if not packages:
            logger.warning("No packages in database")
            return None
        
        # Convert to rows
        rows = []
        for pkg in packages:
            row = {
                'name': pkg.name,
                'action': 'UPDATE',  # Default to UPDATE since they exist
                'validation_status': '',
                'notes': '',
                'db_id': pkg.id,
                'created_at': pkg.created_at.strftime('%Y-%m-%d %H:%M:%S') if pkg.created_at else ''
            }
            
            # Add metadata fields
            if pkg.package_data:
                for key, value in pkg.package_data.items():
                    row[f'metadata_{key}'] = value
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if output_format.lower() == "excel":
            output_path = f"{output_dir}/packages_export_{timestamp}.xlsx"
            df.to_excel(output_path, index=False, sheet_name="Packages")
            self._add_excel_instructions(output_path)
        else:
            output_path = f"{output_dir}/packages_export_{timestamp}.csv"
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        logger.info(f"Exported {len(packages)} packages to: {output_path}")
        
        return output_path
    
    def close(self):
        """Close database session"""
        self.db.close()


def main():
    """CLI interface for package import tool"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Package Import Tool")
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract packages from PDF to template')
    extract_parser.add_argument('pdf_path', help='Path to PDF file')
    extract_parser.add_argument('--format', choices=['excel', 'csv'], default='excel', help='Output format')
    extract_parser.add_argument('--output-dir', default='data/templates', help='Output directory')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate template file')
    validate_parser.add_argument('template_path', help='Path to template file')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import packages from template to database')
    import_parser.add_argument('template_path', help='Path to template file')
    import_parser.add_argument('--dry-run', action='store_true', help='Test run without actual import')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export current packages from database')
    export_parser.add_argument('--format', choices=['excel', 'csv'], default='excel', help='Output format')
    export_parser.add_argument('--output-dir', default='data/exports', help='Output directory')
    
    # Preview command
    preview_parser = subparsers.add_parser('preview', help='Preview template file')
    preview_parser.add_argument('template_path', help='Path to template file')
    preview_parser.add_argument('--rows', type=int, default=10, help='Number of rows to show')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    tool = PackageImportTool()
    
    try:
        if args.command == 'extract':
            output = tool.extract_to_template(
                args.pdf_path,
                output_format=args.format,
                output_dir=args.output_dir
            )
            print(f"\n✓ Template created: {output}")
            print(f"\nNext steps:")
            print(f"1. Open the template file in Excel/Editor")
            print(f"2. Review and edit package information")
            print(f"3. Change 'action' column as needed (INSERT/UPDATE/SKIP)")
            print(f"4. Run: python package_import_tool.py validate {output}")
            print(f"5. Run: python package_import_tool.py import {output}")
        
        elif args.command == 'validate':
            result = tool.validate_template(args.template_path)
            print(f"\n{'='*60}")
            print(f"VALIDATION RESULTS")
            print(f"{'='*60}")
            print(f"Status: {'✓ VALID' if result['valid'] else '✗ INVALID'}")
            print(f"Total rows: {result['total_rows']}")
            print(f"  - INSERT: {result.get('insert_count', 0)}")
            print(f"  - UPDATE: {result.get('update_count', 0)}")
            print(f"  - SKIP: {result.get('skip_count', 0)}")
            
            if result['errors']:
                print(f"\n✗ ERRORS ({len(result['errors'])}):")
                for error in result['errors']:
                    print(f"  - {error}")
            
            if result['warnings']:
                print(f"\n⚠ WARNINGS ({len(result['warnings'])}):")
                for warning in result['warnings']:
                    print(f"  - {warning}")
            
            if result['valid']:
                print(f"\n✓ Template is valid and ready to import")
                print(f"Run: python package_import_tool.py import {args.template_path}")
            else:
                print(f"\n✗ Please fix errors before importing")
        
        elif args.command == 'import':
            result = tool.import_from_template(
                args.template_path,
                dry_run=args.dry_run
            )
            
            print(f"\n{'='*60}")
            print(f"IMPORT RESULTS {'(DRY RUN)' if result['dry_run'] else ''}")
            print(f"{'='*60}")
            print(f"Inserted: {result['inserted']}")
            print(f"Updated: {result['updated']}")
            print(f"Skipped: {result['skipped']}")
            print(f"Failed: {result['failed']}")
            
            if result['errors']:
                print(f"\n✗ ERRORS:")
                for error in result['errors']:
                    print(f"  - {error}")
            
            if result['dry_run']:
                print(f"\n⚠ This was a dry run. Run without --dry-run to actually import.")
            elif result['failed'] == 0:
                print(f"\n✓ Import completed successfully!")
            else:
                print(f"\n✗ Import completed with errors")
        
        elif args.command == 'export':
            output = tool.export_current_packages(
                output_format=args.format,
                output_dir=args.output_dir
            )
            print(f"\n✓ Packages exported: {output}")
            print(f"\nYou can now edit this file and import back with:")
            print(f"python package_import_tool.py import {output}")
        
        elif args.command == 'preview':
            df = tool.preview_template(args.template_path, show_rows=args.rows)
            print(f"\n{'='*60}")
            print(f"TEMPLATE PREVIEW (first {args.rows} rows)")
            print(f"{'='*60}")
            print(df.to_string())
    
    finally:
        tool.close()


if __name__ == "__main__":
    main()
