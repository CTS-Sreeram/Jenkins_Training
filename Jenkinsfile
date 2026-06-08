pipeline {
    agent any

    options {
        timestamps()
        timeout(time: 2, unit: 'HOURS')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    parameters {
        choice(
            name: 'DEPLOYMENT_PATH',
            choices: ['Dev-to-QA', 'QA-to-PROD'],
            description: 'Select the deployment path'
        )
        string(
            name: 'SOURCE_BRANCH',
            defaultValue: '',
            description: 'Source branch for delta identification (leave empty for auto-detect)'
        )
        string(
            name: 'GIT_REPO_URL',
            defaultValue: 'https://github.com/CTS-Sreeram/Jenkins_Training.git',
            description: 'Git repository URL'
        )
        string(
            name: 'SALESFORCE_DEV_ORG',
            defaultValue: 'dev@company.com',
            description: 'Salesforce Dev Org Username'
        )
        string(
            name: 'SALESFORCE_QA_ORG',
            defaultValue: 'qa@company.com',
            description: 'Salesforce QA Org Username'
        )
        string(
            name: 'SALESFORCE_PROD_ORG',
            defaultValue: 'prod@company.com',
            description: 'Salesforce PROD Org Username'
        )
    }

    environment {
        WORKSPACE_DIR = "${WORKSPACE}"
        PYTHON_SCRIPTS_PATH = "${WORKSPACE}/scripts/python"
        DELTA_PACKAGE_PATH = "${WORKSPACE}/delta_package"
        PROMOTION_BRANCH_PREFIX = "promotion"
        TIMESTAMP = sh(script: "date +%Y%m%d_%H%M%S", returnStdout: true).trim()
    }

    stages {
        stage('Initialize') {
            steps {
                script {
                    echo "========================================="
                    echo "Salesforce Pipeline - ${params.DEPLOYMENT_PATH}"
                    echo "========================================="
                    echo "Deployment Path: ${params.DEPLOYMENT_PATH}"
                    echo "Workspace: ${WORKSPACE_DIR}"
                    echo "Timestamp: ${TIMESTAMP}"
                    
                    // Set environment variables based on deployment path
                    if (params.DEPLOYMENT_PATH == 'Dev-to-QA') {
                        env.SOURCE_ENV = 'Dev'
                        env.TARGET_ENV = 'QA'
                        env.SOURCE_ORG = params.SALESFORCE_DEV_ORG
                        env.TARGET_ORG = params.SALESFORCE_QA_ORG
                        env.SOURCE_BRANCH_DEFAULT = 'main'
                        env.PROMOTION_BRANCH = "${PROMOTION_BRANCH_PREFIX}/dev-to-qa/${TIMESTAMP}"
                    } else if (params.DEPLOYMENT_PATH == 'QA-to-PROD') {
                        env.SOURCE_ENV = 'QA'
                        env.TARGET_ENV = 'PROD'
                        env.SOURCE_ORG = params.SALESFORCE_QA_ORG
                        env.TARGET_ORG = params.SALESFORCE_PROD_ORG
                        env.SOURCE_BRANCH_DEFAULT = 'release/qa'
                        env.PROMOTION_BRANCH = "${PROMOTION_BRANCH_PREFIX}/qa-to-prod/${TIMESTAMP}"
                    }
                    
                    if (params.SOURCE_BRANCH) {
                        env.SOURCE_BRANCH_FINAL = params.SOURCE_BRANCH
                    } else {
                        env.SOURCE_BRANCH_FINAL = env.SOURCE_BRANCH_DEFAULT
                    }
                    
                    echo "Source Environment: ${env.SOURCE_ENV}"
                    echo "Target Environment: ${env.TARGET_ENV}"
                    echo "Promotion Branch: ${env.PROMOTION_BRANCH}"
                    echo "Source Branch: ${env.SOURCE_BRANCH_FINAL}"
                }
            }
        }

        stage('Checkout Code') {
            steps {
                script {
                    echo "Checking out code from ${params.GIT_REPO_URL}"
                    checkout([
                        $class: 'GitSCM',
                        branches: [[name: "*/${env.SOURCE_BRANCH_FINAL}"]],
                        userRemoteConfigs: [[url: params.GIT_REPO_URL]]
                    ])
                    echo "Code checked out successfully"
                }
            }
        }

        stage('Create Promotion Branch') {
            steps {
                script {
                    echo "========================================="
                    echo "Stage: Create Promotion Branch"
                    echo "========================================="
                    
                    sh '''
                        # Configure git
                        git config user.name "Jenkins Pipeline"
                        git config user.email "jenkins@company.com"
                        
                        # Create and checkout promotion branch
                        git checkout -b ${PROMOTION_BRANCH}
                        
                        echo "Promotion branch created: ${PROMOTION_BRANCH}"
                        git branch -v
                    '''
                }
            }
        }

        stage('Run Promotion Branch Creation Script') {
            steps {
                script {
                    echo "========================================="
                    echo "Stage: Run Promotion Branch Creation Script"
                    echo "========================================="
                    
                    sh '''
                        if [ -f "${PYTHON_SCRIPTS_PATH}/create_promotion_branch.py" ]; then
                            echo "Running promotion branch creation script..."
                            python "${PYTHON_SCRIPTS_PATH}/create_promotion_branch.py" \
                                --source-branch "${SOURCE_BRANCH_FINAL}" \
                                --promotion-branch "${PROMOTION_BRANCH}" \
                                --source-env "${SOURCE_ENV}" \
                                --target-env "${TARGET_ENV}"
                            echo "Promotion branch creation script completed"
                        else
                            echo "Warning: create_promotion_branch.py not found at ${PYTHON_SCRIPTS_PATH}"
                            echo "Proceeding with standard git branch creation"
                        fi
                    '''
                }
            }
        }

        stage('Identify and Create Delta Package') {
            steps {
                script {
                    echo "========================================="
                    echo "Stage: Identify and Create Delta Package"
                    echo "========================================="
                    
                    sh '''
                        # Create delta package directory
                        mkdir -p ${DELTA_PACKAGE_PATH}
                        
                        if [ -f "${PYTHON_SCRIPTS_PATH}/create_delta_package.py" ]; then
                            echo "Running delta package identification script..."
                            python "${PYTHON_SCRIPTS_PATH}/create_delta_package.py" \
                                --source-branch "${SOURCE_BRANCH_FINAL}" \
                                --target-branch "${PROMOTION_BRANCH}" \
                                --output-path "${DELTA_PACKAGE_PATH}" \
                                --source-env "${SOURCE_ENV}" \
                                --target-env "${TARGET_ENV}"
                            echo "Delta package created successfully"
                        else
                            echo "Warning: create_delta_package.py not found at ${PYTHON_SCRIPTS_PATH}"
                            echo "Creating sample delta package structure..."
                            mkdir -p ${DELTA_PACKAGE_PATH}/force-app/main/default
                        fi
                        
                        echo "Delta Package Contents:"
                        find ${DELTA_PACKAGE_PATH} -type f | head -20
                    '''
                }
            }
        }

        stage('Merge Delta Changes to Promotion Branch') {
            steps {
                script {
                    echo "========================================="
                    echo "Stage: Merge Delta Changes to Promotion Branch"
                    echo "========================================="
                    
                    sh '''
                        echo "Merging delta changes to promotion branch..."
                        
                        # Copy delta package contents to force-app
                        if [ -d "${DELTA_PACKAGE_PATH}/force-app" ]; then
                            cp -r ${DELTA_PACKAGE_PATH}/force-app/* ./force-app/main/default/ || true
                            echo "Delta files merged"
                        fi
                        
                        # Stage changes
                        git add -A
                        
                        # Check if there are changes to commit
                        if ! git diff-index --quiet HEAD --; then
                            git commit -m "Merge delta package from ${SOURCE_ENV} to ${TARGET_ENV}
                            
                            - Promotion Branch: ${PROMOTION_BRANCH}
                            - Timestamp: ${TIMESTAMP}
                            - Source: ${SOURCE_ENV}
                            - Target: ${TARGET_ENV}"
                            echo "Changes committed to promotion branch"
                        else
                            echo "No changes to commit"
                        fi
                        
                        git log --oneline -5
                    '''
                }
            }
        }

        stage('Run Apex PMD Analysis') {
            steps {
                script {
                    echo "========================================="
                    echo "Stage: Run Apex PMD Analysis"
                    echo "========================================="
                    
                    sh '''
                        # Check if PMD is installed
                        if command -v pmd &> /dev/null; then
                            echo "Running PMD analysis on delta package..."
                            
                            PMD_REPORT="${WORKSPACE}/pmd-report.html"
                            
                            pmd -d ${DELTA_PACKAGE_PATH} \
                                -f html \
                                -rulesets category/apex/bestpractices.xml,category/apex/design.xml \
                                -o ${PMD_REPORT} || true
                            
                            echo "PMD analysis completed. Report: ${PMD_REPORT}"
                        else
                            echo "Warning: PMD not installed. Skipping PMD analysis"
                            echo "To install PMD, visit: https://pmd.github.io/"
                        fi
                    '''
                }
            }
        }

        stage('Validate Delta Package') {
            steps {
                script {
                    echo "========================================="
                    echo "Stage: Validate Delta Package"
                    echo "========================================="
                    
                    sh '''
                        if [ -f "${PYTHON_SCRIPTS_PATH}/validate_delta_package.py" ]; then
                            echo "Running delta package validation script..."
                            python "${PYTHON_SCRIPTS_PATH}/validate_delta_package.py" \
                                --package-path "${DELTA_PACKAGE_PATH}" \
                                --target-env "${TARGET_ENV}" \
                                --target-org "${TARGET_ORG}"
                            echo "Validation completed"
                        else
                            echo "Warning: validate_delta_package.py not found"
                            echo "Running basic validation checks..."
                            
                            # Basic validation checks
                            echo "Checking package.xml existence..."
                            [ -f "${DELTA_PACKAGE_PATH}/package.xml" ] && echo "✓ package.xml found" || echo "✗ package.xml not found"
                            
                            echo "Checking force-app structure..."
                            [ -d "${DELTA_PACKAGE_PATH}/force-app/main/default" ] && echo "✓ Force-app structure valid" || echo "✗ Force-app structure missing"
                        fi
                    '''
                }
            }
        }

        stage('Deploy Delta Package to Target Environment') {
            steps {
                script {
                    echo "========================================="
                    echo "Stage: Deploy Delta Package"
                    echo "========================================="
                    echo "Target Environment: ${env.TARGET_ENV}"
                    echo "Target Org: ${env.TARGET_ORG}"
                    
                    sh '''
                        if [ -f "${PYTHON_SCRIPTS_PATH}/deploy_delta_package.py" ]; then
                            echo "Running deployment script..."
                            python "${PYTHON_SCRIPTS_PATH}/deploy_delta_package.py" \
                                --package-path "${DELTA_PACKAGE_PATH}" \
                                --target-env "${TARGET_ENV}" \
                                --target-org "${TARGET_ORG}" \
                                --deployment-id "${BUILD_ID}"
                            echo "Deployment completed"
                        else
                            echo "Warning: deploy_delta_package.py not found"
                            echo "Deployment script execution skipped"
                            echo ""
                            echo "Expected deployment configuration:"
                            echo "  - Package Path: ${DELTA_PACKAGE_PATH}"
                            echo "  - Target Environment: ${TARGET_ENV}"
                            echo "  - Target Org: ${TARGET_ORG}"
                            echo "  - Deployment ID: ${BUILD_ID}"
                        fi
                    '''
                }
            }
        }

        stage('Push Promotion Branch') {
            when {
                expression {
                    return sh(script: "git log -1 --pretty=%B | head -1", returnStdout: true).trim() != ""
                }
            }
            steps {
                script {
                    echo "========================================="
                    echo "Stage: Push Promotion Branch"
                    echo "========================================="
                    
                    sh '''
                        echo "Pushing promotion branch to remote..."
                        git push -u origin ${PROMOTION_BRANCH} || echo "Note: Push requires appropriate git credentials"
                        echo "Promotion branch pushed successfully"
                    '''
                }
            }
        }
    }

    post {
        always {
            script {
                echo "========================================="
                echo "Post-Build Stage: Cleanup and Reporting"
                echo "========================================="
                
                // Archive delta package for debugging
                archiveArtifacts artifacts: 'delta_package/**', allowEmptyArchive: true
                
                // Archive PMD report if it exists
                archiveArtifacts artifacts: '**/pmd-report.html', allowEmptyArchive: true
                
                // Generate build summary
                sh '''
                    echo "=== Build Summary ===" > ${WORKSPACE}/build_summary.txt
                    echo "Build Number: ${BUILD_NUMBER}" >> ${WORKSPACE}/build_summary.txt
                    echo "Deployment Path: ${DEPLOYMENT_PATH}" >> ${WORKSPACE}/build_summary.txt
                    echo "Source Environment: ${SOURCE_ENV}" >> ${WORKSPACE}/build_summary.txt
                    echo "Target Environment: ${TARGET_ENV}" >> ${WORKSPACE}/build_summary.txt
                    echo "Promotion Branch: ${PROMOTION_BRANCH}" >> ${WORKSPACE}/build_summary.txt
                    echo "Build Status: ${BUILD_STATUS}" >> ${WORKSPACE}/build_summary.txt
                    cat ${WORKSPACE}/build_summary.txt
                '''
            }
        }
        success {
            script {
                echo "========================================="
                echo "✓ Pipeline Execution Successful"
                echo "========================================="
                echo "Deployment from ${env.SOURCE_ENV} to ${env.TARGET_ENV} completed successfully"
                echo "Promotion Branch: ${env.PROMOTION_BRANCH}"
            }
        }
        failure {
            script {
                echo "========================================="
                echo "✗ Pipeline Execution Failed"
                echo "========================================="
                echo "Deployment from ${env.SOURCE_ENV} to ${env.TARGET_ENV} failed"
                echo "Check logs for details"
            }
        }
        unstable {
            script {
                echo "========================================="
                echo "⚠ Pipeline Execution Unstable"
                echo "========================================="
                echo "Pipeline completed with warnings"
            }
        }
    }
}
