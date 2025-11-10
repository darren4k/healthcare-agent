#!/bin/bash

###############################################################################
# Healthcare Agent Platform - Database Backup Script
# Step 10: Configure Automated Backups
#
# This script creates comprehensive backups of:
# - PostgreSQL database (schema + data)
# - Redis data
# - Configuration files
# - SSL certificates
#
# Usage:
#   ./scripts/backup_db.sh [--type full|db|redis|config]
#   ./scripts/backup_db.sh --destination /path/to/backup
#
# Cron example (daily at 2 AM):
#   0 2 * * * /path/to/healthcare-agent/scripts/backup_db.sh >> /var/log/backup.log 2>&1
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKUP_TYPE="${1:-full}"  # full, db, redis, or config
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="healthcare_backup_${TIMESTAMP}"

# Database configuration
DB_CONTAINER="healthcare-agent-db-1"
REDIS_CONTAINER="healthcare-agent-redis-1"
DB_USER="postgres"
DB_NAME="healthcare_agent_prod"

# Compression
USE_COMPRESSION=true
COMPRESSION_LEVEL=6

###############################################################################
# Helper Functions
###############################################################################

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check if Docker is running
    if ! docker ps > /dev/null 2>&1; then
        print_error "Docker is not running"
        exit 1
    fi
    print_success "Docker is running"

    # Check if containers are running
    if ! docker ps | grep -q "$DB_CONTAINER"; then
        print_error "Database container is not running"
        exit 1
    fi
    print_success "Database container is running"

    if ! docker ps | grep -q "$REDIS_CONTAINER"; then
        print_info "Redis container is not running (skipping Redis backup)"
    else
        print_success "Redis container is running"
    fi

    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    print_success "Backup directory: $BACKUP_DIR"

    # Check available disk space
    available_space=$(df -BG "$BACKUP_DIR" | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ "$available_space" -lt 5 ]; then
        print_error "Less than 5GB available disk space"
        exit 1
    fi
    print_success "Available disk space: ${available_space}GB"
}

backup_database() {
    print_header "Backing Up PostgreSQL Database"

    local backup_file="$BACKUP_DIR/${BACKUP_NAME}_postgres.sql"

    print_info "Starting database backup..."
    print_info "Database: $DB_NAME"
    print_info "Container: $DB_CONTAINER"

    # Create SQL dump
    docker exec -t "$DB_CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" \
        --verbose \
        --no-owner \
        --no-acl \
        --clean \
        --if-exists \
        > "$backup_file" 2>/dev/null

    if [ $? -eq 0 ]; then
        local size=$(du -h "$backup_file" | cut -f1)
        print_success "Database backup created: $backup_file ($size)"
    else
        print_error "Database backup failed"
        return 1
    fi

    # Compress backup
    if [ "$USE_COMPRESSION" = true ]; then
        print_info "Compressing backup..."
        gzip -$COMPRESSION_LEVEL "$backup_file"
        backup_file="${backup_file}.gz"
        local compressed_size=$(du -h "$backup_file" | cut -f1)
        print_success "Backup compressed: $backup_file ($compressed_size)"
    fi

    # Create checksum
    md5sum "$backup_file" > "${backup_file}.md5"
    print_success "Checksum created: ${backup_file}.md5"

    # Backup database schema separately (for quick reference)
    local schema_file="$BACKUP_DIR/${BACKUP_NAME}_schema.sql"
    docker exec -t "$DB_CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" \
        --schema-only \
        --no-owner \
        --no-acl \
        > "$schema_file" 2>/dev/null
    print_success "Schema backup created: $schema_file"

    # Export table statistics
    local stats_file="$BACKUP_DIR/${BACKUP_NAME}_stats.txt"
    docker exec -t "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
        SELECT
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
            n_tup_ins AS inserts,
            n_tup_upd AS updates,
            n_tup_del AS deletes,
            n_live_tup AS live_rows
        FROM pg_stat_user_tables
        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
    " > "$stats_file" 2>/dev/null
    print_success "Table statistics saved: $stats_file"
}

