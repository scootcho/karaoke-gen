#!/bin/bash
# Run backend unit tests with coverage reporting
# Usage: ./scripts/run-tests.sh [options]

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================"
echo "Running Backend Unit Tests"
echo "========================================"
echo ""

# Check if venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not activated${NC}"
    echo "   Activate it first: source backend/venv/bin/activate"
    echo "   Or run: backend  (if you set up the alias)"
    echo ""
    exit 1
fi

# Check if test dependencies are installed
if ! python -c "import pytest" 2>/dev/null; then
    echo -e "${YELLOW}Installing test dependencies...${NC}"
    pip install -r backend/tests/requirements-test.txt
    echo ""
fi

# Change to project root
cd "$(dirname "$0")/.."

# Run tests with coverage
echo -e "${BLUE}Running unit tests...${NC}"
echo ""

if [ "$1" == "--coverage" ] || [ "$1" == "-c" ]; then
    # Run with coverage report
    pytest backend/tests/ \
        -v \
        --cov=backend \
        --cov-report=term-missing \
        --cov-report=html:htmlcov \
        --cov-fail-under=70 \
        "$@"
    
    EXITCODE=$?
    
    if [ $EXITCODE -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ All tests passed with >= 70% coverage!${NC}"
        echo -e "   Coverage report: htmlcov/index.html"
    else
        echo ""
        echo -e "${RED}❌ Tests failed or coverage below 70%${NC}"
    fi
    
    exit $EXITCODE
else
    # Run without coverage (faster)
    pytest backend/tests/ -v "$@"
    
    EXITCODE=$?
    
    if [ $EXITCODE -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ All tests passed!${NC}"
    else
        echo ""
        echo -e "${RED}❌ Some tests failed${NC}"
    fi
    
    exit $EXITCODE
fi

