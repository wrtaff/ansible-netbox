#!/bin/bash
# Script: scripts/audit_gcp_keys.sh
# Purpose: Iterate through all accessible GCP projects and list active API keys.
# Usage: ./audit_gcp_keys.sh [OPTIONAL_KEY_STRING_TO_MATCH]

TARGET_KEY="$1"

echo "=== Starting Global GCP API Key Audit ==="
echo "Timestamp: $(date)"

# check if logged in
if ! gcloud auth list --format="value(account)" | grep -q "@"; then
    echo "Error: Not authenticated. Please run 'gcloud auth login' first."
    exit 1
fi

# Get list of projects
echo "Fetching project list..."
PROJECTS=$(gcloud projects list --format="value(projectId)")

for PROJECT in $PROJECTS; do
    echo "------------------------------------------------"
    echo "Checking Project: $PROJECT"
    
    # Enable the API keys service specific check or just try to list
    # Note: If API Keys API is not enabled on the project, this might fail/warn, so we suppress stderr slightly or handle it.
    
    KEYS=$(gcloud services api-keys list --project="$PROJECT" --format="value(name,displayName,state,currentKey)" 2>/dev/null)
    
    if [ -z "$KEYS" ]; then
        echo "  No keys found (or API not enabled/accessible)."
    else
        echo "$KEYS" | while read -r KEY_LINE; do
            # Format usually: projects/123/locations/global/keys/UID DisplayName ACTIVE AIzaSy...
            STATE=$(echo "$KEY_LINE" | awk '{print $3}')
            KEY_STRING=$(echo "$KEY_LINE" | awk '{print $4}')
            
            if [ "$STATE" == "ACTIVE" ]; then
                if [ -n "$TARGET_KEY" ]; then
                     if [[ "$KEY_STRING" == *"$TARGET_KEY"* ]]; then
                        echo "  [CRITICAL MATCH] Found Active Key: $KEY_LINE"
                     fi
                else
                    echo "  [ACTIVE] Found Key: $KEY_LINE"
                fi
            else
                echo "  [INACTIVE] $KEY_LINE"
            fi
        done
    fi
done

echo "=== Audit Complete ==="
