---
name: aws-ec2-load-tester
description: Automates an end-to-end API load testing workflow using AWS EC2 instances. Use this when the user asks to run a load test, stress test an API, or execute the AWS load testing workflow.
---

# AWS EC2 Load Tester

This skill orchestrates a fully automated, distributed API load test using AWS EC2 instances. It handles the deployment of infrastructure, execution of the test, report generation, and the teardown of resources.

## Workflow Instructions

When the user asks to run a load test using this skill, follow these exact steps in order.

### Step 0: Ensure Required Scripts are Present
The necessary scripts (`aws_deploy.sh`, `aws_run_test.sh`, `aws_destroy.sh`, `load_test.py`, `generate_report.py`) are bundled in this skill's `assets/scripts/` directory.
If these files do not exist in the user's current working directory, copy them from the skill's `assets/scripts/` folder to the current directory and ensure the `.sh` files have execute permissions (`chmod +x *.sh`).

### Step 1: Gather Requirements
Ensure you have the following information from the user:
1. `API_URL`: The endpoint URL to test.
2. `API_KEY`: The authorization key for the API.
If the user hasn't provided them, politely ask for them using the `ask_user` tool or standard text response before proceeding.

### Step 2: Deploy Infrastructure
Run the deployment script to create 3 EC2 instances in AWS.
**Command**: `./aws_deploy.sh`
Wait for the command to complete successfully. It will generate an `aws_resources.env` file.

### Step 3: Execute Load Test
Run the load test script using the provided URL and Key.
**Command**: `./aws_run_test.sh "<API_URL>" "<API_KEY>"`
This script will take approximately 5-6 minutes. It runs the load test, downloads the results, and generates a `merged_report.html` file in the current directory.

### Step 4: Destroy Infrastructure
Once the test finishes and the report is generated, you MUST tear down the infrastructure to prevent unwanted AWS charges.
**Command**: `./aws_destroy.sh`
Wait for this to complete successfully.

### Step 5: Final Summary
Inform the user that the test is complete, the infrastructure has been safely destroyed, and they can open `merged_report.html` in their browser to view the detailed results and error code summaries.
