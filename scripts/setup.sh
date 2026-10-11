#!/bin/bash
cd "$(dirname "$0")/.."
echo "Setting up the disaster alert system..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo ""
echo "Setup complete. Use ./scripts/run.sh to start (auto: online when available, offline otherwise)."
