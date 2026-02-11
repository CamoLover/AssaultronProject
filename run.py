#!/usr/bin/env python3
"""
Assaultron Project - Main Runner
Simple launcher for the Assaultron AI interface
"""

import sys
import subprocess
import os
import threading

# ============================================
# CONFIGURATION - What to start
# ============================================
START_ASR = True      # Start ASR-7 AI interface (main.py)
START_DOCS = True    # Start documentation website

def check_requirements():
    """Check if required packages are installed"""
    try:
        import flask
        import requests
    except ImportError as e:
        print(f"Missing required package: {e}")
        print("Installing requirements...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

def start_asr():
    """Start the ASR-7 AI interface"""
    print("\n" + "="*60)
    print("STARTING ASR-7 AI INTERFACE")
    print("="*60)
    print("Access at: http://localhost:8080")
    print()

    from main import app
    try:
        app.run(debug=True, host='127.0.0.1', port=8080, use_reloader=False)
    except KeyboardInterrupt:
        print("\nASR-7 interface stopped")

def start_docs():
    """Start the documentation website"""
    print("\n" + "="*60)
    print("STARTING DOCUMENTATION WEBSITE")
    print("="*60)
    print("Access at: http://localhost:8000")
    print()

    import http.server
    import socketserver

    PORT = 8000
    docs_dir = os.path.join(os.path.dirname(__file__), 'docs')

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=docs_dir, **kwargs)

    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"Serving docs at http://localhost:{PORT}")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDocs server stopped")

def main():
    print("=" * 60)
    print("ASSAULTRON PROJECT - AI COMPANION SYSTEM")
    print("=" * 60)
    print()

    # Display what will be started
    services = []
    if START_ASR:
        services.append("ASR-7 AI Interface (http://localhost:8080)")
    if START_DOCS:
        services.append("Documentation Website (http://localhost:8000)")

    if not services:
        print("ERROR: No services enabled!")
        print("Please set START_ASR=True or START_DOCS=True in run.py")
        return

    print("Starting services:")
    for i, service in enumerate(services, 1):
        print(f"  {i}. {service}")
    print()

    if START_ASR:
        print("REQUIREMENTS:")
        print("1. Ollama must be running on localhost:11434")
        print("   - Download from: https://ollama.ai/")
        print("   - Run: ollama serve")
        print("   - Pull model: ollama pull llama3.2:latest")
        print()
        check_requirements()

    print("Press Ctrl+C to stop all servers")
    print()

    threads = []

    try:
        # Start ASR-7 if enabled
        if START_ASR:
            if START_DOCS:
                # Run in thread if we're starting both
                asr_thread = threading.Thread(target=start_asr, daemon=True)
                asr_thread.start()
                threads.append(asr_thread)
            else:
                # Run directly if only starting ASR
                start_asr()
                return

        # Start docs if enabled
        if START_DOCS:
            start_docs()

    except KeyboardInterrupt:
        print("\n\nAssaultron system shutdown initiated...")
        print("Goodbye, Commander.")

if __name__ == "__main__":
    main()