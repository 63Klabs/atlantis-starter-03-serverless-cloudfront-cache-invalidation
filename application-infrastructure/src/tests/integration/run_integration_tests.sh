#!/bin/bash

# Integration Test Runner Script
# This script helps set up environment variables and run integration tests

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== CloudFront Invalidation Service - Integration Test Runner ===${NC}\n"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    echo "Please install AWS CLI: https://aws.amazon.com/cli/"
    exit 1
fi

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest is not installed${NC}"
    echo "Please install: pip install -r requirements.txt"
    exit 1
fi

# Function to get stack output
get_stack_output() {
    local stack_name=$1
    local output_key=$2
    aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --query "Stacks[0].Outputs[?OutputKey=='$output_key'].OutputValue" \
        --output text 2>/dev/null || echo ""
}

# Function to extract function name from ARN
extract_function_name() {
    local arn=$1
    echo "$arn" | awk -F: '{print $7}'
}

# Prompt for stack name if not provided
if [ -z "$STACK_NAME" ]; then
    echo -e "${YELLOW}Enter CloudFormation stack name:${NC}"
    read -r STACK_NAME
fi

if [ -z "$STACK_NAME" ]; then
    echo -e "${RED}Error: Stack name is required${NC}"
    exit 1
fi

echo -e "\n${GREEN}Fetching stack outputs...${NC}"

# Get stack outputs
INGESTOR_ARN=$(get_stack_output "$STACK_NAME" "IngestorFunctionArn")
PROCESSOR_ARN=$(get_stack_output "$STACK_NAME" "ProcessorFunctionArn")
QUEUE_URL=$(get_stack_output "$STACK_NAME" "EventQueueUrl")
TRACKING_TABLE=$(get_stack_output "$STACK_NAME" "TrackingTableName")

if [ -z "$INGESTOR_ARN" ] || [ -z "$PROCESSOR_ARN" ] || [ -z "$QUEUE_URL" ]; then
    echo -e "${RED}Error: Could not fetch stack outputs${NC}"
    echo "Please verify the stack name and that the stack is deployed"
    exit 1
fi

# Extract function names from ARNs
INGESTOR_FUNCTION_NAME=$(extract_function_name "$INGESTOR_ARN")
PROCESSOR_FUNCTION_NAME=$(extract_function_name "$PROCESSOR_ARN")

echo -e "${GREEN}✓ Found Ingestor: $INGESTOR_FUNCTION_NAME${NC}"
echo -e "${GREEN}✓ Found Processor: $PROCESSOR_FUNCTION_NAME${NC}"
echo -e "${GREEN}✓ Found Queue: $QUEUE_URL${NC}"
if [ -n "$TRACKING_TABLE" ]; then
    echo -e "${GREEN}✓ Found Tracking Table: $TRACKING_TABLE${NC}"
fi

# Prompt for test bucket if not provided
if [ -z "$TEST_BUCKET_NAME" ]; then
    echo -e "\n${YELLOW}Enter test S3 bucket name (must have AllowInvalidationEvents=true tag):${NC}"
    read -r TEST_BUCKET_NAME
fi

if [ -z "$TEST_BUCKET_NAME" ]; then
    echo -e "${RED}Error: Test bucket name is required${NC}"
    exit 1
fi

# Verify bucket exists and has correct tag
echo -e "\n${GREEN}Verifying test bucket...${NC}"
if aws s3api head-bucket --bucket "$TEST_BUCKET_NAME" 2>/dev/null; then
    BUCKET_TAGS=$(aws s3api get-bucket-tagging --bucket "$TEST_BUCKET_NAME" 2>/dev/null || echo "")
    if echo "$BUCKET_TAGS" | grep -q "AllowInvalidationEvents"; then
        echo -e "${GREEN}✓ Bucket exists and has AllowInvalidationEvents tag${NC}"
    else
        echo -e "${YELLOW}⚠ Warning: Bucket exists but may not have AllowInvalidationEvents=true tag${NC}"
        echo -e "${YELLOW}  Some tests may fail. Add tag with:${NC}"
        echo -e "  aws s3api put-bucket-tagging --bucket $TEST_BUCKET_NAME \\"
        echo -e "    --tagging 'TagSet=[{Key=AllowInvalidationEvents,Value=true}]'"
    fi
else
    echo -e "${RED}Error: Bucket $TEST_BUCKET_NAME does not exist or is not accessible${NC}"
    exit 1
fi

# Prompt for test distribution if not provided
if [ -z "$TEST_DISTRIBUTION_ID" ]; then
    echo -e "\n${YELLOW}Enter test CloudFront distribution ID (must have AllowCloudFrontCacheInvalidation=true tag):${NC}"
    read -r TEST_DISTRIBUTION_ID
fi

if [ -z "$TEST_DISTRIBUTION_ID" ]; then
    echo -e "${RED}Error: Test distribution ID is required${NC}"
    exit 1
fi

# Verify distribution exists
echo -e "\n${GREEN}Verifying test distribution...${NC}"
if aws cloudfront get-distribution --id "$TEST_DISTRIBUTION_ID" &>/dev/null; then
    echo -e "${GREEN}✓ Distribution exists${NC}"
    
    # Try to check tags (may fail if no permissions)
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    DIST_ARN="arn:aws:cloudfront::${ACCOUNT_ID}:distribution/${TEST_DISTRIBUTION_ID}"
    DIST_TAGS=$(aws cloudfront list-tags-for-resource --resource "$DIST_ARN" 2>/dev/null || echo "")
    
    if echo "$DIST_TAGS" | grep -q "AllowCloudFrontCacheInvalidation"; then
        echo -e "${GREEN}✓ Distribution has AllowCloudFrontCacheInvalidation tag${NC}"
    else
        echo -e "${YELLOW}⚠ Warning: Could not verify distribution tags${NC}"
        echo -e "${YELLOW}  Ensure distribution has AllowCloudFrontCacheInvalidation=true tag${NC}"
    fi
else
    echo -e "${RED}Error: Distribution $TEST_DISTRIBUTION_ID does not exist or is not accessible${NC}"
    exit 1
fi

# Export environment variables
export RUN_INTEGRATION_TESTS=1
export INGESTOR_FUNCTION_NAME="$INGESTOR_FUNCTION_NAME"
export PROCESSOR_FUNCTION_NAME="$PROCESSOR_FUNCTION_NAME"
export TEST_QUEUE_URL="$QUEUE_URL"
export TEST_BUCKET_NAME="$TEST_BUCKET_NAME"
export TEST_DISTRIBUTION_ID="$TEST_DISTRIBUTION_ID"
if [ -n "$TRACKING_TABLE" ]; then
    export TRACKING_TABLE="$TRACKING_TABLE"
fi

echo -e "\n${GREEN}=== Environment Variables Set ===${NC}"
echo "RUN_INTEGRATION_TESTS=$RUN_INTEGRATION_TESTS"
echo "INGESTOR_FUNCTION_NAME=$INGESTOR_FUNCTION_NAME"
echo "PROCESSOR_FUNCTION_NAME=$PROCESSOR_FUNCTION_NAME"
echo "TEST_QUEUE_URL=$TEST_QUEUE_URL"
echo "TEST_BUCKET_NAME=$TEST_BUCKET_NAME"
echo "TEST_DISTRIBUTION_ID=$TEST_DISTRIBUTION_ID"
if [ -n "$TRACKING_TABLE" ]; then
    echo "TRACKING_TABLE=$TRACKING_TABLE"
fi

# Determine which tests to run
TEST_FILE="${1:-src/tests/integration/test_iam_permissions.py}"

echo -e "\n${GREEN}=== Running Integration Tests ===${NC}"
echo -e "Test file: ${YELLOW}$TEST_FILE${NC}\n"

# Run pytest
cd "$(dirname "$0")/../../.." || exit 1
pytest "$TEST_FILE" -v --tb=short

# Capture exit code
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}=== All Tests Passed! ===${NC}"
else
    echo -e "\n${RED}=== Some Tests Failed ===${NC}"
    echo -e "${YELLOW}Check the output above for details${NC}"
    echo -e "${YELLOW}You can also check CloudWatch Logs for Lambda execution details${NC}"
fi

exit $EXIT_CODE
