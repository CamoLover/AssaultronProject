"""
Assaultron Monitoring Service
Tracks system performance, API delays, voice processing times, and generates reports
"""

import time
import threading
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Any, Optional
import statistics
import logging

logger = logging.getLogger('assaultron.monitoring')

# Export for other modules
MONITORING_ENABLED = True


class MetricsCollector:
    """Collects and stores performance metrics"""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.start_time = datetime.now()
        self.metrics = {
            'api_responses': deque(maxlen=max_history),
            'voice_processing': deque(maxlen=max_history),
            'llm_requests': deque(maxlen=max_history),
            'system_delays': deque(maxlen=max_history),
            'message_pipeline': deque(maxlen=max_history),
            'errors': deque(maxlen=max_history),
        }

        # Counters
        self.counters = {
            'total_messages': 0,
            'total_api_calls': 0,
            'total_voice_generated': 0,
            'total_errors': 0,
            'total_llm_tokens': 0,
        }

        # System status
        self.system_status = {
            'ai_active': False,
            'voice_enabled': False,
            'discord_bot_active': False,
            'current_requests': 0,
        }

        self._lock = threading.Lock()

    def record_api_response(self, endpoint: str, duration_ms: float, status_code: int):
        """Record API response time"""
        with self._lock:
            self.metrics['api_responses'].append({
                'timestamp': datetime.now().isoformat(),
                'endpoint': endpoint,
                'duration_ms': duration_ms,
                'status_code': status_code
            })
            self.counters['total_api_calls'] += 1

    def record_voice_processing(self, text_length: int, duration_ms: float, success: bool):
        """Record voice synthesis time"""
        with self._lock:
            self.metrics['voice_processing'].append({
                'timestamp': datetime.now().isoformat(),
                'text_length': text_length,
                'duration_ms': duration_ms,
                'success': success
            })
            if success:
                self.counters['total_voice_generated'] += 1

    def record_llm_request(self, model: str, prompt_tokens: int, response_tokens: int, duration_ms: float):
        """Record LLM request metrics"""
        with self._lock:
            self.metrics['llm_requests'].append({
                'timestamp': datetime.now().isoformat(),
                'model': model,
                'prompt_tokens': prompt_tokens,
                'response_tokens': response_tokens,
                'total_tokens': prompt_tokens + response_tokens,
                'duration_ms': duration_ms
            })
            self.counters['total_llm_tokens'] += (prompt_tokens + response_tokens)

    def record_system_delay(self, component: str, duration_ms: float, details: Optional[str] = None):
        """Record system delays between components"""
        with self._lock:
            self.metrics['system_delays'].append({
                'timestamp': datetime.now().isoformat(),
                'component': component,
                'duration_ms': duration_ms,
                'details': details
            })

    def record_message_pipeline(self, stage: str, duration_ms: float):
        """Record message processing pipeline timing"""
        with self._lock:
            self.metrics['message_pipeline'].append({
                'timestamp': datetime.now().isoformat(),
                'stage': stage,
                'duration_ms': duration_ms
            })
            self.counters['total_messages'] += 1

    def record_error(self, error_type: str, component: str, message: str):
        """Record errors"""
        with self._lock:
            self.metrics['errors'].append({
                'timestamp': datetime.now().isoformat(),
                'error_type': error_type,
                'component': component,
                'message': message
            })
            self.counters['total_errors'] += 1

    def update_system_status(self, **kwargs):
        """Update system status flags"""
        with self._lock:
            self.system_status.update(kwargs)

    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics summary"""
        with self._lock:
            stats = {
                'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
                'counters': self.counters.copy(),
                'system_status': self.system_status.copy(),
                'recent_metrics': {}
            }

            # Calculate recent averages (last 100 items)
            for metric_name, metric_data in self.metrics.items():
                if not metric_data:
                    continue

                recent = list(metric_data)[-100:]

                if metric_name == 'api_responses':
                    durations = [m['duration_ms'] for m in recent]
                    stats['recent_metrics']['api_avg_ms'] = statistics.mean(durations) if durations else 0
                    stats['recent_metrics']['api_max_ms'] = max(durations) if durations else 0
                    stats['recent_metrics']['api_min_ms'] = min(durations) if durations else 0

                elif metric_name == 'voice_processing':
                    durations = [m['duration_ms'] for m in recent if m['success']]
                    stats['recent_metrics']['voice_avg_ms'] = statistics.mean(durations) if durations else 0
                    stats['recent_metrics']['voice_max_ms'] = max(durations) if durations else 0

                elif metric_name == 'llm_requests':
                    durations = [m['duration_ms'] for m in recent]
                    tokens = [m['total_tokens'] for m in recent]
                    stats['recent_metrics']['llm_avg_ms'] = statistics.mean(durations) if durations else 0
                    stats['recent_metrics']['llm_avg_tokens'] = statistics.mean(tokens) if tokens else 0

            return stats

    def get_time_series_data(self, metric_name: str, minutes: int = 60) -> List[Dict]:
        """Get time series data for charting"""
        with self._lock:
            if metric_name not in self.metrics:
                return []

            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            data = list(self.metrics[metric_name])

            # Filter by time
            filtered = [
                d for d in data
                if datetime.fromisoformat(d['timestamp']) > cutoff_time
            ]

            return filtered

    def get_all_metrics(self) -> Dict[str, List]:
        """Get all metrics (for export)"""
        with self._lock:
            return {
                metric_name: list(metric_data)
                for metric_name, metric_data in self.metrics.items()
            }


class MonitoringService:
    """Main monitoring service - singleton"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.metrics_collector = MetricsCollector()
            self.initialized = True
            logger.info("Monitoring Service initialized")

    def get_collector(self) -> MetricsCollector:
        """Get the metrics collector instance"""
        return self.metrics_collector

    def generate_markdown_report(self, output_path: str = None):
        """Generate a comprehensive markdown report"""
        # Default to /report directory with timestamp
        if output_path is None:
            os.makedirs('report', exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"report/monitoring_report_{timestamp}.md"

        stats = self.metrics_collector.get_stats()
        all_metrics = self.metrics_collector.get_all_metrics()

        report_lines = [
            "# Assaultron Monitoring Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Session Duration:** {timedelta(seconds=int(stats['uptime_seconds']))}",
            "",
            "## System Status",
            "",
            f"- AI Active: {'✅' if stats['system_status']['ai_active'] else '❌'}",
            f"- Voice Enabled: {'✅' if stats['system_status']['voice_enabled'] else '❌'}",
            f"- Discord Bot: {'✅' if stats['system_status']['discord_bot_active'] else '❌'}",
            "",
            "## Summary Statistics",
            "",
            f"- **Total Messages:** {stats['counters']['total_messages']}",
            f"- **Total API Calls:** {stats['counters']['total_api_calls']}",
            f"- **Voice Generations:** {stats['counters']['total_voice_generated']}",
            f"- **LLM Tokens Used:** {stats['counters']['total_llm_tokens']:,}",
            f"- **Total Errors:** {stats['counters']['total_errors']}",
            "",
            "## Performance Metrics",
            "",
        ]

        # API Response Times
        if 'api_avg_ms' in stats['recent_metrics']:
            report_lines.extend([
                "### API Response Times",
                "",
                f"- **Average:** {stats['recent_metrics']['api_avg_ms']:.2f}ms",
                f"- **Min:** {stats['recent_metrics']['api_min_ms']:.2f}ms",
                f"- **Max:** {stats['recent_metrics']['api_max_ms']:.2f}ms",
                "",
            ])

        # Voice Processing
        if 'voice_avg_ms' in stats['recent_metrics']:
            report_lines.extend([
                "### Voice Processing Times",
                "",
                f"- **Average:** {stats['recent_metrics']['voice_avg_ms']:.2f}ms",
                f"- **Max:** {stats['recent_metrics']['voice_max_ms']:.2f}ms",
                "",
            ])

        # LLM Performance
        if 'llm_avg_ms' in stats['recent_metrics']:
            report_lines.extend([
                "### LLM Performance",
                "",
                f"- **Average Response Time:** {stats['recent_metrics']['llm_avg_ms']:.2f}ms",
                f"- **Average Tokens/Request:** {stats['recent_metrics']['llm_avg_tokens']:.0f}",
                "",
            ])

        # Errors
        if all_metrics['errors']:
            report_lines.extend([
                "## Errors",
                "",
                "| Time | Component | Type | Message |",
                "|------|-----------|------|---------|"
            ])

            for error in list(all_metrics['errors'])[-50:]:  # Last 50 errors
                time_str = datetime.fromisoformat(error['timestamp']).strftime('%H:%M:%S')
                report_lines.append(
                    f"| {time_str} | {error['component']} | {error['error_type']} | {error['message'][:50]} |"
                )

            report_lines.append("")

        # System Delays Analysis
        if all_metrics['system_delays']:
            delays_by_component = defaultdict(list)
            for delay in all_metrics['system_delays']:
                delays_by_component[delay['component']].append(delay['duration_ms'])

            report_lines.extend([
                "## System Component Delays",
                "",
                "| Component | Avg (ms) | Max (ms) | Count |",
                "|-----------|----------|----------|-------|"
            ])

            for component, delays in delays_by_component.items():
                avg = statistics.mean(delays)
                max_delay = max(delays)
                count = len(delays)
                report_lines.append(f"| {component} | {avg:.2f} | {max_delay:.2f} | {count} |")

            report_lines.append("")

        # Recent API Calls
        if all_metrics['api_responses']:
            report_lines.extend([
                "## Recent API Calls (Last 20)",
                "",
                "| Time | Endpoint | Duration (ms) | Status |",
                "|------|----------|---------------|--------|"
            ])

            for api_call in list(all_metrics['api_responses'])[-20:]:
                time_str = datetime.fromisoformat(api_call['timestamp']).strftime('%H:%M:%S')
                report_lines.append(
                    f"| {time_str} | {api_call['endpoint']} | {api_call['duration_ms']:.2f} | {api_call['status_code']} |"
                )

            report_lines.append("")

        # Footer
        report_lines.extend([
            "---",
            "",
            "Report generated by Assaultron Monitoring Service"
        ])

        report_content = "\n".join(report_lines)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

        logger.info(f"Monitoring report generated: {output_path}")
        return output_path


# Global singleton instance
monitoring_service = MonitoringService()


def get_monitoring_service() -> MonitoringService:
    """Get the global monitoring service instance"""
    return monitoring_service
