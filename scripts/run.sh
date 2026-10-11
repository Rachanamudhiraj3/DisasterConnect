#!/bin/bash
cd "$(dirname "$0")/.."
source venv/bin/activate
echo "Starting the monitoring loop -- AUTO mode (online when available, offline otherwise)..."
python main.py --mode auto
