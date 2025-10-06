#!/bin/bash

# Deployment script for retirement planning system
set -e

# Configuration
ENVIRONMENT=${1:-staging}
VERSION=${2:-latest}
COMPOSE_FILE="docker-compose.yml"

if [ "$ENVIRONMENT" = "staging" ]; then
    COMPOSE_FILE="docker-compose.staging.yml"
fi

echo "🚀 Starting deployment for environment: $ENVIRONMENT"
echo "📦 Version: $VERSION"

# Pre-deployment checks
echo "🔍 Running pre-deployment checks..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if required files exist
required_files=("$COMPOSE_FILE" "Dockerfile" "requirements.txt")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Required file $file not found."
        exit 1
    fi
done

# Build and deploy
echo "🏗️ Building application..."
docker-compose -f $COMPOSE_FILE build --no-cache

echo "🗄️ Starting database..."
docker-compose -f $COMPOSE_FILE up -d db

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
sleep 10

# Run database migrations
echo "🔄 Running database migrations..."
docker-compose -f $COMPOSE_FILE run --rm app alembic upgrade head

echo "🚀 Starting all services..."
docker-compose -f $COMPOSE_FILE up -d

# Health check
echo "🏥 Running health checks..."
sleep 15

if [ "$ENVIRONMENT" = "staging" ]; then
    HEALTH_URL="http://localhost:8001/health"
else
    HEALTH_URL="http://localhost:8000/health"
fi

for i in {1..10}; do
    if curl -f $HEALTH_URL > /dev/null 2>&1; then
        echo "✅ Health check passed!"
        break
    else
        echo "⏳ Health check attempt $i/10 failed, retrying..."
        sleep 5
    fi
    
    if [ $i -eq 10 ]; then
        echo "❌ Health check failed after 10 attempts"
        docker-compose -f $COMPOSE_FILE logs app
        exit 1
    fi
done

# Show running services
echo "📊 Deployment status:"
docker-compose -f $COMPOSE_FILE ps

echo "✅ Deployment completed successfully!"
echo "🌐 Application is available at: $HEALTH_URL"

# Show logs
echo "📋 Recent logs:"
docker-compose -f $COMPOSE_FILE logs --tail=20 app
