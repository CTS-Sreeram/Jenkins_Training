#!/usr/bin/env python3
"""
Create Delta Package Script
Identifies changed files between two branches and creates a delta package.
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
import shutil
import json
import logging
from datetime import datetime
import xml.etree.ElementTree as ET

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DeltaPackageCreator:
    """Creates delta packages by identifying changed files between branches."""
    
    # Salesforce metadata folder mappings
    METADATA_TYPES = {
        'classes': 'ApexClass',
        'components': 'ApexComponent',
        'pages': 'ApexPage',
        'triggers': 'ApexTrigger',
        'objects': 'CustomObject',
        'flows': 'Flow',
        'layouts': 'Layout',
        'profiles': 'Profile',
        'permissionsets': 'PermissionSet',
        'staticresources': 'StaticResource',
        'labels': 'CustomLabel',
        'customMetadata': 'CustomMetadata',
        'settings': 'Settings',
    }
    
    def __init__(self, source_branch, target_branch, output_path, source_env, target_env):
        """
        Initialize the delta package creator.
        
        Args:
            source_branch (str): Source branch name
            target_branch (str): Target branch name (promotion branch)
            output_path (str): Output directory for delta package
            source_env (str): Source environment
            target_env (str): Target environment
        """
        self.source_branch = source_branch
        self.target_branch = target_branch
        self.output_path = Path(output_path)
        self.source_env = source_env
        self.target_env = target_env
        self.workspace = Path(os.getcwd())
        self.changed_files = []
        self.metadata_types_used = set()
        
    def run_command(self, command, check=True):
        """
        Execute a shell command.
        
        Args:
            command (str): Command to execute
            check (bool): Raise exception on non-zero exit code
            
        Returns:
            subprocess.CompletedProcess: Command result
        """
        logger.info(f"Executing: {command}")
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.stdout:
            logger.debug(result.stdout)
        if result.stderr:
            logger.debug(result.stderr)
            
        if check and result.returncode != 0:
            raise RuntimeError(f"Command failed with exit code {result.returncode}")
            
        return result
    
    def verify_branches_exist(self):
        """Verify both branches exist."""
        logger.info("Verifying branches exist...")
        
        for branch in [self.source_branch, self.target_branch]:
            result = self.run_command(
                f"git rev-parse --verify {branch}",
                check=False
            )
            if result.returncode != 0:
                raise RuntimeError(f"Branch '{branch}' does not exist")
        
        logger.info("✓ Both branches exist")
    
    def identify_changed_files(self):
        """Identify changed files between source and target branches."""
        logger.info(f"Identifying changes between '{self.source_branch}' and '{self.target_branch}'...")
        
        # Get diff between branches
        result = self.run_command(
            f"git diff --name-status {self.source_branch}...{self.target_branch}"
        )
        
        if not result.stdout.strip():
            logger.warning("⚠ No changes found between branches")
            self.changed_files = []
            return
        
        # Parse diff output
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split('\t')
            status = parts[0]  # M=Modified, A=Added, D=Deleted, R=Renamed
            filepath = parts[1]
            
            # Only include Salesforce metadata files
            if self._is_salesforce_file(filepath):
                self.changed_files.append({
                    'path': filepath,
                    'status': status,
                    'type': self._get_metadata_type(filepath)
                })
                logger.info(f"  [{status}] {filepath}")
        
        logger.info(f"✓ Identified {len(self.changed_files)} changed Salesforce files")
    
    def _is_salesforce_file(self, filepath):
        """Check if file is a Salesforce metadata file."""
        salesforce_dirs = [
            'force-app',
            'src',
            'classes',
            'components',
            'pages',
            'triggers',
            'objects',
            'flows',
            'layouts',
            'profiles',
            'permissionsets'
        ]
        
        # Check if file is in a Salesforce directory
        for dir_name in salesforce_dirs:
            if dir_name in filepath:
                return True
        
        return False
    
    def _get_metadata_type(self, filepath):
        """Get Salesforce metadata type from filepath."""
        filepath_lower = filepath.lower()
        
        for folder, metadata_type in self.METADATA_TYPES.items():
            if f"/{folder}/" in filepath_lower or f"\\{folder}\\" in filepath_lower:
                return metadata_type
        
        return "Unknown"
    
    def create_directory_structure(self):
        """Create delta package directory structure."""
        logger.info(f"Creating delta package directory structure at {self.output_path}...")
        
        # Create main directories
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # Create force-app structure
        force_app_dir = self.output_path / "force-app" / "main" / "default"
        force_app_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✓ Directory structure created")
    
    def copy_changed_files(self):
        """Copy changed files to delta package."""
        logger.info("Copying changed files to delta package...")
        
        copied_count = 0
        
        for file_info in self.changed_files:
            filepath = file_info['path']
            status = file_info['status']
            
            # Skip deleted files in delta package (will be handled in destructiveChanges.xml)
            if status == 'D':
                continue
            
            source_file = self.workspace / filepath
            
            # Determine relative path in delta package
            # Remove 'force-app/main/default/' prefix if present
            relative_parts = Path(filepath).parts
            
            if 'force-app' in relative_parts:
                idx = relative_parts.index('force-app')
                relative_path = Path(*relative_parts[idx+3:])  # Skip force-app/main/default
            else:
                relative_path = Path(filepath)
            
            # Reconstruct target path
            target_file = self.output_path / "force-app" / "main" / "default" / relative_path
            target_file.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                if source_file.exists():
                    shutil.copy2(source_file, target_file)
                    copied_count += 1
                    logger.info(f"  Copied: {filepath}")
                else:
                    logger.warning(f"  Source file not found: {filepath}")
            except Exception as e:
                logger.error(f"  Error copying {filepath}: {str(e)}")
        
        logger.info(f"✓ Copied {copied_count} files to delta package")
    
    def create_package_xml(self):
        """Create package.xml for delta package."""
        logger.info("Creating package.xml...")
        
        # Collect metadata types used
        metadata_types = {}
        for file_info in self.changed_files:
            metadata_type = file_info['type']
            if metadata_type not in metadata_types:
                metadata_types[metadata_type] = []
            
            # Extract member name (filename without extension)
            filepath = Path(file_info['path'])
            member_name = filepath.stem
            if member_name not in metadata_types[metadata_type]:
                metadata_types[metadata_type].append(member_name)
        
        # Create XML root
        root = ET.Element('Package')
        root.set('xmlns', 'http://soap.sforce.com/2006/04/metadata')
        
        # Add types
        for metadata_type in sorted(metadata_types.keys()):
            if metadata_type == "Unknown":
                continue
            
            types_elem = ET.SubElement(root, 'types')
            for member in sorted(metadata_types[metadata_type]):
                member_elem = ET.SubElement(types_elem, 'members')
                member_elem.text = member
            
            name_elem = ET.SubElement(types_elem, 'name')
            name_elem.text = metadata_type
        
        # Add API version
        api_version = ET.SubElement(root, 'version')
        api_version.text = '58.0'  # Latest version
        
        # Create package.xml file
        package_xml_path = self.output_path / "package.xml"
        tree = ET.ElementTree(root)
        ET.indent(root, space="    ")
        tree.write(package_xml_path, encoding='UTF-8', xml_declaration=True)
        
        logger.info(f"✓ Created package.xml with {len(metadata_types)} metadata types")
        self._print_package_xml(package_xml_path)
    
    def _print_package_xml(self, filepath):
        """Print package.xml content for logging."""
        with open(filepath, 'r') as f:
            logger.info("Package.xml content:")
            for line in f:
                logger.info(f"  {line.rstrip()}")
    
    def create_destructive_changes_xml(self):
        """Create destructiveChanges.xml for deleted files."""
        logger.info("Creating destructiveChanges.xml...")
        
        deleted_files = [f for f in self.changed_files if f['status'] == 'D']
        
        if not deleted_files:
            logger.info("ℹ No deleted files, skipping destructiveChanges.xml")
            return
        
        # Collect metadata types for deleted files
        metadata_types = {}
        for file_info in deleted_files:
            metadata_type = file_info['type']
            if metadata_type not in metadata_types:
                metadata_types[metadata_type] = []
            
            filepath = Path(file_info['path'])
            member_name = filepath.stem
            if member_name not in metadata_types[metadata_type]:
                metadata_types[metadata_type].append(member_name)
        
        # Create XML root
        root = ET.Element('Package')
        root.set('xmlns', 'http://soap.sforce.com/2006/04/metadata')
        
        # Add types
        for metadata_type in sorted(metadata_types.keys()):
            if metadata_type == "Unknown":
                continue
            
            types_elem = ET.SubElement(root, 'types')
            for member in sorted(metadata_types[metadata_type]):
                member_elem = ET.SubElement(types_elem, 'members')
                member_elem.text = member
            
            name_elem = ET.SubElement(types_elem, 'name')
            name_elem.text = metadata_type
        
        # Add API version
        api_version = ET.SubElement(root, 'version')
        api_version.text = '58.0'
        
        # Create destructiveChanges.xml file
        destructive_xml_path = self.output_path / "destructiveChanges.xml"
        tree = ET.ElementTree(root)
        ET.indent(root, space="    ")
        tree.write(destructive_xml_path, encoding='UTF-8', xml_declaration=True)
        
        logger.info(f"✓ Created destructiveChanges.xml with {len(deleted_files)} deletions")
    
    def create_delta_summary(self):
        """Create summary report of delta package."""
        logger.info("Creating delta package summary...")
        
        summary = {
            "delta_package_info": {
                "created_timestamp": datetime.now().isoformat(),
                "source_environment": self.source_env,
                "target_environment": self.target_env,
                "source_branch": self.source_branch,
                "target_branch": self.target_branch
            },
            "statistics": {
                "total_files_changed": len(self.changed_files),
                "added": len([f for f in self.changed_files if f['status'] == 'A']),
                "modified": len([f for f in self.changed_files if f['status'] == 'M']),
                "deleted": len([f for f in self.changed_files if f['status'] == 'D']),
                "renamed": len([f for f in self.changed_files if f['status'] == 'R'])
            },
            "changed_files": self.changed_files
        }
        
        summary_file = self.output_path / "delta_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"✓ Created delta summary: {summary_file}")
        
        # Print summary
        stats = summary['statistics']
        logger.info("Delta Package Statistics:")
        logger.info(f"  Total Changes: {stats['total_files_changed']}")
        logger.info(f"  Added: {stats['added']}")
        logger.info(f"  Modified: {stats['modified']}")
        logger.info(f"  Deleted: {stats['deleted']}")
        logger.info(f"  Renamed: {stats['renamed']}")
    
    def create_deployment_info(self):
        """Create deployment information file."""
        logger.info("Creating deployment information file...")
        
        deployment_info = {
            "deployment_type": "delta_package",
            "source_environment": self.source_env,
            "target_environment": self.target_env,
            "package_location": str(self.output_path),
            "package_xml": str(self.output_path / "package.xml"),
            "destructive_xml": str(self.output_path / "destructiveChanges.xml"),
            "created_timestamp": datetime.now().isoformat(),
            "validation_status": "pending",
            "deployment_status": "pending"
        }
        
        info_file = self.output_path / "deployment_info.json"
        with open(info_file, 'w') as f:
            json.dump(deployment_info, f, indent=2)
        
        logger.info(f"✓ Created deployment info: {info_file}")
    
    def display_summary(self):
        """Display delta package summary."""
        logger.info("=" * 70)
        logger.info("DELTA PACKAGE CREATED SUCCESSFULLY")
        logger.info("=" * 70)
        logger.info(f"Source Environment: {self.source_env}")
        logger.info(f"Target Environment: {self.target_env}")
        logger.info(f"Source Branch: {self.source_branch}")
        logger.info(f"Target Branch: {self.target_branch}")
        logger.info(f"Output Path: {self.output_path}")
        logger.info(f"Total Changes: {len(self.changed_files)}")
        logger.info("=" * 70)
    
    def execute(self):
        """Execute delta package creation."""
        try:
            logger.info("Starting delta package creation...")
            
            # Verify branches
            self.verify_branches_exist()
            
            # Identify changes
            self.identify_changed_files()
            
            if not self.changed_files:
                logger.warning("No Salesforce files changed between branches")
            
            # Create structure
            self.create_directory_structure()
            
            # Copy files
            if self.changed_files:
                self.copy_changed_files()
            
            # Create metadata files
            self.create_package_xml()
            self.create_destructive_changes_xml()
            
            # Create summary files
            self.create_delta_summary()
            self.create_deployment_info()
            
            # Display summary
            self.display_summary()
            
            logger.info("✓ Delta package creation completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"✗ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Create delta package by identifying changes between branches"
    )
    parser.add_argument(
        "--source-branch",
        required=True,
        help="Source branch name"
    )
    parser.add_argument(
        "--target-branch",
        required=True,
        help="Target branch name (promotion branch)"
    )
    parser.add_argument(
        "--output-path",
        required=True,
        help="Output path for delta package"
    )
    parser.add_argument(
        "--source-env",
        required=True,
        choices=["Dev", "QA", "PROD"],
        help="Source environment"
    )
    parser.add_argument(
        "--target-env",
        required=True,
        choices=["Dev", "QA", "PROD"],
        help="Target environment"
    )
    
    args = parser.parse_args()
    
    creator = DeltaPackageCreator(
        source_branch=args.source_branch,
        target_branch=args.target_branch,
        output_path=args.output_path,
        source_env=args.source_env,
        target_env=args.target_env
    )
    
    success = creator.execute()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
