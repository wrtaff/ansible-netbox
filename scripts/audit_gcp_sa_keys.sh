#!/bin/bash
# Script: scripts/audit_gcp_sa_keys.sh
# Purpose: List all service accounts and their user-managed keys for a project.
# Usage: ./audit_gcp_sa_keys.sh <PROJECT_ID>

PROJECT="$1"

if [ -z "$PROJECT" ]; then
    echo "Usage: $0 <PROJECT_ID>"
    exit 1
fi

echo "=== Auditing Service Account Keys for Project: $PROJECT ==="

# Get SAs
SAs=$(gcloud iam service-accounts list --project="$PROJECT" --format="value(email)")

if [ -z "$SAs" ]; then
    echo "No service accounts found in project $PROJECT."
    exit 0
fi

for SA in $SAs; do
    echo "------------------------------------------------"
    echo "Service Account: $SA"
    
    # List keys, filter for USER_MANAGED keys (ignore SYSTEM_MANAGED)
    KEYS=$(gcloud iam service-accounts keys list --iam-account="$SA" --project="$PROJECT" --filter="keyType=USER_MANAGED" --format="table(name,validBeforeTime)")
    
    if [[ "$KEYS" == *"KEY_ID"* ]]; then
        echo "$KEYS"
    else
        echo "  No user-managed keys found."
    fi
done

echo "=== Audit Complete ==="
