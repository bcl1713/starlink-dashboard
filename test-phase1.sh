#!/bin/bash
set -e

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test counters
PASSED=0
FAILED=0

# Test helper function
test_endpoint() {
    local name=$1
    local url=$2
    local expected_status=$3

    echo -n "Testing $name... "

    local status=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")

    if [ "$status" = "$expected_status" ]; then
        echo -e "${GREEN}PASS${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAIL${NC} (expected $expected_status, got $status)"
        ((FAILED++))
    fi
}

# Test helper for JSON response
test_health_endpoint() {
    echo -n "Testing backend /health endpoint... "

    local response=$(curl -s http://localhost:8000/health 2>/dev/null || echo "{}")

    if echo "$response" | grep -q '"status":"ok"'; then
        echo -e "${GREEN}PASS${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAIL${NC} (response: $response)"
        ((FAILED++))
    fi
}

# Test for metrics endpoint
test_metrics_endpoint() {
    echo -n "Testing backend /metrics endpoint... "

    local response=$(curl -s http://localhost:8000/metrics 2>/dev/null || echo "")

    if echo "$response" | grep -q "starlink_service_info"; then
        echo -e "${GREEN}PASS${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAIL${NC} (metric not found in response)"
        ((FAILED++))
    fi
}

# Test container status
test_containers() {
    echo -n "Testing container status... "

    local running=$(docker compose ps --format 'table {{.Names}}\t{{.Status}}' | grep -c "running" || echo "0")
    local expected=3

    if [ "$running" -ge "$expected" ]; then
        echo -e "${GREEN}PASS${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAIL${NC} (expected at least $expected running containers)"
        ((FAILED++))
    fi
}

# Test Prometheus targets
test_prometheus_targets() {
    echo -n "Testing Prometheus targets... "

    local response=$(curl -s http://localhost:9090/api/v1/targets 2>/dev/null || echo "{}")

    if echo "$response" | grep -q "starlink-location"; then
        echo -e "${GREEN}PASS${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAIL${NC} (starlink-location target not found)"
        ((FAILED++))
    fi
}

echo "========================================="
echo "Phase 1 Infrastructure Validation Tests"
echo "========================================="
echo ""

# Run all tests
test_containers
test_endpoint "Grafana" "http://localhost:3000" "200"
test_endpoint "Prometheus" "http://localhost:9090" "200"
test_health_endpoint
test_metrics_endpoint
test_prometheus_targets

echo ""
echo "========================================="
echo "Test Summary"
echo "========================================="
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo "========================================="

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi
