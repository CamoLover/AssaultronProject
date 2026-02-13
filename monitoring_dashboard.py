"""
Assaultron Monitoring Dashboard
Live web interface on port 8081 for monitoring system performance
"""

from flask import Flask, render_template, jsonify, Response, request
import json
import time
from datetime import datetime
import logging
from monitoring_service import get_monitoring_service

logger = logging.getLogger('assaultron.monitoring_dashboard')

app = Flask(__name__)


@app.route('/')
def index():
    """Render the main dashboard"""
    return render_template('monitoring_dashboard.html')


@app.route('/api/stats')
def get_stats():
    """Get current statistics summary"""
    monitoring = get_monitoring_service()
    stats = monitoring.get_collector().get_stats()
    return jsonify(stats)


@app.route('/api/metrics/<metric_name>')
def get_metric_data(metric_name):
    """Get time series data for a specific metric"""
    minutes = int(request.args.get('minutes', 60))
    monitoring = get_monitoring_service()
    data = monitoring.get_collector().get_time_series_data(metric_name, minutes)
    return jsonify(data)


@app.route('/api/stream')
def stream():
    """Server-Sent Events stream for real-time updates"""
    def event_stream():
        monitoring = get_monitoring_service()
        while True:
            stats = monitoring.get_collector().get_stats()
            yield f"data: {json.dumps(stats)}\n\n"
            time.sleep(1)  # Update every second

    return Response(event_stream(), mimetype='text/event-stream')


@app.route('/api/export')
def export_metrics():
    """Export all metrics as JSON"""
    monitoring = get_monitoring_service()
    all_metrics = monitoring.get_collector().get_all_metrics()
    stats = monitoring.get_collector().get_stats()

    export_data = {
        'export_time': datetime.now().isoformat(),
        'stats': stats,
        'metrics': all_metrics
    }

    return jsonify(export_data)


def start_monitoring_dashboard(host='127.0.0.1', port=8081):
    """Start the monitoring dashboard server"""
    logger.info(f"Starting Monitoring Dashboard on http://{host}:{port}")
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == '__main__':
    start_monitoring_dashboard()
