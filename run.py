#!/usr/bin/env python3
"""
Assaultron Project - Main Runner

Copyright (c) 2026 Evan Escabasse.
Licensed under the MIT License - see LICENSE file for details.

Simple launcher for the Assaultron AI interface
"""

import sys
import subprocess
import os
import threading
import signal
import atexit
from datetime import datetime

# ============================================
# CONFIGURATION - What to start
# ============================================
START_ASR = True            # Start ASR-7 AI interface (main.py)
START_DOCS = True           # Start documentation website
START_DISCORD_BOT = True    # Start the discord bot
START_MONITORING = True     # Start monitoring dashboard

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

    # Add src to path for imports
    import sys
    sys.path.insert(0, os.path.dirname(__file__))

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

def start_discord_bot():
    """Start the Discord Bot (Node.js)"""
    print("\n" + "="*60)
    print("STARTING DISCORD BOT")
    print("="*60)
    print("Bot will connect to Discord servers")
    print()

    discord_dir = os.path.join(os.path.dirname(__file__), 'src', 'discord')

    try:
        # Start the bot
        subprocess.run(['node', 'bot.js'], cwd=discord_dir, check=True)
    except KeyboardInterrupt:
        print("\nDiscord bot stopped")
    except Exception as e:
        print(f"\nDiscord bot error: {e}")

def start_monitoring():
    """Start the monitoring dashboard"""
    print("\n" + "="*60)
    print("STARTING MONITORING DASHBOARD")
    print("="*60)
    print("Access at: http://localhost:8081")
    print()

    from src.monitoring_dashboard import start_monitoring_dashboard
    try:
        start_monitoring_dashboard()
    except KeyboardInterrupt:
        print("\nMonitoring dashboard stopped")

def generate_shutdown_report():
    """Generate monitoring report on shutdown"""
    if START_MONITORING:
        try:
            from src.monitoring_service import get_monitoring_service
            monitoring = get_monitoring_service()

            print("\n" + "="*60)
            print("GENERATING MONITORING REPORT")
            print("="*60)
            report_path = monitoring.generate_markdown_report()
            print(f"Report saved to: {report_path}")
            print("="*60)
        except Exception as e:
            print(f"Failed to generate monitoring report: {e}")

def main():
    print("=" * 60)
    print("ASSAULTRON PROJECT - AI COMPANION SYSTEM")
    print("=" * 60)
    print()

    # Register shutdown report generator
    atexit.register(generate_shutdown_report)

    # Display what will be started
    services = []
    if START_ASR:
        services.append("ASR-7 AI Interface (http://localhost:8080)")
    if START_DOCS:
        services.append("Documentation Website (http://localhost:8000)")
    if START_DISCORD_BOT:
        services.append("Discord bot (ASR-7#8233)")
    if START_MONITORING:
        services.append("Monitoring dashboard (http://localhost:8081)")

    if not services:
        print("ERROR: No services enabled!")
        print("Please set START_ASR=True or any other services in run.py")
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

    print("Press Ctrl+C to stop all servers and generate monitoring report")
    print()

    threads = []

    try:
        # Start monitoring first (so it can track everything)
        if START_MONITORING:
            monitoring_thread = threading.Thread(target=start_monitoring, daemon=True)
            monitoring_thread.start()
            threads.append(monitoring_thread)

        # Start Discord bot if enabled
        if START_DISCORD_BOT:
            discord_thread = threading.Thread(target=start_discord_bot, daemon=True)
            discord_thread.start()
            threads.append(discord_thread)

        # Start ASR-7 if enabled
        if START_ASR:
            # Run in thread if we're starting multiple services
            if START_DOCS or START_DISCORD_BOT or START_MONITORING:
                asr_thread = threading.Thread(target=start_asr, daemon=True)
                asr_thread.start()
                threads.append(asr_thread)
            else:
                # Run directly if only starting ASR
                start_asr()
                return

        # Start docs if enabled (blocking call)
        if START_DOCS:
            start_docs()
        else:
            # If docs is not started, keep main thread alive
            while True:
                threading.Event().wait(1)

    except KeyboardInterrupt:
        print("\n\nAssaultron system shutdown initiated...")
        print("Generating monitoring report...")
        print("Goodbye, Commander.")

if __name__ == "__main__":
    main()