#!/bin/bash
cd "$(dirname "$0")/.."
source venv/bin/activate
echo "Starting the monitoring loop -- OFFLINE mode (forced, for testing)..."
python main.py --mode offline
