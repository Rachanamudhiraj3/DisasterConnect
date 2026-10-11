#!/bin/bash
cd "$(dirname "$0")/.."
source venv/bin/activate
echo "Starting the local web app..."
echo "Open http://localhost:5000 in your browser once this says 'Running on'."
python -m backend.server
