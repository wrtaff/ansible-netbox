#!/bin/bash
# ==============================================================================
# Filename:       scripts/download_takeout.sh
# Version:        1.0
# Author:         Gemini CLI
# Last Modified:  2026-02-07
# Context:        http://trac.home.arpa/ticket/3054
#
# Purpose:
#   Automate the download of large Google Takeout archives using wget.
#   Handles session-protected URLs via cookies and supports resuming.
#
# Usage:
#   ./download_takeout.sh <urls_file> <cookies_file> [destination_dir]
#
# Example:
#   ./download_takeout.sh urls.txt cookies.txt /mnt/tank22/backups/gdrive/takeout/2026-02-07
# ==============================================================================

URL_FILE=$1
COOKIE_FILE=$2
DEST_DIR=${3:-"/mnt/nfs/will/backups/google_takeout/$(date +%Y-%m-%d)"}

# Validation
if [[ -z "$URL_FILE" || -z "$COOKIE_FILE" ]]; then
    echo "Usage: $0 <urls_file> <cookies_file> [destination_dir]"
    exit 1
fi

if [[ ! -f "$URL_FILE" ]]; then
    echo "Error: URL file '$URL_FILE' not found."
    exit 1
fi

if [[ ! -f "$COOKIE_FILE" ]]; then
    echo "Error: Cookie file '$COOKIE_FILE' not found."
    exit 1
fi

# Create destination directory
mkdir -p "$DEST_DIR"
cd "$DEST_DIR" || exit 1

echo "------------------------------------------------------------------------------"
echo "Starting Google Takeout Download"
echo "Date:        $(date)"
echo "Destination: $DEST_DIR"
echo "URL List:    $URL_FILE"
echo "Cookie File: $COOKIE_FILE"
echo "------------------------------------------------------------------------------"

# Run wget
# --load-cookies: Use the exported browser session
# --content-disposition: Respect the filename suggested by the server
# --continue: Resume partially downloaded files
# --tries: Number of retries for each file
# --wait: Seconds to wait between retrievals (polite)
wget --load-cookies "../../$COOKIE_FILE" 
     --content-disposition 
     --continue 
     --tries=20 
     --wait=2 
     -i "../../$URL_FILE"

EXIT_CODE=$?

echo "------------------------------------------------------------------------------"
if [ $EXIT_CODE -eq 0 ]; then
    echo "Download process finished successfully."
else
    echo "Download process finished with errors (Exit Code: $EXIT_CODE)."
fi
echo "Final file listing:"
ls -lh
echo "------------------------------------------------------------------------------"
