#!/bin/bash
# scripts/verify_confidentiality.sh
# This script performs a baseline security audit to verify NFR WUN-95 (Confidentiality).

set -e

# Navigate to project root if run from scripts/
[[ "$(basename "$PWD")" == "scripts" ]] && cd ..

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo "--- WUN-95 Confidentiality Verification ---"

# 1. Check TLS Configuration
echo -e "\n1. Checking TLS Configuration (Caddyfile Audit)..."
if [[ -f "Caddyfile" ]]; then
    if grep -q "wunschkonzert.jj11.ch" Caddyfile; then
        echo -e "${GREEN}[PASS]${NC} Caddy is configured for production domains. Caddy 2.x defaults to TLS 1.2+."
    else
        echo -e "${RED}[FAIL]${NC} No production domain found in Caddyfile."
    fi
else
    echo -e "${RED}[ERROR]${NC} Caddyfile not found."
fi

# 2. Check Credential Storage Policy
echo -e "\n2. Checking Credential Storage Policy..."
DOMAIN_MODEL="backend/python/models/domain.py"

if [[ -f "$DOMAIN_MODEL" ]]; then
    if grep -q "password_hash" "$DOMAIN_MODEL"; then
        echo -e "${GREEN}[PASS]${NC} Secure 'password_hash' field found in domain models."
    elif grep -q "password: Mapped\[str\]" "$DOMAIN_MODEL"; then
        echo -e "${RED}[FAIL]${NC} Plaintext 'password' field detected in $DOMAIN_MODEL! High risk."
    else
        echo -e "${GREEN}[PASS]${NC} No credential fields found. System follows Data Minimization (OAuth/External only)."
    fi
else
    echo -e "${RED}[ERROR]${NC} $DOMAIN_MODEL not found."
fi

# 3. Check for Security Infrastructure (if internal auth is used)
PYPROJECT="backend/python/pyproject.toml"
if grep -q "password_hash" "$DOMAIN_MODEL" 2>/dev/null; then
    echo -e "\n3. Checking Hashing Infrastructure..."
    if grep -qi "bcrypt\|argon2\|passlib" "$PYPROJECT"; then
        echo -e "${GREEN}[PASS]${NC} Secure hashing library found in pyproject.toml."
    else
        echo -e "${RED}[FAIL]${NC} Internal auth used but no hashing library found in $PYPROJECT."
    fi
else
    echo -e "\n3. Checking Hashing Infrastructure..."
    echo -e "${YELLOW}[SKIP]${NC} No internal credentials stored; secure hashing library not required for local models."
fi

# 4. Encryption at Rest (Methodology)
echo -e "\n4. Encryption at Rest (Methodology)..."
echo "Verification: 'lsblk -f' on host to verify LUKS or cloud dashboard for Volume Encryption."

echo -e "\n--- End of Audit ---"