backup_redis() {
    print_header "Backing Up Redis Data"

    if ! docker ps | grep -q "$REDIS_CONTAINER"; then
        print_info "Redis container not running, skipping Redis backup"
        return 0
    fi

    local backup_file="$BACKUP_DIR/${BACKUP_NAME}_redis.rdb"

    print_info "Starting Redis backup..."

    # Trigger Redis save
    docker exec "$REDIS_CONTAINER" redis-cli BGSAVE

    # Wait for save to complete
    print_info "Waiting for Redis to complete background save..."
    sleep 2

    # Copy RDB file
    docker cp "$REDIS_CONTAINER:/data/dump.rdb" "$backup_file"

    if [ $? -eq 0 ]; then
        local size=$(du -h "$backup_file" | cut -f1)
        print_success "Redis backup created: $backup_file ($size)"
    else
        print_error "Redis backup failed"
        return 1
    fi

    # Compress backup
    if [ "$USE_COMPRESSION" = true ]; then
        print_info "Compressing Redis backup..."
        gzip -$COMPRESSION_LEVEL "$backup_file"
        backup_file="${backup_file}.gz"
        print_success "Redis backup compressed: $backup_file"
    fi

    # Create checksum
    md5sum "$backup_file" > "${backup_file}.md5"
    print_success "Checksum created: ${backup_file}.md5"
}

