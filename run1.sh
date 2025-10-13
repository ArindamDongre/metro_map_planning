#!/bin/bash
if [ -z "$1" ]; then
    echo "Usage: ./run1.sh <basename>"
    exit 1
fi
python3 encoder.py "$1"
