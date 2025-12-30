#!/bin/bash

# Pi-hole Backup Verification Script
# File: verify_pihole_backup.sh

BACKUP_DIR="/opt/netbox/ansible-netbox/playbooks/backups/pihole/20250826_1941"

echo "================================================================"
echo "🔍 PI-HOLE BACKUP VERIFICATION"
echo "================================================================"
echo ""

# Check if backup directory exists
if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ ERROR: Backup directory not found!"
    echo "   Expected: $BACKUP_DIR"
    echo ""
    echo "Searching for backup files..."
    find /opt/netbox -name "*20250826_1941*" -type d 2>/dev/null
    exit 1
fi

echo "📁 Backup Location: $BACKUP_DIR"
echo ""

# List all backup files
echo "📋 All Backup Files:"
echo "────────────────────"
ls -la "$BACKUP_DIR/"
echo ""

# Check critical files
echo "🔑 Critical Files Check:"
echo "────────────────────────"

# Teleporter backup (most important)
if [ -f "$BACKUP_DIR/pihole_teleporter_backup.tar.gz" ]; then
    SIZE=$(ls -lh "$BACKUP_DIR/pihole_teleporter_backup.tar.gz" | awk '{print $5}')
    echo "✅ Teleporter Backup: $SIZE"
else
    echo "❌ Teleporter Backup: MISSING"
fi

# DHCP configuration
if [ -f "$BACKUP_DIR/dhcp_config.txt" ]; then
    LINES=$(wc -l < "$BACKUP_DIR/dhcp_config.txt")
    echo "✅ DHCP Configuration: $LINES lines"
else
    echo "❌ DHCP Configuration: MISSING"
fi

# Static DHCP leases
if [ -f "$BACKUP_DIR/static_dhcp_leases.txt" ]; then
    LINES=$(wc -l < "$BACKUP_DIR/static_dhcp_leases.txt")
    echo "✅ Static DHCP Leases: $LINES lines"
else
    echo "❌ Static DHCP Leases: MISSING"
fi

# Setup variables
if [ -f "$BACKUP_DIR/setupVars.conf" ]; then
    LINES=$(wc -l < "$BACKUP_DIR/setupVars.conf")
    echo "✅ Setup Variables: $LINES lines"
else
    echo "❌ Setup Variables: MISSING"
fi

echo ""
echo "📊 Total Files Backed Up: $(ls -1 "$BACKUP_DIR/" | wc -l)"
echo ""

# Show key configuration previews
echo "👀 DHCP Configuration Preview:"
echo "──────────────────────────────"
if [ -f "$BACKUP_DIR/dhcp_config.txt" ]; then
    head -10 "$BACKUP_DIR/dhcp_config.txt"
fi

echo ""
echo "📋 Static DHCP Reservations Preview:"
echo "────────────────────────────────────"
if [ -f "$BACKUP_DIR/static_dhcp_leases.txt" ]; then
    head -5 "$BACKUP_DIR/static_dhcp_leases.txt"
    RESERVATION_COUNT=$(grep -c "dhcp-host=" "$BACKUP_DIR/static_dhcp_leases.txt" 2>/dev/null || echo "0")
    echo "   → $RESERVATION_COUNT static reservations found"
fi

echo ""
echo "================================================================"

# Final status
if [ -f "$BACKUP_DIR/pihole_teleporter_backup.tar.gz" ] && [ -f "$BACKUP_DIR/dhcp_config.txt" ] && [ -f "$BACKUP_DIR/setupVars.conf" ]; then
    echo "🎉 BACKUP VERIFICATION: SUCCESS!"
    echo "✅ All critical files present and ready for migration"
    echo "🚀 Ready for Phase 2: Create new Pi-hole containers"
else
    echo "⚠️  BACKUP VERIFICATION: INCOMPLETE!"
    echo "❌ Some critical files are missing"
fi

echo "================================================================"
