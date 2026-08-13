#!/usr/bin/env bash
# Simple integration test script for Push API endpoints.
# Requires: curl, python3. Admin server must be running at http://localhost:8080

set -euo pipefail
BASE_URL=${BASE_URL:-http://127.0.0.1:8080}
TEST_TG_ID=${TEST_TG_ID:-1234567890}
AUTH_TOKEN=${AUTH_TOKEN:-}
API_KEY=${API_KEY:-}

headers=()
if [ -n "$AUTH_TOKEN" ]; then
  headers+=( -H "Authorization: Bearer $AUTH_TOKEN" )
fi
if [ -n "$API_KEY" ]; then
  headers+=( -H "X-API-Key: $API_KEY" )
fi

if [ ${#headers[@]} -eq 0 ]; then
  echo "Warning: no AUTH_TOKEN or API_KEY provided; requests will be unauthenticated."
fi

echo "Running /push/api/send-test (may fail if user has no token registered)"
curl -s -X POST "$BASE_URL/push/api/send-test"   "${headers[@]}"   -H "Content-Type: application/x-www-form-urlencoded"   -d "telegram_id=$TEST_TG_ID"   -d "title=Integration test"   -d "body=hello"   | python3 -c 'import sys, json; print(json.load(sys.stdin))'

echo

echo "Running /push/api/transfer-sent (integration check)"
curl -s -X POST "$BASE_URL/push/api/transfer-sent"   "${headers[@]}"   -H "Content-Type: application/json"   -d "{"telegram_id": $TEST_TG_ID, "amount": "300.00", "currency": "USD", "counterparty_name": "Alice", "transaction_id": "TXN-INT-001", "timestamp": "2025-01-01T12:00:00Z"}"   | python3 -c 'import sys, json; print(json.load(sys.stdin))'

echo

echo "Done. If admin is not running locally, start admin (admin app) and re-run this script."
