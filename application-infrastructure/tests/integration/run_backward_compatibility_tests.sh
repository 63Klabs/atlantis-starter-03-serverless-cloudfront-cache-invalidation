#!/bin/bash

# Backward Compatibility Test Runner Script
# This script runs backward compatibility tests for the origin-path-pattern feature

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Backward Compatibility Test Runner ===${NC}"
echo -e "${BLUE}=== Origin Path Pattern Feature ===${NC}\n"

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest is not installed${NC}"
    echo "Please install: pip install -r requirements-test.txt"
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

# Function to get stack parameter
get_stack_parameter() {
    local stack_name=$1
    local parameter_key=$2
    aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --query "Stacks[0].Parameters[?ParameterKey=='$parameter_key'].ParameterValue" \
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

echo -e "\n${GREEN}Fetching stack information...${NC}"

# Get stack outputs
PROCESSOR_ARN=$(get_stack_output "$STACK_NAME" "ProcessorFunctionArn")
QUEUE_URL=$(get_stack_output "$STACK_NAME" "EventQueueUrl")

if [ -z "$PROCESSOR_ARN" ] || [ -z "$QUEUE_URL" ]; then
    echo -e "${RED}Error: Could not fetch stack outputs${NC}"
    echo "Please verify the stack name and that the stack is deployed"
    exit 1
fi

# Extract function name from ARN
PROCESSOR_FUNCTION_NAME=$(extract_function_name "$PROCESSOR_ARN")

echo -e "${GREEN}✓ Found Processor: $PROCESSOR_FUNCTION_NAME${NC}"
echo -e "${GREEN}✓ Found Queue: $QUEUE_URL${NC}"

# Get stack parameters to verify default values
ORIGIN_PATH_PATTERN=$(get_stack_parameter "$STACK_NAME" "OriginPathPattern")
DIR_THRESHOLD=$(get_stack_parameter "$STACK_NAME" "DirectoryConsolidationThreshold")
STOP_LEVEL=$(get_stack_parameter "$STACK_NAME" "ConsolidationStopLevel")

echo -e "\n${BLUE}=== Stack Configuration ===${NC}"
echo -e "OriginPathPattern: ${YELLOW}${ORIGIN_PATH_PATTERN:-/{stageId}/public (default)}${NC}"
echo -e "DirectoryConsolidationThreshold: ${YELLOW}${DIR_THRESHOLD:-3 (default)}${NC}"
echo -e "ConsolidationStopLevel: ${YELLOW}${STOP_LEVEL:-1 (default)}${NC}"

# Verify default configuration
if [ -n "$ORIGIN_PATH_PATTERN" ] && [ "$ORIGIN_PATH_PATTERN" != "/{stageId}/public" ]; then
    echo -e "\n${YELLOW}⚠ WARNING: OriginPathPattern is not set to default value${NC}"
    echo -e "${YELLOW}  Current: $ORIGIN_PATH_PATTERN${NC}"
    echo -e "${YELLOW}  Expected: /{stageId}/public${NC}"
    echo -e "${YELLOW}  Backward compatibility tests expect default configuration${NC}"
    echo -e "\n${YELLOW}Continue anyway? (y/n)${NC}"
    read -r CONTINUE
    if [ "$CONTINUE" != "y" ]; then
        echo -e "${RED}Aborted${NC}"
        exit 1
    fi
fi

# Prompt for test bucket if not provided
if [ -z "$TEST_BUCKET_WITHOUT_CONFIG_TAGS" ]; then
    echo -e "\n${YELLOW}Enter test S3 bucket name (legacy bucket WITHOUT new config tags):${NC}"
    read -r TEST_BUCKET_WITHOUT_CONFIG_TAGS
fi

if [ -z "$TEST_BUCKET_WITHOUT_CONFIG_TAGS" ]; then
    echo -e "${RED}Error: Test bucket name is required${NC}"
    exit 1
fi

# Verify bucket exists and check tags
echo -e "\n${GREEN}Verifying test bucket...${NC}"
if aws s3api head-bucket --bucket "$TEST_BUCKET_WITHOUT_CONFIG_TAGS" 2>/dev/null; then
    echo -e "${GREEN}✓ Bucket exists${NC}"
    
    # Check bucket tags
    BUCKET_TAGS=$(aws s3api get-bucket-tagging --bucket "$TEST_BUCKET_WITHOUT_CONFIG_TAGS" 2>/dev/null || echo "")
    
    # Verify AllowInvalidationEvents tag
    if echo "$BUCKET_TAGS" | grep -q "AllowInvalidationEvents"; then
        echo -e "${GREEN}✓ Has AllowInvalidationEvents tag${NC}"
    else
        echo -e "${RED}✗ Missing AllowInvalidationEvents=true tag${NC}"
        echo -e "${YELLOW}  Add tag with:${NC}"
        echo -e "  aws s3api put-bucket-tagging --bucket $TEST_BUCKET_WITHOUT_CONFIG_TAGS \\"
        echo -e "    --tagging 'TagSet=[{Key=AllowInvalidationEvents,Value=true}]'"
        exit 1
    fi
    
    # Verify NO new config tags (for backward compatibility testing)
    if echo "$BUCKET_TAGS" | grep -q "invalidator:OriginPathPattern"; then
        echo -e "${YELLOW}⚠ WARNING: Bucket has invalidator:OriginPathPattern tag${NC}"
        echo -e "${YELLOW}  Backward compatibility tests expect legacy buckets WITHOUT new tags${NC}"
        echo -e "${YELLOW}  Remove the tag or use a different bucket${NC}"
        echo -e "\n${YELLOW}Continue anyway? (y/n)${NC}"
        read -r CONTINUE
        if [ "$CONTINUE" != "y" ]; then
            echo -e "${RED}Aborted${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✓ No new config tags (legacy bucket)${NC}"
    fi
else
    echo -e "${RED}Error: Bucket $TEST_BUCKET_WITHOUT_CONFIG_TAGS does not exist or is not accessible${NC}"
    exit 1
fi

# Prompt for test distribution if not provided
if [ -z "$TEST_DISTRIBUTION_ID" ]; then
    echo -e "\n${YELLOW}Enter test CloudFront distribution ID:${NC}"
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
else
    echo -e "${RED}Error: Distribution $TEST_DISTRIBUTION_ID does not exist or is not accessible${NC}"
    exit 1
fi

# Export environment variables
export RUN_INTEGRATION_TESTS=1
export PROCESSOR_FUNCTION_NAME="$PROCESSOR_FUNCTION_NAME"
export TEST_QUEUE_URL="$QUEUE_URL"
export TEST_BUCKET_WITHOUT_CONFIG_TAGS="$TEST_BUCKET_WITHOUT_CONFIG_TAGS"
export TEST_DISTRIBUTION_ID="$TEST_DISTRIBUTION_ID"
export DIRECTORY_CONSOLIDATION_THRESHOLD="${DIR_THRESHOLD:-3}"
export CONSOLIDATION_STOP_LEVEL="${STOP_LEVEL:-1}"

echo -e "\n${BLUE}=== Environment Variables Set ===${NC}"
echo "RUN_INTEGRATION_TESTS=$RUN_INTEGRATION_TESTS"
echo "PROCESSOR_FUNCTION_NAME=$PROCESSOR_FUNCTION_NAME"
echo "TEST_QUEUE_URL=$TEST_QUEUE_URL"
echo "TEST_BUCKET_WITHOUT_CONFIG_TAGS=$TEST_BUCKET_WITHOUT_CONFIG_TAGS"
echo "TEST_DISTRIBUTION_ID=$TEST_DISTRIBUTION_ID"
echo "DIRECTORY_CONSOLIDATION_THRESHOLD=$DIRECTORY_CONSOLIDATION_THRESHOLD"
echo "CONSOLIDATION_STOP_LEVEL=$CONSOLIDATION_STOP_LEVEL"

echo -e "\n${BLUE}=== Running Backward Compatibility Tests ===${NC}\n"

# Change to the correct directory
cd "$(dirname "$0")/../.." || exit 1

# Run pytest with backward compatibility tests
pytest tests/integration/test_backward_compatibility.py -v --tb=short

# Capture exit code
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}=== ✓ All Backward Compatibility Tests Passed! ===${NC}"
    echo -e "${GREEN}The enhanced system maintains full backward compatibility${NC}"
    echo -e "${GREEN}with the previous version when using default configuration.${NC}"
else
    echo -e "\n${RED}=== ✗ Some Tests Failed ===${NC}"
    echo -e "${YELLOW}Check the output above for details${NC}"
    echo -e "${YELLOW}Review CloudWatch Logs for Lambda execution details${NC}"
    echo -e "${YELLOW}Ensure the stack is deployed with default parameters${NC}"
fi

exit $EXIT_CODE
