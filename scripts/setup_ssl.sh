#!/bin/bash

###############################################################################
# Healthcare Agent Platform - SSL Certificate Setup
# Step 7: Configure SSL/TLS Certificates
#
# This script automates SSL certificate setup using:
# - Let's Encrypt (Certbot) for production
# - Self-signed certificates for development/testing
#
# Usage:
#   ./scripts/setup_ssl.sh --domain api.yourdomain.com --email admin@yourdomain.com
#   ./scripts/setup_ssl.sh --self-signed  # For testing
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOMAIN=""
EMAIL=""
SELF_SIGNED=false
SSL_DIR="./nginx/ssl"
CERTBOT_WEBROOT="/var/www/certbot"

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

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --domain DOMAIN     Domain name (e.g., api.yourdomain.com)"
    echo "  --email EMAIL       Email for Let's Encrypt notifications"
    echo "  --self-signed       Generate self-signed certificate for testing"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  # Production with Let's Encrypt:"
    echo "  $0 --domain api.healthcare.com --email admin@healthcare.com"
    echo ""
    echo "  # Self-signed for testing:"
    echo "  $0 --self-signed"
    exit 1
}

check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check if running as root (needed for certbot)
    if [ ! "$SELF_SIGNED" = true ] && [ "$EUID" -ne 0 ]; then
        print_error "This script must be run as root for Let's Encrypt setup"
        echo "Use: sudo $0 $@"
        exit 1
    fi

    # Check if openssl is installed (for self-signed)
    if [ "$SELF_SIGNED" = true ]; then
        if ! command -v openssl &> /dev/null; then
            print_error "openssl is not installed"
            echo "Install: sudo apt-get install openssl"
            exit 1
        fi
        print_success "openssl is installed"
    fi

    # Check if certbot is installed (for Let's Encrypt)
    if [ ! "$SELF_SIGNED" = true ]; then
        if ! command -v certbot &> /dev/null; then
            print_info "certbot not found. Installing..."
            apt-get update
            apt-get install -y certbot
            print_success "certbot installed"
        else
            print_success "certbot is installed"
        fi
    fi

    # Create SSL directory if it doesn't exist
    mkdir -p "$SSL_DIR"
    print_success "SSL directory created: $SSL_DIR"
}

generate_self_signed_cert() {
    print_header "Generating Self-Signed Certificate"

    print_info "This certificate is for TESTING ONLY"
    print_info "For production, use Let's Encrypt (--domain option)"

    # Generate private key
    openssl genrsa -out "$SSL_DIR/key.pem" 2048
    print_success "Generated private key"

    # Generate certificate
    openssl req -new -x509 -key "$SSL_DIR/key.pem" -out "$SSL_DIR/cert.pem" -days 365 \
        -subj "/C=US/ST=State/L=City/O=Healthcare Agent/CN=localhost"
    print_success "Generated self-signed certificate (valid for 365 days)"

    # Generate dhparam
    openssl dhparam -out "$SSL_DIR/dhparam.pem" 2048
    print_success "Generated Diffie-Hellman parameters"

    # Set permissions
    chmod 600 "$SSL_DIR/key.pem"
    chmod 644 "$SSL_DIR/cert.pem"
    chmod 644 "$SSL_DIR/dhparam.pem"
    print_success "Set appropriate file permissions"

    echo ""
    print_success "Self-signed certificate generated successfully!"
    echo ""
    print_info "Certificate details:"
    openssl x509 -in "$SSL_DIR/cert.pem" -noout -text | grep -E "Subject:|Issuer:|Not Before:|Not After"
    echo ""
    print_info "Warning: Browsers will show security warnings for self-signed certificates"
    print_info "Files created:"
    echo "  - $SSL_DIR/cert.pem (certificate)"
    echo "  - $SSL_DIR/key.pem (private key)"
    echo "  - $SSL_DIR/dhparam.pem (DH parameters)"
}

