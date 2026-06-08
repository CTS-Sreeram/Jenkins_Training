#!/usr/bin/env python3
"""
Python Scripts Directory
Contains helper scripts for Salesforce multi-environment deployment pipeline.

Scripts:
- create_promotion_branch.py: Creates promotion branches for deployments
- create_delta_package.py: Identifies changes and creates delta packages
- validate_delta_package.py: Validates package structure and metadata
- deploy_delta_package.py: Deploys packages to Salesforce environments

Requirements:
- Python 3.7+
- Salesforce CLI (sf or sfdx)
- Git
- Access to Salesforce orgs

Usage:
Each script can be run independently with --help for detailed options.
They are primarily called from the Jenkins pipeline.

Example:
  python create_promotion_branch.py --source-branch main --promotion-branch promotion/dev-to-qa/20260608_120000 --source-env Dev --target-env QA
"""
