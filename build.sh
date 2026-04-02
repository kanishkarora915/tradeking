#!/bin/bash
set -e

# Install Python dependencies
pip install -r backend/requirements.txt

# Build React frontend
cd frontend
npm install
npm run build
cd ..
