#!/usr/bin/env python3
"""
Deploy Delta Package Script
Handles deployment of delta packages to Salesforce environments.
"""

import os
import sys
import argparse
import subprocess
import json
from pathlib import Path
from datetime import datetime
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DeltaPackageDeployer:
    """Handles deployment of delta packages to Salesforce."""
    
    def __init__(self, package_path, target_env, target_org, deployment_id):
        """
        Initialize the deployer.
        
        Args:
            package_path (str): Path to delta package
            target_env (str): Target environment
            target_org (str): Target Salesforce org username
            deployment_id (str): Unique deployment ID
        """
        self.package_path = Path(package_path)
        self.target_env = target_env
        self.target_org = target_org
        self.deployment_id = deployment_id
        self.deployment_status = {
            'deployment_id': deployment_id,
            'target_environment': target_env,
            'target_org': target_org,
            'package_path': str(self.package_path),
            'timestamp': datetime.now().isoformat(),
            'status': 'pending',
            'deployment_logs': []
        }
    
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
            logger.info(result.stdout)
            self.deployment_status['deployment_logs'].append(result.stdout)
        
        if result.stderr:
            logger.warning(result.stderr)
            self.deployment_status['deployment_logs'].append(result.stderr)
        
        if check and result.returncode != 0:
            raise RuntimeError(f"Command failed with exit code {result.returncode}")
        
        return result
    
    def verify_package(self):
        """Verify package is ready for deployment."""
        logger.info("Verifying package for deployment...")
        
        # Check package.xml exists
        package_xml = self.package_path / "package.xml"
        if not package_xml.exists():
            raise RuntimeError(f"package.xml not found in {self.package_path}")
        
        logger.info("✓ Package verification successful")
    
    def verify_salesforce_cli(self):
        """Verify Salesforce CLI is installed."""
        logger.info("Checking Salesforce CLI installation...")
        
        result = self.run_command("sf --version", check=False)
        
        if result.returncode != 0:
            logger.warning("⚠ Salesforce CLI (sf) not found. Attempting with sfdx...")
            result = self.run_command("sfdx --version", check=False)
            
            if result.returncode != 0:
                raise RuntimeError("Neither Salesforce CLI (sf) nor sfdx found. Please install Salesforce CLI.")
            
            self.cli_tool = "sfdx"
        else:
            self.cli_tool = "sf"
        
        logger.info(f"✓ Using {self.cli_tool} CLI")
    
    def verify_org_authentication(self):
        """Verify target org is authenticated."""
        logger.info(f"Verifying authentication for org: {self.target_org}...")
        
        if self.cli_tool == "sf":
            result = self.run_command(
                f"sf org list --all",
                check=False
            )
        else:
            result = self.run_command(
                f"sfdx force:org:list",
                check=False
            )
        
        if self.target_org not in result.stdout:
            error_msg = f"Org '{self.target_org}' not found in authenticated orgs"
            logger.error(f"✗ {error_msg}")
            logger.info("Authenticated orgs:")
            logger.info(result.stdout)
            raise RuntimeError(error_msg)
        
        logger.info(f"✓ Org '{self.target_org}' is authenticated")
    
    def deploy_package(self):
        """Deploy package to target org."""
        logger.info(f"Deploying package to {self.target_env} ({self.target_org})...")
        
        # Build deployment command
        if self.cli_tool == "sf":
            command = (
                f"sf project deploy start "
                f"--source-dir {self.package_path} "
                f"--target-org {self.target_org} "
                f"--wait 30 "
                f"--json"
            )
        else:
            command = (
                f"sfdx force:source:deploy "
                f"--sourcepath {self.package_path} "
                f"--targetusername {self.target_org} "
                f"--wait 30 "
                f"--json"
            )
        
        try:
            result = self.run_command(command)
            
            # Parse JSON response
            if result.stdout:
                try:
                    deploy_result = json.loads(result.stdout)
                    self.deployment_status['cli_response'] = deploy_result
                    
                    # Extract deployment status
                    if 'status' in deploy_result:
                        self.deployment_status['status'] = deploy_result['status']
                    
                    # Check for test results
                    if 'result' in deploy_result:
                        result_data = deploy_result['result']
                        if 'numberComponentsDeployed' in result_data:
                            logger.info(f"Components deployed: {result_data['numberComponentsDeployed']}")
                        if 'numberTestsCompleted' in result_data:
                            logger.info(f"Tests completed: {result_data['numberTestsCompleted']}")
                except json.JSONDecodeError:
                    logger.warning("Could not parse deployment response as JSON")
            
            logger.info("✓ Deployment command executed successfully")
            self.deployment_status['status'] = 'success'
            
        except RuntimeError as e:
            logger.error(f"✗ Deployment failed: {str(e)}")
            self.deployment_status['status'] = 'failed'
            raise
    
    def validate_deployment(self):
        """Validate deployment to check for errors."""
        logger.info("Validating deployment...")
        
        # Check deployment status
        if self.cli_tool == "sf":
            command = (
                f"sf project deploy report "
                f"--target-org {self.target_org} "
                f"--json"
            )
        else:
            command = (
                f"sfdx force:source:deploy:report "
                f"--targetusername {self.target_org} "
                f"--json"
            )
        
        try:
            result = self.run_command(command, check=False)
            
            if result.returncode == 0:
                logger.info("✓ Deployment validation successful")
                self.deployment_status['validation_status'] = 'passed'
            else:
                logger.warning("⚠ Deployment validation returned warnings or errors")
                self.deployment_status['validation_status'] = 'warning'
                
        except Exception as e:
            logger.warning(f"⚠ Could not validate deployment: {str(e)}")
    
    def run_post_deployment_tests(self):
        """Run post-deployment tests."""
        logger.info("Running post-deployment tests...")
        
        if self.cli_tool == "sf":
            command = (
                f"sf apex run test "
                f"--target-org {self.target_org} "
                f"--wait 10 "
                f"--json"
            )
        else:
            command = (
                f"sfdx force:apex:test:run "
                f"--targetusername {self.target_org} "
                f"--wait 10 "
                f"--json"
            )
        
        try:
            result = self.run_command(command, check=False)
            logger.info("✓ Post-deployment tests completed")
        except Exception as e:
            logger.warning(f"⚠ Error running post-deployment tests: {str(e)}")
    
    def generate_deployment_report(self):
        """Generate deployment report."""
        logger.info("Generating deployment report...")
        
        report_file = self.package_path / f"deployment_report_{self.deployment_id}.json"
        with open(report_file, 'w') as f:
            json.dump(self.deployment_status, f, indent=2)
        
        logger.info(f"✓ Deployment report saved: {report_file}")
    
    def display_summary(self):
        """Display deployment summary."""
        logger.info("=" * 70)
        logger.info("DEPLOYMENT SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Deployment ID: {self.deployment_id}")
        logger.info(f"Target Environment: {self.target_env}")
        logger.info(f"Target Org: {self.target_org}")
        logger.info(f"Package Path: {self.package_path}")
        logger.info(f"Deployment Status: {self.deployment_status['status'].upper()}")
        logger.info(f"Timestamp: {self.deployment_status['timestamp']}")
        logger.info("=" * 70)
    
    def execute(self):
        """Execute deployment."""
        try:
            logger.info("Starting deployment process...")
            logger.info(f"Target Environment: {self.target_env}")
            logger.info(f"Target Org: {self.target_org}")
            logger.info(f"Deployment ID: {self.deployment_id}")
            
            # Verification steps
            self.verify_package()
            self.verify_salesforce_cli()
            self.verify_org_authentication()
            
            # Deployment
            self.deploy_package()
            
            # Validation
            self.validate_deployment()
            
            # Post-deployment
            self.run_post_deployment_tests()
            
            # Reports
            self.generate_deployment_report()
            self.display_summary()
            
            logger.info("✓ Deployment process completed")
            return self.deployment_status['status'] == 'success'
            
        except Exception as e:
            logger.error(f"✗ Deployment failed: {str(e)}")
            self.deployment_status['status'] = 'failed'
            self.deployment_status['error'] = str(e)
            self.generate_deployment_report()
            self.display_summary()
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Deploy delta package to Salesforce environment"
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
    parser.add_argument(
        "--deployment-id",
        required=True,
        help="Unique deployment ID (e.g., Jenkins BUILD_ID)"
    )
    
    args = parser.parse_args()
    
    deployer = DeltaPackageDeployer(
        package_path=args.package_path,
        target_env=args.target_env,
        target_org=args.target_org,
        deployment_id=args.deployment_id
    )
    
    success = deployer.execute()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
