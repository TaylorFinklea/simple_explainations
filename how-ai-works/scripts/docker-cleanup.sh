#!/bin/bash

# Docker Complete Cleanup Script
# This script removes ALL Docker data: images, containers, volumes, networks, and build cache

set -e

echo "🧹 Starting Docker cleanup..."
echo "⚠️  This will remove ALL Docker data (images, containers, volumes, build cache)"
echo "Press Ctrl+C within 5 seconds to cancel..."
sleep 5

echo ""
echo "📊 Current Docker disk usage:"
docker system df

echo ""
echo "🗑️  Step 1: Removing all unused Docker data..."
docker system prune -a --volumes -f

echo ""
echo "🗑️  Step 2: Force removing any remaining volumes..."
docker volume ls -q | xargs -r docker volume rm 2>/dev/null || true

echo ""
echo "🗑️  Step 3: Force removing any remaining images..."
docker images -q | xargs -r docker rmi -f 2>/dev/null || true

echo ""
echo "🗑️  Step 4: Removing all build cache..."
docker builder prune -a -f

echo ""
echo "✅ Cleanup complete! Final Docker disk usage:"
docker system df

echo ""
echo "🎉 Docker cleanup finished successfully!"