backup_config() {
    print_header "Backing Up Configuration Files"

    local config_backup="$BACKUP_DIR/${BACKUP_NAME}_config.tar.gz"

    print_info "Starting configuration backup..."

    # Create tar archive of configuration files
    tar -czf "$config_backup" \
        --exclude='*.pyc' \
        --exclude='__pycache__' \
        --exclude='*.log' \
        --exclude='backups' \
        .env* \
        docker-compose*.yml \
        Dockerfile* \
        nginx/nginx.conf \
        nginx/ssl/*.pem 2>/dev/null \
        monitoring/*.yml 2>/dev/null \
        scripts/*.sh 2>/dev/null \
        || true

    if [ -f "$config_backup" ]; then
        local size=$(du -h "$config_backup" | cut -f1)
        print_success "Configuration backup created: $config_backup ($size)"
    else
        print_error "Configuration backup failed"
        return 1
    fi

    # Create checksum
    md5sum "$config_backup" > "${config_backup}.md5"
    print_success "Checksum created: ${config_backup}.md5"
}

create_backup_manifest() {
    print_header "Creating Backup Manifest"

    local manifest_file="$BACKUP_DIR/${BACKUP_NAME}_manifest.txt"

    cat > "$manifest_file" << EOF
Healthcare Agent Platform - Backup Manifest
============================================

Backup Date: $(date)
Backup Type: $BACKUP_TYPE
Hostname: $(hostname)
User: $(whoami)

Files Included:
EOF

    # List all backup files
    ls -lh "$BACKUP_DIR/${BACKUP_NAME}"* | awk '{print $5, $9}' >> "$manifest_file"

    # Add checksums
    echo "" >> "$manifest_file"
    echo "Checksums:" >> "$manifest_file"
    cat "$BACKUP_DIR/${BACKUP_NAME}"*.md5 >> "$manifest_file" 2>/dev/null || true

    # Add database statistics
    if [ -f "$BACKUP_DIR/${BACKUP_NAME}_stats.txt" ]; then
        echo "" >> "$manifest_file"
        echo "Database Statistics:" >> "$manifest_file"
        cat "$BACKUP_DIR/${BACKUP_NAME}_stats.txt" >> "$manifest_file"
    fi

    print_success "Manifest created: $manifest_file"
}

cleanup_old_backups() {
    print_header "Cleaning Up Old Backups"

    print_info "Removing backups older than $RETENTION_DAYS days..."

    local deleted_count=0
    while IFS= read -r file; do
        rm -f "$file"
        ((deleted_count++))
    done < <(find "$BACKUP_DIR" -name "healthcare_backup_*" -type f -mtime +$RETENTION_DAYS)

    if [ $deleted_count -gt 0 ]; then
        print_success "Deleted $deleted_count old backup files"
    else
        print_info "No old backups to delete"
    fi

    # Show remaining backups
    local remaining=$(find "$BACKUP_DIR" -name "healthcare_backup_*" -type f | wc -l)
    print_info "Total backup files: $remaining"

    # Show disk usage
    local backup_size=$(du -sh "$BACKUP_DIR" | cut -f1)
    print_info "Total backup size: $backup_size"
}

test_backup_integrity() {
    print_header "Testing Backup Integrity"

    # Verify checksums
    local checksum_failed=false
    for md5_file in "$BACKUP_DIR/${BACKUP_NAME}"*.md5; do
        if [ -f "$md5_file" ]; then
            if md5sum -c "$md5_file" > /dev/null 2>&1; then
                print_success "Checksum verified: $(basename $md5_file)"
            else
                print_error "Checksum verification failed: $(basename $md5_file)"
                checksum_failed=true
            fi
        fi
    done

    if [ "$checksum_failed" = true ]; then
        print_error "Some checksums failed verification"
        return 1
    fi

    # Test compressed files can be decompressed
    for gz_file in "$BACKUP_DIR/${BACKUP_NAME}"*.gz; do
        if [ -f "$gz_file" ]; then
            if gzip -t "$gz_file" > /dev/null 2>&1; then
                print_success "Archive is valid: $(basename $gz_file)"
            else
                print_error "Archive is corrupted: $(basename $gz_file)"
                return 1
            fi
        fi
    done

    print_success "All backup files passed integrity checks"
}

upload_to_remote() {
    print_header "Uploading to Remote Storage"

    # Check if remote storage is configured
    if [ -z "$BACKUP_REMOTE_PATH" ]; then
        print_info "Remote backup not configured (set BACKUP_REMOTE_PATH)"
        return 0
    fi

    print_info "Uploading to: $BACKUP_REMOTE_PATH"

    # Example for S3 (uncomment and configure)
    # aws s3 sync "$BACKUP_DIR/${BACKUP_NAME}"* "s3://$BACKUP_REMOTE_PATH/"

    # Example for rsync (uncomment and configure)
    # rsync -avz "$BACKUP_DIR/${BACKUP_NAME}"* "$BACKUP_REMOTE_PATH/"

    print_info "Remote backup feature not enabled"
}

send_notification() {
    local status=$1
    local message=$2

    # Example email notification (configure sendmail or use API)
    # echo "$message" | mail -s "Healthcare Agent Backup: $status" admin@example.com

    # Example Slack notification (uncomment and configure)
    # curl -X POST -H 'Content-type: application/json' \
    #   --data "{\"text\":\"Healthcare Agent Backup: $status\n$message\"}" \
    #   "$SLACK_WEBHOOK_URL"

    echo "$message"
}

###############################################################################
# Main Backup Function
###############################################################################

perform_backup() {
    local start_time=$(date +%s)

    print_header "Healthcare Agent Platform - Database Backup"
    print_info "Backup type: $BACKUP_TYPE"
    print_info "Timestamp: $TIMESTAMP"

    # Check prerequisites
    check_prerequisites

    # Perform backup based on type
    case $BACKUP_TYPE in
        full)
            backup_database
            backup_redis
            backup_config
            ;;
        db|database)
            backup_database
            ;;
        redis)
            backup_redis
            ;;
        config)
            backup_config
            ;;
        *)
            print_error "Invalid backup type: $BACKUP_TYPE"
            echo "Valid types: full, db, redis, config"
            exit 1
            ;;
    esac

    # Create manifest
    create_backup_manifest

    # Test integrity
    test_backup_integrity

    # Upload to remote (if configured)
    upload_to_remote

    # Cleanup old backups
    cleanup_old_backups

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    print_header "Backup Summary"
    echo ""
    print_success "Backup completed successfully!"
    print_info "Duration: ${duration} seconds"
    print_info "Backup location: $BACKUP_DIR"
    print_info "Backup name: $BACKUP_NAME"
    echo ""

    # Send success notification
    send_notification "SUCCESS" "Backup completed in ${duration}s"
}

###############################################################################
# Main Script
###############################################################################

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --type)
            BACKUP_TYPE="$2"
            shift 2
            ;;
        --destination)
            BACKUP_DIR="$2"
            shift 2
            ;;
        --retention)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --type TYPE          Backup type: full, db, redis, config (default: full)"
            echo "  --destination DIR    Backup destination directory (default: ./backups)"
            echo "  --retention DAYS     Retention period in days (default: 30)"
            echo "  --help               Show this help message"
            exit 0
            ;;
        *)
            # If it's the first positional argument, treat as type
            if [ -z "$BACKUP_TYPE_SET" ]; then
                BACKUP_TYPE="$1"
                BACKUP_TYPE_SET=true
            fi
            shift
            ;;
    esac
done

# Perform backup
if perform_backup; then
    exit 0
else
    print_error "Backup failed"
    send_notification "FAILED" "Backup failed after ${duration}s"
    exit 1
fi
