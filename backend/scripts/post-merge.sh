#!/bin/bash
set -e

# Install Python dependencies
pip install -q fastapi "uvicorn[standard]" 2>/dev/null || true

# Install Node.js dependencies for the Vite frontend
cd kingin-vite && npm install --prefer-offline 2>/dev/null
