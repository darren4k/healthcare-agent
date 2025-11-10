#!/bin/bash
# Production Deployment Script for Healthcare Agent Platform
# This script automates the complete deployment process

set -e  # Exit on error

echo "========================================="
echo "Healthcare Agent Platform - Production Deployment"
echo "========================================="
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found!"
    echo "Please copy .env.production to .env and configure your credentials."
    echo ""
    echo "Run: cp .env.production .env"
    echo "Then edit .env with your actual credentials"
    exit 1
fi

# Check required environment variables
required_vars=(
    "DB_PASSWORD"
    "JWT_SECRET_KEY"
    "LLM_API_KEY"
    "HELLONOTE_USERNAME"
    "HELLONOTE_PASSWORD"
    "TWILIO_ACCOUNT_SID"
    "SENDGRID_API_KEY"
)

echo "Step 1: Validating environment configuration..."
missing_vars=()
for var in "${required_vars[@]}"; do
    if ! grep -q "^${var}=" .env || grep -q "^${var}=CHANGE_THIS" .env || grep -q "^${var}=your_" .env; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "ERROR: The following environment variables are not configured:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo "Please edit .env file and set these variables to valid values."
    exit 1
fi
echo "✓ Environment configuration validated"
echo ""

# Create necessary directories
echo "Step 2: Creating data directories..."
mkdir -p data/logs/screenshots
mkdir -p data/logs/videos
mkdir -p data/logs/traces
mkdir -p data/logs/nginx
mkdir -p data/uploads
mkdir -p nginx/ssl
echo "✓ Data directories created"
echo ""

# Generate self-signed SSL certificate for testing (replace with real cert in production)
echo "Step 3: Setting up SSL certificates..."
if [ ! -f nginx/ssl/cert.pem ]; then
    echo "Generating self-signed SSL certificate for testing..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout nginx/ssl/key.pem \
        -out nginx/ssl/cert.pem \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
    echo "✓ Self-signed certificate generated"
    echo "NOTE: Replace with real SSL certificate before production launch!"
else
    echo "✓ SSL certificates already exist"
fi
echo ""

# Stop existing containers
echo "Step 4: Stopping existing containers..."
docker-compose -f docker-compose.prod.yml down || true
echo "✓ Existing containers stopped"
echo ""

# Build Docker images
echo "Step 5: Building Docker images..."
docker-compose -f docker-compose.prod.yml build --no-cache
echo "✓ Docker images built"
echo ""

# Start database first
echo "Step 6: Starting database..."
docker-compose -f docker-compose.prod.yml up -d db redis
echo "Waiting for database to be ready..."
sleep 10
echo "✓ Database started"
echo ""

# Run database migrations
echo "Step 7: Running database migrations..."
docker-compose -f docker-compose.prod.yml run --rm api alembic upgrade head
echo "✓ Database migrations completed"
echo ""

# Seed initial data
echo "Step 8: Seeding initial data..."
docker-compose -f docker-compose.prod.yml run --rm api python scripts/seed_data.py
echo "✓ Initial data seeded"
echo ""

# Initialize vector database
echo "Step 9: Initializing vector database..."
if grep -q "VECTOR_STORE=pinecone" .env; then
    echo "Creating Pinecone index..."
    docker-compose -f docker-compose.prod.yml run --rm api python scripts/init_pinecone.py
elif grep -q "VECTOR_STORE=pgvector" .env; then
    echo "Initializing pgvector..."
    docker-compose -f docker-compose.prod.yml run --rm api python scripts/init_pgvector.py
fi
echo "✓ Vector database initialized"
echo ""

# Start all services
echo "Step 10: Starting all services..."
docker-compose -f docker-compose.prod.yml up -d
echo "✓ All services started"
echo ""

# Wait for services to be healthy
echo "Step 11: Waiting for services to be healthy..."
sleep 15

# Health checks
echo "Step 12: Running health checks..."
echo ""
echo "API Health:"
curl -s http://localhost:8001/health | python -m json.tool || echo "API not ready yet"
echo ""

echo "Database Connection:"
docker-compose -f docker-compose.prod.yml exec -T db pg_isready -U postgres || echo "Database not ready yet"
echo ""

echo "Redis Connection:"
docker-compose -f docker-compose.prod.yml exec -T redis redis-cli ping || echo "Redis not ready yet"
echo ""

echo "Celery Worker:"
docker-compose -f docker-compose.prod.yml exec -T celery celery -A tasks.celery_app inspect ping || echo "Celery not ready yet"
echo ""

# Display service status
echo "Step 13: Service Status"
echo "========================================="
docker-compose -f docker-compose.prod.yml ps
echo ""

# Display logs
echo "Step 14: Recent logs (last 20 lines)"
echo "========================================="
docker-compose -f docker-compose.prod.yml logs --tail=20
echo ""

echo "========================================="
echo "✓ Deployment Complete!"
echo "========================================="
echo ""
echo "Services are running at:"
echo "  - API: http://localhost:8001"
echo "  - API Docs: http://localhost:8001/docs"
echo "  - Frontend: http://localhost:80"
echo "  - Database: localhost:5432"
echo "  - Redis: localhost:6379"
echo ""
echo "Next steps:"
echo "  1. Test API: curl http://localhost:8001/health"
echo "  2. Access API docs: http://localhost:8001/docs"
echo "  3. Submit test SOAP note"
echo "  4. Configure your domain and SSL certificates"
echo "  5. Set up monitoring and alerts"
echo ""
echo "To view logs:"
echo "  docker-compose -f docker-compose.prod.yml logs -f"
echo ""
echo "To stop all services:"
echo "  docker-compose -f docker-compose.prod.yml down"
echo ""
echo "For troubleshooting, see: docs/TROUBLESHOOTING.md"
echo ""
