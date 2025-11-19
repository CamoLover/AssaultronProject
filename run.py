#!/usr/bin/env python3
"""
Assaultron Project - Main Runner
Simple launcher for the Assaultron AI interface
"""

import sys
import subprocess
import os

def check_requirements():
    """Check if required packages are installed"""
    try:
        import flask
        import requests
    except ImportError as e:
        print(f"Missing required package: {e}")
        print("Installing requirements...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

def main():
    print("=" * 60)
    print("ASSAULTRON PROJECT - AI COMPANION SYSTEM")
    print("=" * 60)
    print()
    print("Initializing Assaultron interface...")
    print()
    print("REQUIREMENTS:")
    print("1. Ollama must be running on localhost:11434")
    print("   - Download from: https://ollama.ai/")
    print("   - Run: ollama serve")
    print("   - Pull model: ollama pull llama3.2:latest")
    print()
    print("2. Access the interface at: http://localhost:8080")
    print()
    
    # Check requirements
    check_requirements()
    
    # Import and run
    from main import app
    print("Starting Assaultron Control Interface...")
    print("Press Ctrl+C to stop the server")
    print()
    
    try:
        app.run(debug=True, host='127.0.0.1', port=8080)
    except KeyboardInterrupt:
        print("\n\nAssaultron system shutdown initiated...")
        print("Goodbye, Commander.")

if __name__ == "__main__":
    main()