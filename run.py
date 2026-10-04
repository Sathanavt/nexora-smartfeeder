#!/usr/bin/env python3
"""
SmartFeeder EMS — Substation Server Entrypoint
Intelligent Renewable Management at Feeder Level
"""
import sys
import os

# Ensure current workspace root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app import create_app
from backend.config import Config

app = create_app(Config)

if __name__ == "__main__":
    port = Config.PORT
    print("=" * 60)
    print(" SmartFeeder EMS — Substation SCADA Console")
    print(" Intelligent Renewable Management at Feeder Level")
    print("=" * 60)
    print(f" * Server running on: http://127.0.0.1:{port}")
    print(f" * Protected route:   http://127.0.0.1:{port}/")
    print(f" * Login route:       http://127.0.0.1:{port}/login")
    print("=" * 60)
    
    app.run(host="0.0.0.0", port=port, debug=False)
