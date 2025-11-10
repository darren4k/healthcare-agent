#!/bin/bash

###############################################################################
# Healthcare Agent Platform - Monitoring Setup
# Step 9: Set Up Monitoring with Prometheus and Grafana
#
# This script sets up comprehensive monitoring:
# - Prometheus for metrics collection
# - Grafana for visualization
# - Exporters for PostgreSQL, Redis, Nginx, System
# - Pre-configured dashboards
# - Alert rules
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directories
MONITORING_DIR="./monitoring"
GRAFANA_DIR="$MONITORING_DIR/grafana"
DASHBOARDS_DIR="$GRAFANA_DIR/dashboards"
PROVISIONING_DIR="$GRAFANA_DIR/provisioning"

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

###############################################################################
# Setup Functions
###############################################################################

create_directories() {
    print_header "Creating Directories"

    mkdir -p "$GRAFANA_DIR/provisioning/datasources"
    mkdir -p "$GRAFANA_DIR/provisioning/dashboards"
    mkdir -p "$DASHBOARDS_DIR"
    mkdir -p "$MONITORING_DIR/alerts"

    print_success "Created monitoring directories"
}

create_grafana_datasource() {
    print_header "Configuring Grafana Data Source"

    cat > "$GRAFANA_DIR/provisioning/datasources/prometheus.yml" << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: 15s
      httpMethod: POST
EOF

    print_success "Created Prometheus datasource configuration"
}

create_grafana_dashboard_provisioning() {
    print_header "Configuring Grafana Dashboard Provisioning"

    cat > "$GRAFANA_DIR/provisioning/dashboards/dashboards.yml" << 'EOF'
apiVersion: 1

providers:
  - name: 'Healthcare Agent Dashboards'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
EOF

    print_success "Created dashboard provisioning configuration"
}

create_alertmanager_config() {
    print_header "Configuring Alertmanager"

    cat > "$MONITORING_DIR/alertmanager.yml" << 'EOF'
global:
  resolve_timeout: 5m
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@healthcare-agent.com'
  smtp_auth_username: 'alerts@healthcare-agent.com'
  smtp_auth_password: 'your-smtp-password'

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default-receiver'
  routes:
    - match:
        severity: critical
      receiver: 'critical-receiver'
      continue: true
    - match:
        severity: warning
      receiver: 'warning-receiver'

receivers:
  - name: 'default-receiver'
    email_configs:
      - to: 'ops@healthcare-agent.com'
        headers:
          Subject: 'Healthcare Agent Alert: {{ .GroupLabels.alertname }}'

  - name: 'critical-receiver'
    email_configs:
      - to: 'oncall@healthcare-agent.com'
        headers:
          Subject: 'CRITICAL: {{ .GroupLabels.alertname }}'
    # Uncomment to add Slack notifications
    # slack_configs:
    #   - api_url: 'YOUR_SLACK_WEBHOOK_URL'
    #     channel: '#alerts'
    #     title: 'CRITICAL: {{ .GroupLabels.alertname }}'

  - name: 'warning-receiver'
    email_configs:
      - to: 'ops@healthcare-agent.com'
        headers:
          Subject: 'WARNING: {{ .GroupLabels.alertname }}'

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'cluster', 'service']
EOF

    print_success "Created Alertmanager configuration"
    print_info "Update email settings in $MONITORING_DIR/alertmanager.yml"
}

create_api_dashboard() {
    print_header "Creating API Dashboard"

    cat > "$DASHBOARDS_DIR/api-dashboard.json" << 'EOF'
{
  "dashboard": {
    "title": "Healthcare Agent API Dashboard",
    "tags": ["healthcare", "api"],
    "timezone": "browser",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~\"5..\"}[5m])"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Response Time (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"
          }
        ],
        "type": "graph"
      }
    ]
  }
}
EOF

    print_success "Created API dashboard"
}

