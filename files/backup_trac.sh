#!/bin/bash
#
# v2: Refactored for trac-lxc
# - Removes NFS dependency, uses scp to push backup.
# - Relies *only* on 'trac-admin hotcopy' for a complete backup.
# - Assumes an SSH key is set up for 'BACKUP_USER@BACKUP_HOST'.

set -e  # Exit immediately if a command exits with a non-zero status.

# --- Configuration ---
# (Verify these paths inside the 'trac-lxc' container)
TRAC_ADMIN_CMD="/usr/local/bin/trac-admin"      # <-- VERIFIED
TRAC_PROJECT_PATH="/var/trac/trac_bak_TEMP" # <-- VERIFIED (Live project)

# --- Backup Destination ---
NOW=$(date +"%Y%m%d%H%M%S")
BACKUP_FILENAME="tracBak_${NOW}.tar.gz"
TEMP_DIR_PARENT="/tmp" # Use /tmp for temporary build space
TEMP_BACKUP_DIR="${TEMP_DIR_PARENT}/trac_hotcopy_${NOW}"

# --- Remote Server Details ---
# (This user/host must be reachable via SSH key from 'trac-lxc')
# (Updated per your input)
BACKUP_USER="will"
BACKUP_HOST="truenas.home.arpa"
REMOTE_DEST_DIR="/mnt/tank22/nfs-share/backup"

# --- 1. Create Hotcopy ---
echo "Creating Trac hotcopy at ${TEMP_BACKUP_DIR}..."
${TRAC_ADMIN_CMD} ${TRAC_PROJECT_PATH} hotcopy ${TEMP_BACKUP_DIR}

# --- 2. Create Tarball ---
# We tar from *within* the temp parent dir to get a clean tarball
# The tarball will be created in /tmp
echo "Creating tarball..."
tar -zcvf "${TEMP_DIR_PARENT}/${BACKUP_FILENAME}" -C ${TEMP_BACKUP_DIR} .

# --- 3. Push to Backup Server ---
echo "Pushing ${BACKUP_FILENAME} to ${BACKUP_HOST}..."
scp "${TEMP_DIR_PARENT}/${BACKUP_FILENAME}" ${BACKUP_USER}@${BACKUP_HOST}:${REMOTE_DEST_DIR}

# --- 4. Cleanup ---
echo "Cleaning up local files..."
rm -r "${TEMP_BACKUP_DIR}"
rm "${TEMP_DIR_PARENT}/${BACKUP_FILENAME}"

echo "Backup complete."
