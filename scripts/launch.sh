#!/bin/bash
# Koach OS — Quick launcher
cd "$(dirname "$0")/.."
source venv/bin/activate
streamlit run app.py
