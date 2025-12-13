#!/bin/bash

# DLQ Integration Test Runner Script
# This script helps set up environment variables and run DLQ integration tests

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== DLQ Integration Test Runner ===${NC}\n"

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

# Function to get DLQ URL from main queue
get_dlq_url_from_queue() {
    local queue_url=$1
    local redrive_policy=$(aws sqs get-queue-attributes \
        --queue-url "$queue_url" \
        --attribute-names RedrivePolicy \
        --query 'Attributes.RedrivePolicy' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$redrive_policy" ]; then
        local dlq_arn=$(echo "$redrive_policy" | python3 -c "import sys, json; print(json.load(sys.stdin).get('deadLetterTargetArn', ''))" 2>/dev/null || echo "")
        if [ -n "$dlq_arn" ]; then
            # Convert ARN to URL
            local region=$(echo "$dlq_arn" | cut -d: -f4)
            local account=$(echo "$dlq_arn" | cut -d: -f5)
            local queue_name=$(echo "$dlq_arn" | cut -d: -f6)
            echo "https://sqs.${region}.amazonaws.com/${account}/${queue_name}"
        fi
    fi
}

# Function to find DLQ alarm name
find_dlq_alarm() {
    local stack_name=$1
    local prefix=$(echo "$stack_name" | cut -d- -f1-3)
    
    # Try to find alarm with DLQ in the name
    aws cloudwatch describe-alarms \
        --alarm-name-prefix "$prefix" \
        --query "MetricAlarms[?contains(AlarmName, 'DLQ') || contains(AlarmName, 'DeadLetter')].AlarmName" \
        --output text 2>/dev/null | head -1 || echo ""
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

# Get DLQ URL
echo -e "\n${GREEN}Finding DLQ URL...${NC}"
DLQ_URL=$(get_dlq_url_from_queue "$QUEUE_URL")

if [ -z "$DLQ_URL" ]; then
    echo -e "${RED}Error: Could not find DLQ URL from queue redrive policy${NC}"
    echo -e "${YELLOW}Please provide DLQ URL manually:${NC}"
    read -r DLQ_URL
    
    if [ -z "$DLQ_URL" ]; then
        echo -e "${RED}Error: DLQ URL is required${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ Found DLQ: $DLQ_URL${NC}"

# Try to find DLQ alarm
echo -e "\n${GREEN}Finding DLQ alarm...${NC}"
DLQ_ALARM_NAME=$(find_dlq_alarm "$STACK_NAME")

if [ -n "$DLQ_ALARM_NAME" ]; then
    echo -e "${GREEN}✓ Found DLQ Alarm: $DLQ_ALARM_NAME${NC}"
else
    echo -e "${YELLOW}⚠ Warning: Could not find DLQ alarm${NC}"
    echo -e "${YELLOW}  Alarm tests will be skipped${NC}"
fi

# Export environment variables
export RUN_INTEGRATION_TESTS=1
export PROCESSOR_FUNCTION_NAME="$PROCESSOR_FUNCTION_NAME"
export TEST_QUEUE_URL="$QUEUE_URL"
export TEST_DLQ_URL="$DLQ_URL"
if [ -n "$DLQ_ALARM_NAME" ]; then
    export DLQ_ALARM_NAME="$DLQ_ALARM_NAME"
fi

echo -e "\n${GREEN}=== Environment Variables Set ===${NC}"
echo "RUN_INTEGRATION_TESTS=$RUN_INTEGRATION_TESTS"
echo "PROCESSOR_FUNCTION_NAME=$PROCESSOR_FUNCTION_NAME"
echo "TEST_QUEUE_URL=$TEST_QUEUE_URL"
echo "TEST_DLQ_URL=$TEST_DLQ_URL"
if [ -n "$DLQ_ALARM_NAME" ]; then
    echo "DLQ_ALARM_NAME=$DLQ_ALARM_NAME"
fi

echo -e "\n${GREEN}=== Running DLQ Integration Tests ===${NC}\n"

# Run pytest
cd "$(dirname "$0")/../.." || exit 1
pytest tests/integration/test_dlq.py -v --tb=short

# Capture exit code
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}=== All DLQ Tests Passed! ===${NC}"
else
    echo -e "\n${RED}=== Some DLQ Tests Failed ===${NC}"
    echo -e "${YELLOW}Check the output above for details${NC}"
    echo -e "${YELLOW}You can also check CloudWatch Logs for Lambda execution details${NC}"
fi

exit $EXIT_CODE
