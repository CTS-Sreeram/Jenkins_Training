#!/usr/bin/env python3
"""
Create Promotion Branch Script
Handles creation and initialization of promotion branches for Salesforce deployments.
"""

import os
import sys
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PromotionBranchManager:
    """Manages creation and initialization of promotion branches."""
    
    def __init__(self, source_branch, promotion_branch, source_env, target_env):
        """
        Initialize the promotion branch manager.
        
        Args:
            source_branch (str): Source branch name
            promotion_branch (str): Promotion branch name
            source_env (str): Source environment (Dev, QA, PROD)
            target_env (str): Target environment (Dev, QA, PROD)
        """
        self.source_branch = source_branch
        self.promotion_branch = promotion_branch
        self.source_env = source_env
        self.target_env = target_env
        self.workspace = os.getcwd()
        self.promotion_metadata = {}
        
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
        if result.stderr:
            logger.warning(result.stderr)
            
        if check and result.returncode != 0:
            raise RuntimeError(f"Command failed with exit code {result.returncode}")
            
        return result
    
    def verify_git_setup(self):
        """Verify git is properly configured."""
        logger.info("Verifying git setup...")
        
        try:
            self.run_command("git --version")
            logger.info("✓ Git is installed")
        except RuntimeError:
            logger.error("✗ Git is not installed or not in PATH")
            raise
            
        # Verify we're in a git repository
        try:
            self.run_command("git rev-parse --git-dir")
            logger.info("✓ Current directory is a git repository")
        except RuntimeError:
            logger.error("✗ Not in a git repository")
            raise
    
    def verify_source_branch_exists(self):
        """Verify source branch exists."""
        logger.info(f"Verifying source branch '{self.source_branch}' exists...")
        
        result = self.run_command(
            f"git rev-parse --verify {self.source_branch}",
            check=False
        )
        
        if result.returncode != 0:
            logger.error(f"✗ Source branch '{self.source_branch}' does not exist")
            raise RuntimeError(f"Source branch '{self.source_branch}' not found")
        
        logger.info(f"✓ Source branch '{self.source_branch}' exists")
    
    def verify_branch_not_exists(self):
        """Verify promotion branch doesn't already exist."""
        logger.info(f"Checking if promotion branch '{self.promotion_branch}' already exists...")
        
        result = self.run_command(
            f"git rev-parse --verify {self.promotion_branch}",
            check=False
        )
        
        if result.returncode == 0:
            logger.warning(f"⚠ Promotion branch '{self.promotion_branch}' already exists")
            logger.info("Deleting existing promotion branch...")
            self.run_command(f"git branch -D {self.promotion_branch}", check=False)
        else:
            logger.info(f"✓ Promotion branch '{self.promotion_branch}' doesn't exist")
    
    def create_promotion_branch(self):
        """Create the promotion branch from source branch."""
        logger.info(f"Creating promotion branch '{self.promotion_branch}' from '{self.source_branch}'...")
        
        self.run_command(f"git checkout {self.source_branch}")
        self.run_command(f"git pull origin {self.source_branch}", check=False)
        self.run_command(f"git checkout -b {self.promotion_branch}")
        
        logger.info(f"✓ Promotion branch '{self.promotion_branch}' created successfully")
    
    def create_promotion_metadata(self):
        """Create metadata file for promotion."""
        logger.info("Creating promotion metadata...")
        
        self.promotion_metadata = {
            "promotion_branch": self.promotion_branch,
            "source_branch": self.source_branch,
            "source_environment": self.source_env,
            "target_environment": self.target_env,
            "created_timestamp": datetime.now().isoformat(),
            "created_by": self._get_git_user(),
            "workspace": self.workspace,
            "status": "created"
        }
        
        # Create .promotion directory if it doesn't exist
        promotion_dir = Path(self.workspace) / ".promotion"
        promotion_dir.mkdir(exist_ok=True)
        
        # Write metadata file
        metadata_file = promotion_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(self.promotion_metadata, f, indent=2)
        
        logger.info(f"✓ Promotion metadata created: {metadata_file}")
        
        # Add to git
        self.run_command(f"git add {metadata_file}")
    
    def _get_git_user(self):
        """Get current git user."""
        result = self.run_command("git config user.name", check=False)
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    
    def create_promotion_readme(self):
        """Create README file for promotion."""
        logger.info("Creating promotion README...")
        
        readme_content = f"""# Promotion Branch: {self.promotion_branch}

## Overview
This is an automated promotion branch for Salesforce deployment.

- **Source Environment:** {self.source_env}
- **Target Environment:** {self.target_env}
- **Source Branch:** {self.source_branch}
- **Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Created By:** {self._get_git_user()}

## Purpose
This branch contains delta changes identified between {self.source_env} and {self.target_env} environments.

## Stages
1. Delta package identification
2. Merge delta changes
3. Apex PMD analysis
4. Package validation
5. Deployment to {self.target_env}

## Important Notes
- **Do not merge this branch directly into main or develop**
- Wait for all pipeline validations to complete
- Review validation results before deploying
- Keep this branch until deployment is confirmed successful

## Next Steps
1. Review delta package contents
2. Validate package integrity
3. Deploy to {self.target_env}
4. Verify deployment success
5. Merge promotion branch to tracking branch

---
*This branch was created automatically by Jenkins Pipeline*
"""
        
        # Create .promotion directory if it doesn't exist
        promotion_dir = Path(self.workspace) / ".promotion"
        promotion_dir.mkdir(exist_ok=True)
        
        # Write README file
        readme_file = promotion_dir / "PROMOTION_README.md"
        with open(readme_file, 'w') as f:
            f.write(readme_content)
        
        logger.info(f"✓ Promotion README created: {readme_file}")
        
        # Add to git
        self.run_command(f"git add {readme_file}")
    
    def create_promotion_hooks(self):
        """Create git hooks for promotion branch."""
        logger.info("Setting up promotion branch hooks...")
        
        hooks_dir = Path(self.workspace) / ".git" / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        
        # Create pre-commit hook to prevent accidental commits
        pre_commit_hook = hooks_dir / "pre-commit"
        hook_content = f"""#!/bin/bash
# Prevent accidental commits on promotion branches

BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [[ $BRANCH == promotion/* ]]; then
    echo "⚠️  WARNING: You are on a promotion branch ($BRANCH)"
    echo "This branch should only be modified by the automated pipeline."
    echo "Direct commits to promotion branches are discouraged."
    echo ""
    echo "If you need to make changes:"
    echo "1. Create a feature branch"
    echo "2. Make your changes"
    echo "3. Submit a pull request"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

exit 0
"""
        
        with open(pre_commit_hook, 'w') as f:
            f.write(hook_content)
        
        os.chmod(pre_commit_hook, 0o755)
        logger.info(f"✓ Pre-commit hook created: {pre_commit_hook}")
    
    def commit_promotion_setup(self):
        """Commit promotion branch setup."""
        logger.info("Committing promotion branch setup...")
        
        # Check if there are changes to commit
        result = self.run_command("git status --porcelain", check=False)
        
        if result.stdout.strip():
            self.run_command(
                f"git commit -m 'Initialize promotion branch: {self.promotion_branch}\n\n"
                f"Source Environment: {self.source_env}\n"
                f"Target Environment: {self.target_env}\n"
                f"Source Branch: {self.source_branch}'"
            )
            logger.info("✓ Promotion branch setup committed")
        else:
            logger.info("ℹ No changes to commit for promotion setup")
    
    def display_branch_info(self):
        """Display promotion branch information."""
        logger.info("=" * 70)
        logger.info("PROMOTION BRANCH CREATED SUCCESSFULLY")
        logger.info("=" * 70)
        logger.info(f"Promotion Branch: {self.promotion_branch}")
        logger.info(f"Source Environment: {self.source_env}")
        logger.info(f"Target Environment: {self.target_env}")
        logger.info(f"Source Branch: {self.source_branch}")
        logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 70)
        
        # Display git log
        logger.info("Recent commits:")
        self.run_command("git log --oneline -5")
    
    def execute(self):
        """Execute the promotion branch creation process."""
        try:
            logger.info("Starting promotion branch creation process...")
            logger.info(f"Source: {self.source_env} ({self.source_branch})")
            logger.info(f"Target: {self.target_env}")
            
            # Verify git setup
            self.verify_git_setup()
            
            # Verify source branch exists
            self.verify_source_branch_exists()
            
            # Check if promotion branch already exists
            self.verify_branch_not_exists()
            
            # Create promotion branch
            self.create_promotion_branch()
            
            # Create metadata
            self.create_promotion_metadata()
            
            # Create README
            self.create_promotion_readme()
            
            # Create hooks
            self.create_promotion_hooks()
            
            # Commit setup
            self.commit_promotion_setup()
            
            # Display information
            self.display_branch_info()
            
            logger.info("✓ Promotion branch creation completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"✗ Error: {str(e)}")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Create Salesforce promotion branch for multi-environment deployment"
    )
    parser.add_argument(
        "--source-branch",
        required=True,
        help="Source branch name (e.g., main, release/qa)"
    )
    parser.add_argument(
        "--promotion-branch",
        required=True,
        help="Promotion branch name"
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
    
    manager = PromotionBranchManager(
        source_branch=args.source_branch,
        promotion_branch=args.promotion_branch,
        source_env=args.source_env,
        target_env=args.target_env
    )
    
    success = manager.execute()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
