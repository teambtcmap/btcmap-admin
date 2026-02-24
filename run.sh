#!/bin/bash
source .venv/bin/activate
FLASK_DEBUG=1 python3 -c "from app import app; app.run(host='0.0.0.0', port=5001)"
