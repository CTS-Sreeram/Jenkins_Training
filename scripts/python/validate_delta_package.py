#!/usr/bin/env python3
"""
Validate Delta Package Script
Validates the delta package structure, metadata, and readiness for deployment.
"""

import os
import sys
import argparse
import json
from pathlib import Path
import logging
import xml.etree.ElementTree as ET
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DeltaPackageValidator:
    """Validates delta package structure and metadata."""
    
    # Valid Salesforce metadata file extensions
    VALID_EXTENSIONS = {
        '.cls', '.trigger', '.component', '.page', '.resource',
        '.labels', '.workflow', '.xml', '.json', '.yaml', '.yml'
    }
    
    # Required apex metadata extensions
    APEX_EXTENSIONS = {'.cls', '.trigger', '.component', '.page'}
    
    def __init__(self, package_path, target_env, target_org):
        """
        Initialize the validator.
        
        Args:
            package_path (str): Path to delta package
            target_env (str): Target environment
            target_org (str): Target Salesforce org
        """
        self.package_path = Path(package_path)
        self.target_env = target_env
        self.target_org = target_org
        self.validation_results = {
            'package_path': str(self.package_path),
            'target_environment': target_env,
            'target_org': target_org,
            'timestamp': datetime.now().isoformat(),
            'checks': {},
            'overall_status': 'pending'
        }
        self.errors = []
        self.warnings = []
    
    def validate(self):
        """Execute all validation checks."""
        logger.info("Starting delta package validation...")
        
        try:
            # Run all validation checks
            self.check_package_exists()
            self.check_package_xml()
            self.check_directory_structure()
            self.check_metadata_files()
            self.check_apex_code_quality()
            self.check_package_size()
            self.check_destructive_changes()
            
            # Determine overall status
            if self.errors:
                self.validation_results['overall_status'] = 'failed'
            elif self.warnings:
                self.validation_results['overall_status'] = 'warning'
            else:
                self.validation_results['overall_status'] = 'passed'
            
            self.validation_results['errors'] = self.errors
            self.validation_results['warnings'] = self.warnings
            
            return self.validation_results['overall_status'] == 'passed'
            
        except Exception as e:
            logger.error(f"Validation error: {str(e)}")
            self.validation_results['overall_status'] = 'failed'
            self.errors.append(f"Validation exception: {str(e)}")
            return False
    
    def check_package_exists(self):
        """Check if package directory exists."""
        logger.info("Checking package directory existence...")
        
        if not self.package_path.exists():
            error_msg = f"Package directory does not exist: {self.package_path}"
            logger.error(f"✗ {error_msg}")
            self.errors.append(error_msg)
            self.validation_results['checks']['package_exists'] = False
        else:
            logger.info(f"✓ Package directory exists: {self.package_path}")
            self.validation_results['checks']['package_exists'] = True
    
    def check_package_xml(self):
        """Check package.xml exists and is valid."""
        logger.info("Checking package.xml...")
        
        package_xml_path = self.package_path / "package.xml"
        
        if not package_xml_path.exists():
            error_msg = "package.xml not found"
            logger.error(f"✗ {error_msg}")
            self.errors.append(error_msg)
            self.validation_results['checks']['package_xml_exists'] = False
            return
        
        logger.info("✓ package.xml found")
        self.validation_results['checks']['package_xml_exists'] = True
        
        # Validate XML structure
        try:
            tree = ET.parse(package_xml_path)
            root = tree.getroot()
            
            # Check root element
            if root.tag != 'Package':
                warning = "package.xml root element is not 'Package'"
                logger.warning(f"⚠ {warning}")
                self.warnings.append(warning)
            
            # Check version
            version_elem = root.find('version')
            if version_elem is not None:
                version = version_elem.text
                logger.info(f"✓ API Version: {version}")
            else:
                warning = "No API version specified in package.xml"
                logger.warning(f"⚠ {warning}")
                self.warnings.append(warning)
            
            # Check metadata types
            types = root.findall('types')
            logger.info(f"✓ Found {len(types)} metadata types in package.xml")
            
            self.validation_results['checks']['package_xml_valid'] = True
            
        except ET.ParseError as e:
            error_msg = f"package.xml is not valid XML: {str(e)}"
            logger.error(f"✗ {error_msg}")
            self.errors.append(error_msg)
            self.validation_results['checks']['package_xml_valid'] = False
    
    def check_directory_structure(self):
        """Check if directory structure follows Salesforce standards."""
        logger.info("Checking directory structure...")
        
        required_dirs = [
            self.package_path / "force-app" / "main" / "default"
        ]
        
        all_exist = True
        for required_dir in required_dirs:
            if required_dir.exists():
                logger.info(f"✓ {required_dir} exists")
            else:
                warning = f"Expected directory not found: {required_dir}"
                logger.warning(f"⚠ {warning}")
                self.warnings.append(warning)
                all_exist = False
        
        self.validation_results['checks']['directory_structure'] = all_exist
    
    def check_metadata_files(self):
        """Check metadata files for validity."""
        logger.info("Checking metadata files...")
        
        force_app_dir = self.package_path / "force-app" / "main" / "default"
        
        if not force_app_dir.exists():
            warning = "force-app/main/default directory does not exist"
            logger.warning(f"⚠ {warning}")
            self.warnings.append(warning)
            self.validation_results['checks']['metadata_files'] = False
            return
        
        # Find all metadata files
        metadata_files = []
        for ext in self.VALID_EXTENSIONS:
            metadata_files.extend(force_app_dir.rglob(f"*{ext}"))
        
        if not metadata_files:
            warning = "No metadata files found in package"
            logger.warning(f"⚠ {warning}")
            self.warnings.append(warning)
        else:
            logger.info(f"✓ Found {len(metadata_files)} metadata files")
        
        # Check for meta.xml files for Apex classes
        meta_files_found = 0
        for metadata_file in metadata_files:
            if metadata_file.suffix in self.APEX_EXTENSIONS:
                meta_file = Path(str(metadata_file) + '-meta.xml')
                if meta_file.exists():
                    meta_files_found += 1
                else:
                    warning = f"Meta file not found: {meta_file}"
                    logger.warning(f"⚠ {warning}")
                    self.warnings.append(warning)
        
        logger.info(f"✓ Found {meta_files_found} meta.xml files")
        self.validation_results['checks']['metadata_files'] = len(metadata_files) > 0
    
    def check_apex_code_quality(self):
        """Check for common Apex code quality issues."""
        logger.info("Checking Apex code quality...")
        
        force_app_dir = self.package_path / "force-app" / "main" / "default"
        
        if not force_app_dir.exists():
            self.validation_results['checks']['apex_code_quality'] = True
            return
        
        apex_files = list(force_app_dir.rglob("*.cls")) + list(force_app_dir.rglob("*.trigger"))
        
        if not apex_files:
            logger.info("ℹ No Apex files to check")
            self.validation_results['checks']['apex_code_quality'] = True
            return
        
        issues_found = 0
        
        for apex_file in apex_files:
            try:
                with open(apex_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Check for debugging statements
                    if 'System.debug' in content:
                        warning = f"Debug statement found in {apex_file.name}"
                        logger.warning(f"⚠ {warning}")
                        self.warnings.append(warning)
                        issues_found += 1
                    
                    # Check for hardcoded values
                    if 'hardcoded' in content.lower():
                        warning = f"Potential hardcoded value in {apex_file.name}"
                        logger.warning(f"⚠ {warning}")
                        self.warnings.append(warning)
                        issues_found += 1
                    
                    # Check for empty catches
                    if 'catch' in content and 'catch (Exception e) {}' in content:
                        warning = f"Empty catch block in {apex_file.name}"
                        logger.warning(f"⚠ {warning}")
                        self.warnings.append(warning)
                        issues_found += 1
                        
            except Exception as e:
                logger.error(f"Error reading {apex_file}: {str(e)}")
        
        if issues_found == 0:
            logger.info(f"✓ No obvious code quality issues found in {len(apex_files)} Apex files")
        
        self.validation_results['checks']['apex_code_quality'] = issues_found == 0
    
    def check_package_size(self):
        """Check package size."""
        logger.info("Checking package size...")
        
        total_size = 0
        file_count = 0
        
        for file_path in self.package_path.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1
        
        size_mb = total_size / (1024 * 1024)
        logger.info(f"✓ Package size: {size_mb:.2f} MB ({file_count} files)")
        
        # Warn if too large
        if size_mb > 400:
            warning = f"Package size ({size_mb:.2f} MB) is large. Deployment may take longer."
            logger.warning(f"⚠ {warning}")
            self.warnings.append(warning)
        
        self.validation_results['checks']['package_size'] = {
            'size_mb': round(size_mb, 2),
            'file_count': file_count
        }
    
    def check_destructive_changes(self):
        """Check destructiveChanges.xml if present."""
        logger.info("Checking destructiveChanges.xml...")
        
        destructive_xml_path = self.package_path / "destructiveChanges.xml"
        
        if not destructive_xml_path.exists():
            logger.info("ℹ No destructiveChanges.xml found (no deletions)")
            self.validation_results['checks']['destructive_changes'] = True
            return
        
        try:
            tree = ET.parse(destructive_xml_path)
            root = tree.getroot()
            
            types = root.findall('types')
            deletions_count = sum(len(t.findall('members')) for t in types)
            
            logger.info(f"✓ destructiveChanges.xml found with {deletions_count} deletions")
            
            warning = f"Deployment includes {deletions_count} deletions. Review carefully!"
            logger.warning(f"⚠ {warning}")
            self.warnings.append(warning)
            
            self.validation_results['checks']['destructive_changes'] = True
            
        except ET.ParseError as e:
            error_msg = f"destructiveChanges.xml is not valid XML: {str(e)}"
            logger.error(f"✗ {error_msg}")
            self.errors.append(error_msg)
            self.validation_results['checks']['destructive_changes'] = False
    
    def generate_report(self):
        """Generate validation report."""
        logger.info("Generating validation report...")
        
        report_file = self.package_path / "validation_report.json"
        with open(report_file, 'w') as f:
            json.dump(self.validation_results, f, indent=2)
        
        logger.info(f"✓ Validation report saved: {report_file}")
    
    def display_summary(self):
        """Display validation summary."""
        logger.info("=" * 70)
        logger.info("DELTA PACKAGE VALIDATION SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Package Path: {self.package_path}")
        logger.info(f"Target Environment: {self.target_env}")
        logger.info(f"Target Org: {self.target_org}")
        logger.info(f"Overall Status: {self.validation_results['overall_status'].upper()}")
        
        if self.errors:
            logger.error(f"Errors ({len(self.errors)}):")
            for error in self.errors:
                logger.error(f"  ✗ {error}")
        
        if self.warnings:
            logger.warning(f"Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                logger.warning(f"  ⚠ {warning}")
        
        if not self.errors and not self.warnings:
            logger.info("✓ All validation checks passed")
        
        logger.info("=" * 70)
    
    def execute(self):
        """Execute validation."""
        success = self.validate()
        self.generate_report()
        self.display_summary()
        return success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate delta package structure and metadata"
    )
    parser.add_argument(
        "--package-path",
        required=True,
        help="Path to delta package"
    )
    parser.add_argument(
        "--target-env",
        required=True,
        choices=["Dev", "QA", "PROD"],
        help="Target environment"
    )
    parser.add_argument(
        "--target-org",
        required=True,
        help="Target Salesforce org username"
    )
    
    args = parser.parse_args()
    
    validator = DeltaPackageValidator(
        package_path=args.package_path,
        target_env=args.target_env,
        target_org=args.target_org
    )
    
    success = validator.execute()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