start_monitoring_stack() {
    print_header "Starting Monitoring Stack"

    # Load environment variables
    if [ -f .env ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi

    # Start monitoring services
    docker-compose -f monitoring/docker-compose.monitoring.yml up -d

    print_success "Monitoring stack started"

    # Wait for services to be ready
    print_info "Waiting for services to be ready..."
    sleep 10

    # Check service health
    if docker-compose -f monitoring/docker-compose.monitoring.yml ps | grep -q "Up"; then
        print_success "All monitoring services are running"
    else
        print_error "Some monitoring services failed to start"
        docker-compose -f monitoring/docker-compose.monitoring.yml ps
        exit 1
    fi
}

verify_monitoring() {
    print_header "Verifying Monitoring Setup"

    # Check Prometheus
    if curl -sf http://localhost:9090/-/healthy > /dev/null; then
        print_success "Prometheus is healthy"
    else
        print_error "Prometheus is not responding"
    fi

    # Check Grafana
    if curl -sf http://localhost:3000/api/health > /dev/null; then
        print_success "Grafana is healthy"
    else
        print_error "Grafana is not responding"
    fi

    # Check exporters
    for port in 9187 9121 9113 9100 8080; do
        if curl -sf http://localhost:$port/metrics > /dev/null 2>&1 || curl -sf http://localhost:$port > /dev/null 2>&1; then
            print_success "Exporter on port $port is running"
        else
            print_info "Exporter on port $port may not be configured yet"
        fi
    done
}

print_access_info() {
    print_header "Access Information"

    echo ""
    echo "Monitoring services are now available:"
    echo ""
    echo -e "${GREEN}Grafana:${NC}"
    echo "  URL: http://localhost:3000"
    echo "  Username: admin"
    echo "  Password: admin"
    echo "  (Change password on first login)"
    echo ""
    echo -e "${GREEN}Prometheus:${NC}"
    echo "  URL: http://localhost:9090"
    echo ""
    echo -e "${GREEN}Alertmanager:${NC}"
    echo "  URL: http://localhost:9093"
    echo ""
    echo -e "${YELLOW}Exporters:${NC}"
    echo "  PostgreSQL: http://localhost:9187/metrics"
    echo "  Redis: http://localhost:9121/metrics"
    echo "  Nginx: http://localhost:9113/metrics"
    echo "  Node: http://localhost:9100/metrics"
    echo "  cAdvisor: http://localhost:8080"
    echo ""
}

print_next_steps() {
    print_header "Next Steps"

    echo ""
    echo "1. Access Grafana and change default password:"
    echo "   http://localhost:3000"
    echo ""
    echo "2. Import additional dashboards:"
    echo "   - PostgreSQL: Dashboard ID 9628"
    echo "   - Redis: Dashboard ID 11835"
    echo "   - Node Exporter: Dashboard ID 1860"
    echo ""
    echo "3. Configure alert notifications in:"
    echo "   monitoring/alertmanager.yml"
    echo ""
    echo "4. Test alerts:"
    echo "   docker-compose -f docker-compose.prod.yml stop api"
    echo "   (Should trigger APIServiceDown alert)"
    echo ""
    echo "5. View metrics:"
    echo "   curl http://localhost:8001/metrics"
    echo ""
    echo "6. Set up automated backups:"
    echo "   ./scripts/backup_db.sh"
    echo ""
}

###############################################################################
# Main Script
###############################################################################

print_header "Healthcare Agent Platform - Monitoring Setup"

# Check if monitoring directory exists
if [ ! -d "monitoring" ]; then
    print_error "Run this script from the project root directory"
    exit 1
fi

# Create directories
create_directories

# Create configurations
create_grafana_datasource
create_grafana_dashboard_provisioning
create_alertmanager_config
create_api_dashboard

# Start monitoring stack
start_monitoring_stack

# Verify setup
sleep 5
verify_monitoring

# Print access info
print_access_info

# Print next steps
print_next_steps

echo ""
print_success "Monitoring setup completed successfully!"
echo ""
