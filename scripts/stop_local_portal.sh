#!/usr/bin/env zsh
set -e

lsof -ti:8001 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true

echo "LOCAL PORTAL STOPPED"
