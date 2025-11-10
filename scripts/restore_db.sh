#!/bin/bash

###############################################################################
# Healthcare Agent Platform - Database Restore Script
# Restore backups created by backup_db.sh
#
# This script restores:
# - PostgreSQL database
# - Redis data
# - Configuration files
#
# Usage:
#   ./scripts/restore_db.sh --backup healthcare_backup_20251110_020000
#   ./scripts/restore_db.sh --file /path/to/backup_postgres.sql.gz
#   ./scripts/restore_db.sh --latest  # Restore latest backup
#
# WARNING: This will OVERWRITE existing data!
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_NAME=""
RESTORE_TYPE="full"  # full, db, redis, or config
SKIP_CONFIRMATION=false

# Database configuration
DB_CONTAINER="healthcare-agent-db-1"
REDIS_CONTAINER="healthcare-agent-redis-1"
DB_USER="postgres"
DB_NAME="healthcare_agent_prod"

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

print_warning() {
    echo -e "${RED}⚠ WARNING: $1${NC}"
}

list_available_backups() {
    print_header "Available Backups"

    if [ ! -d "$BACKUP_DIR" ]; then
        print_error "Backup directory not found: $BACKUP_DIR"
        exit 1
    fi

    # Find all backup manifests
    local backups=($(find "$BACKUP_DIR" -name "*_manifest.txt" -type f | sort -r))

    if [ ${#backups[@]} -eq 0 ]; then
        print_error "No backups found in $BACKUP_DIR"
        exit 1
    fi

    echo ""
    echo "Found ${#backups[@]} backup(s):"
    echo ""

    local index=1
    for manifest in "${backups[@]}"; do
        local backup_name=$(basename "$manifest" "_manifest.txt")
        local backup_date=$(echo "$backup_name" | sed 's/healthcare_backup_//' | sed 's/_/ /')
        local backup_size=$(du -sh "$(dirname $manifest)" | cut -f1)

        echo "[$index] $backup_date"
        echo "    Name: $backup_name"
        echo "    Size: $backup_size"

        # Show what's included
        if [ -f "$(dirname $manifest)/${backup_name}_postgres.sql.gz" ]; then
            echo "    - PostgreSQL database ✓"
        fi
        if [ -f "$(dirname $manifest)/${backup_name}_redis.rdb.gz" ]; then
            echo "    - Redis data ✓"
        fi
        if [ -f "$(dirname $manifest)/${backup_name}_config.tar.gz" ]; then
            echo "    - Configuration files ✓"
        fi
        echo ""

        ((index++))
    done
}

get_latest_backup() {
    local latest=$(find "$BACKUP_DIR" -name "*_manifest.txt" -type f | sort -r | head -n 1)

    if [ -z "$latest" ]; then
        print_error "No backups found"
        exit 1
    fi

    BACKUP_NAME=$(basename "$latest" "_manifest.txt")
    print_info "Latest backup: $BACKUP_NAME"
}

verify_backup_integrity() {
    print_header "Verifying Backup Integrity"

    local backup_path="$BACKUP_DIR/$BACKUP_NAME"

    # Check if backup exists
    if [ ! -d "$BACKUP_DIR" ]; then
        print_error "Backup not found: $backup_path"
        exit 1
    fi

    # Verify checksums
    local checksum_failed=false
    for md5_file in "$backup_path"*.md5; do
        if [ -f "$md5_file" ]; then
            local file_to_check=$(echo "$md5_file" | sed 's/.md5$//')
            if md5sum -c "$md5_file" > /dev/null 2>&1; then
                print_success "Checksum verified: $(basename $file_to_check)"
            else
                print_error "Checksum verification failed: $(basename $file_to_check)"
                checksum_failed=true
            fi
        fi
    done

    if [ "$checksum_failed" = true ]; then
        print_error "Backup integrity check failed"
        return 1
    fi

    print_success "Backup integrity verified"
}

confirm_restore() {
    if [ "$SKIP_CONFIRMATION" = true ]; then
        return 0
    fi

    print_warning "This will OVERWRITE existing data!"
    print_warning "Backup: $BACKUP_NAME"
    print_warning "Target database: $DB_NAME"
    echo ""
    read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirmation

    if [ "$confirmation" != "yes" ]; then
        print_info "Restore cancelled"
        exit 0
    fi

    print_success "Confirmation received"
}

create_pre_restore_backup() {
    print_header "Creating Pre-Restore Backup"

    print_info "Creating safety backup of current data..."

    local safety_backup="$BACKUP_DIR/pre_restore_$(date +%Y%m%d_%H%M%S)"

    # Backup current database
    docker exec -t "$DB_CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" \
        > "${safety_backup}_postgres.sql" 2>/dev/null

    if [ $? -eq 0 ]; then
        gzip "${safety_backup}_postgres.sql"
        print_success "Safety backup created: ${safety_backup}_postgres.sql.gz"
    else
        print_error "Failed to create safety backup"
        read -p "Continue without safety backup? (type 'yes'): " cont
        if [ "$cont" != "yes" ]; then
            exit 1
        fi
    fi
}

restore_database() {
    print_header "Restoring PostgreSQL Database"

    local backup_file="$BACKUP_DIR/${BACKUP_NAME}_postgres.sql.gz"

    if [ ! -f "$backup_file" ]; then
        # Try without .gz extension
        backup_file="${backup_file%.gz}"
        if [ ! -f "$backup_file" ]; then
            print_error "Database backup file not found"
            return 1
        fi
    fi

    print_info "Backup file: $backup_file"
    print_info "Target database: $DB_NAME"

    # Stop API and Celery workers to prevent connections
    print_info "Stopping API and Celery workers..."
    docker-compose -f docker-compose.prod.yml stop api celery celery-beat 2>/dev/null || true

    # Terminate existing connections
    print_info "Terminating existing database connections..."
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid();" \
        > /dev/null 2>&1 || true

    # Drop and recreate database
    print_info "Dropping existing database..."
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c \
        "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null

    print_info "Creating fresh database..."
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c \
        "CREATE DATABASE $DB_NAME;" 2>/dev/null

    # Enable pgvector extension
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c \
        "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null

    # Restore database
    print_info "Restoring database from backup..."

    if [[ "$backup_file" == *.gz ]]; then
        gunzip -c "$backup_file" | docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1
    else
        cat "$backup_file" | docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1
    fi

    if [ $? -eq 0 ]; then
        print_success "Database restored successfully"
    else
        print_error "Database restore failed"
        return 1
    fi

    # Verify restore
    print_info "Verifying database restore..."
    local table_count=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' ')

    print_success "Restored $table_count tables"

    # Show row counts
    print_info "Table row counts:"
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c \
        "SELECT schemaname, tablename, n_live_tup AS rows FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 10;" \
        2>/dev/null || true

    # Restart services
    print_info "Restarting API and Celery workers..."
    docker-compose -f docker-compose.prod.yml start api celery celery-beat 2>/dev/null || true
    sleep 5

    print_success "Database restoration complete"
}

restore_redis() {
    print_header "Restoring Redis Data"

    local backup_file="$BACKUP_DIR/${BACKUP_NAME}_redis.rdb.gz"

    if [ ! -f "$backup_file" ]; then
        backup_file="${backup_file%.gz}"
        if [ ! -f "$backup_file" ]; then
            print_info "Redis backup file not found, skipping"
            return 0
        fi
    fi

    if ! docker ps | grep -q "$REDIS_CONTAINER"; then
        print_error "Redis container is not running"
        return 1
    fi

    print_info "Backup file: $backup_file"

    # Stop services using Redis
    print_info "Stopping services..."
    docker-compose -f docker-compose.prod.yml stop api celery celery-beat 2>/dev/null || true

    # Stop Redis
    print_info "Stopping Redis..."
    docker-compose -f docker-compose.prod.yml stop redis 2>/dev/null

    # Decompress if needed
    local rdb_file="$backup_file"
    if [[ "$backup_file" == *.gz ]]; then
        print_info "Decompressing Redis backup..."
        rdb_file="/tmp/restore_dump.rdb"
        gunzip -c "$backup_file" > "$rdb_file"
    fi

    # Copy RDB file to Redis container
    print_info "Copying RDB file to Redis container..."
    docker cp "$rdb_file" "$REDIS_CONTAINER:/data/dump.rdb"

    # Start Redis
    print_info "Starting Redis..."
    docker-compose -f docker-compose.prod.yml start redis 2>/dev/null
    sleep 3

    # Verify Redis is working
    if docker exec "$REDIS_CONTAINER" redis-cli ping | grep -q "PONG"; then
        print_success "Redis restored successfully"
    else
        print_error "Redis restore failed"
        return 1
    fi

    # Restart services
    print_info "Restarting services..."
    docker-compose -f docker-compose.prod.yml start api celery celery-beat 2>/dev/null || true

    # Cleanup temp file
    if [ -f "/tmp/restore_dump.rdb" ]; then
        rm -f "/tmp/restore_dump.rdb"
    fi

    print_success "Redis restoration complete"
}

restore_config() {
    print_header "Restoring Configuration Files"

    local backup_file="$BACKUP_DIR/${BACKUP_NAME}_config.tar.gz"

    if [ ! -f "$backup_file" ]; then
        print_info "Configuration backup file not found, skipping"
        return 0
    fi

    print_info "Backup file: $backup_file"

    # Create backup of current config
    print_info "Backing up current configuration..."
    tar -czf "./config_backup_$(date +%Y%m%d_%H%M%S).tar.gz" \
        .env* docker-compose*.yml Dockerfile* nginx/ 2>/dev/null || true

    # Extract configuration
    print_info "Extracting configuration files..."
    tar -xzf "$backup_file" -C .

    print_success "Configuration files restored"
    print_warning "Review configuration files before restarting services"
}

verify_restore() {
    print_header "Verifying Restore"

    # Test database connection
    print_info "Testing database connection..."
    if docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
        print_success "Database is accessible"
    else
        print_error "Database connection failed"
        return 1
    fi

    # Test Redis connection
    if docker ps | grep -q "$REDIS_CONTAINER"; then
        print_info "Testing Redis connection..."
        if docker exec "$REDIS_CONTAINER" redis-cli ping | grep -q "PONG"; then
            print_success "Redis is accessible"
        else
            print_error "Redis connection failed"
            return 1
        fi
    fi

    # Test API health
    print_info "Testing API health..."
    sleep 5  # Wait for API to start
    if curl -sf http://localhost:8001/health > /dev/null; then
        print_success "API is responding"
    else
        print_warning "API health check failed (may need more time to start)"
    fi

    print_success "Restore verification complete"
}

###############################################################################
# Main Restore Function
###############################################################################

perform_restore() {
    local start_time=$(date +%s)

    print_header "Healthcare Agent Platform - Database Restore"

    # Get backup name if --latest specified
    if [ "$BACKUP_NAME" = "latest" ]; then
        get_latest_backup
    fi

    if [ -z "$BACKUP_NAME" ]; then
        list_available_backups
        read -p "Enter backup name to restore: " BACKUP_NAME
    fi

    print_info "Backup: $BACKUP_NAME"
    print_info "Restore type: $RESTORE_TYPE"

    # Verify backup integrity
    verify_backup_integrity

    # Confirm restore
    confirm_restore

    # Create pre-restore backup
    create_pre_restore_backup

    # Perform restore based on type
    case $RESTORE_TYPE in
        full)
            restore_database
            restore_redis
            restore_config
            ;;
        db|database)
            restore_database
            ;;
        redis)
            restore_redis
            ;;
        config)
            restore_config
            ;;
        *)
            print_error "Invalid restore type: $RESTORE_TYPE"
            exit 1
            ;;
    esac

    # Verify restore
    verify_restore

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    print_header "Restore Summary"
    echo ""
    print_success "Restore completed successfully!"
    print_info "Duration: ${duration} seconds"
    print_info "Restored from: $BACKUP_NAME"
    echo ""
    print_info "Next steps:"
    echo "1. Verify application functionality"
    echo "2. Check logs: docker-compose -f docker-compose.prod.yml logs -f"
    echo "3. Run tests: ./scripts/test_deployment.sh"
    echo ""
}

###############################################################################
# Main Script
###############################################################################

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --backup)
            BACKUP_NAME="$2"
            shift 2
            ;;
        --latest)
            BACKUP_NAME="latest"
            shift
            ;;
        --type)
            RESTORE_TYPE="$2"
            shift 2
            ;;
        --yes)
            SKIP_CONFIRMATION=true
            shift
            ;;
        --list)
            list_available_backups
            exit 0
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --backup NAME    Backup name to restore"
            echo "  --latest         Restore latest backup"
            echo "  --type TYPE      Restore type: full, db, redis, config (default: full)"
            echo "  --yes            Skip confirmation prompt"
            echo "  --list           List available backups"
            echo "  --help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 --latest"
            echo "  $0 --backup healthcare_backup_20251110_020000"
            echo "  $0 --backup healthcare_backup_20251110_020000 --type db"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Perform restore
if perform_restore; then
    exit 0
else
    print_error "Restore failed"
    exit 1
fi