setup_letsencrypt() {
    print_header "Setting Up Let's Encrypt Certificate"

    if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
        print_error "Domain and email are required for Let's Encrypt"
        usage
    fi

    print_info "Domain: $DOMAIN"
    print_info "Email: $EMAIL"

    # Check if port 80 is available
    if netstat -tuln | grep -q ":80 "; then
        print_error "Port 80 is already in use"
        print_info "Stop nginx temporarily: docker-compose -f docker-compose.prod.yml stop nginx"
        exit 1
    fi

    # Create webroot directory for verification
    mkdir -p "$CERTBOT_WEBROOT"

    # Obtain certificate using standalone mode
    print_info "Requesting certificate from Let's Encrypt..."
    print_info "This may take a few minutes..."

    certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        --domains "$DOMAIN" \
        --keep-until-expiring

    if [ $? -eq 0 ]; then
        print_success "Certificate obtained successfully!"
    else
        print_error "Failed to obtain certificate"
        exit 1
    fi

    # Copy certificates to nginx SSL directory
    print_info "Copying certificates to nginx directory..."

    cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$SSL_DIR/cert.pem"
    cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$SSL_DIR/key.pem"
    cp "/etc/letsencrypt/live/$DOMAIN/chain.pem" "$SSL_DIR/chain.pem"

    # Generate dhparam if it doesn't exist
    if [ ! -f "$SSL_DIR/dhparam.pem" ]; then
        print_info "Generating Diffie-Hellman parameters (this may take several minutes)..."
        openssl dhparam -out "$SSL_DIR/dhparam.pem" 2048
    fi

    # Set permissions
    chmod 600 "$SSL_DIR/key.pem"
    chmod 644 "$SSL_DIR/cert.pem"
    chmod 644 "$SSL_DIR/chain.pem"
    chmod 644 "$SSL_DIR/dhparam.pem"
    print_success "Set appropriate file permissions"

    # Set up auto-renewal
    setup_auto_renewal

    echo ""
    print_success "Let's Encrypt certificate configured successfully!"
    echo ""
    print_info "Certificate details:"
    openssl x509 -in "$SSL_DIR/cert.pem" -noout -text | grep -E "Subject:|Issuer:|Not Before:|Not After"
    echo ""
    print_info "Files created:"
    echo "  - $SSL_DIR/cert.pem (certificate)"
    echo "  - $SSL_DIR/key.pem (private key)"
    echo "  - $SSL_DIR/chain.pem (certificate chain)"
    echo "  - $SSL_DIR/dhparam.pem (DH parameters)"
}

