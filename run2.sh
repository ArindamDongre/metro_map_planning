#!/bin/bash
if [ -z "$1" ]; then
    echo "Usage: ./run2.sh <basename>"
    exit 1
fi
python3 decoder.py "$1"
