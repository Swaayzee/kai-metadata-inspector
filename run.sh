#!/bin/bash

cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Virtual environment not found."
    echo "Create it with:"
    echo "python3 -m venv venv"
    echo "source venv/bin/activate"
    echo "pip install -r requirements.txt"
    exit 1
fi

source venv/bin/activate

if ! command -v exiftool >/dev/null 2>&1; then
    echo "ExifTool is not installed."
    echo "Install it with:"
    echo "sudo apt install libimage-exiftool-perl"
    exit 1
fi

python app.py