setup_auto_renewal() {
    print_header "Setting Up Auto-Renewal"

    # Create renewal script
    cat > /usr/local/bin/renew-healthcare-cert.sh << 'RENEWAL_SCRIPT'
#!/bin/bash
# Healthcare Agent SSL Certificate Renewal Script

certbot renew --quiet

if [ $? -eq 0 ]; then
    # Copy renewed certificates
    cp /etc/letsencrypt/live/*/fullchain.pem /path/to/healthcare-agent/nginx/ssl/cert.pem
    cp /etc/letsencrypt/live/*/privkey.pem /path/to/healthcare-agent/nginx/ssl/key.pem
    cp /etc/letsencrypt/live/*/chain.pem /path/to/healthcare-agent/nginx/ssl/chain.pem

    # Reload nginx
    docker-compose -f /path/to/healthcare-agent/docker-compose.prod.yml exec nginx nginx -s reload

    echo "SSL certificate renewed and nginx reloaded"
fi
RENEWAL_SCRIPT

    # Update paths in renewal script
    sed -i "s|/path/to/healthcare-agent|$(pwd)|g" /usr/local/bin/renew-healthcare-cert.sh

    # Make executable
    chmod +x /usr/local/bin/renew-healthcare-cert.sh
    print_success "Created renewal script: /usr/local/bin/renew-healthcare-cert.sh"

    # Add to crontab (run daily at 2:30 AM)
    (crontab -l 2>/dev/null | grep -v "renew-healthcare-cert"; echo "30 2 * * * /usr/local/bin/renew-healthcare-cert.sh >> /var/log/ssl-renewal.log 2>&1") | crontab -
    print_success "Added auto-renewal to crontab (daily at 2:30 AM)"

    print_info "Let's Encrypt certificates are valid for 90 days"
    print_info "Auto-renewal will run daily and renew when needed (< 30 days remaining)"
}

verify_ssl_setup() {
    print_header "Verifying SSL Setup"

    # Check if certificate files exist
    if [ -f "$SSL_DIR/cert.pem" ] && [ -f "$SSL_DIR/key.pem" ]; then
        print_success "Certificate files exist"
    else
        print_error "Certificate files not found"
        exit 1
    fi

    # Verify certificate
    print_info "Certificate information:"
    openssl x509 -in "$SSL_DIR/cert.pem" -noout -subject -issuer -dates

    # Check certificate validity
    if openssl x509 -in "$SSL_DIR/cert.pem" -noout -checkend 86400; then
        print_success "Certificate is valid for at least 24 hours"
    else
        print_error "Certificate expires within 24 hours!"
    fi

    # Test private key matches certificate
    cert_modulus=$(openssl x509 -in "$SSL_DIR/cert.pem" -noout -modulus | md5sum)
    key_modulus=$(openssl rsa -in "$SSL_DIR/key.pem" -noout -modulus 2>/dev/null | md5sum)

    if [ "$cert_modulus" = "$key_modulus" ]; then
        print_success "Private key matches certificate"
    else
        print_error "Private key does not match certificate!"
        exit 1
    fi
}

restart_nginx() {
    print_header "Restarting Nginx"

    print_info "Restarting nginx to apply SSL configuration..."

    if docker-compose -f docker-compose.prod.yml ps nginx | grep -q "Up"; then
        docker-compose -f docker-compose.prod.yml restart nginx
        print_success "Nginx restarted successfully"
    else
        print_info "Starting nginx..."
        docker-compose -f docker-compose.prod.yml up -d nginx
        print_success "Nginx started successfully"
    fi

    # Wait for nginx to be ready
    sleep 3

    # Test nginx configuration
    if docker-compose -f docker-compose.prod.yml exec nginx nginx -t 2>&1 | grep -q "successful"; then
        print_success "Nginx configuration is valid"
    else
        print_error "Nginx configuration test failed"
        docker-compose -f docker-compose.prod.yml exec nginx nginx -t
        exit 1
    fi
}

print_next_steps() {
    print_header "Next Steps"

    echo ""
    echo "1. Update your DNS records:"
    echo "   A    $DOMAIN -> YOUR_SERVER_IP"
    echo ""
    echo "2. Update .env file:"
    echo "   CORS_ORIGINS=https://$DOMAIN"
    echo ""
    echo "3. Restart all services:"
    echo "   docker-compose -f docker-compose.prod.yml restart"
    echo ""
    echo "4. Test HTTPS access:"
    echo "   curl https://$DOMAIN/health"
    echo ""
    echo "5. Test SSL certificate:"
    echo "   openssl s_client -connect $DOMAIN:443 -servername $DOMAIN"
    echo ""
}

###############################################################################
# Main Script
###############################################################################

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --email)
            EMAIL="$2"
            shift 2
            ;;
        --self-signed)
            SELF_SIGNED=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate arguments
if [ "$SELF_SIGNED" = false ] && ([ -z "$DOMAIN" ] || [ -z "$EMAIL" ]); then
    print_error "Either use --self-signed or provide --domain and --email"
    usage
fi

print_header "Healthcare Agent Platform - SSL Setup"

# Check prerequisites
check_prerequisites

# Generate certificate
if [ "$SELF_SIGNED" = true ]; then
    generate_self_signed_cert
else
    setup_letsencrypt
fi

# Verify SSL setup
verify_ssl_setup

# Restart nginx
restart_nginx

# Print next steps
if [ ! "$SELF_SIGNED" = true ]; then
    print_next_steps
fi

echo ""
print_success "SSL setup completed successfully!"
echo ""
