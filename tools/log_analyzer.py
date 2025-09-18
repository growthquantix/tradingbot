"""
Log Analysis Tools for Trading System

This module provides tools for parsing, analyzing, and extracting insights
from trading system logs including performance analysis, error tracking,
and audit trail verification.
"""

import json
import re
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from collections import defaultdict, Counter
from dataclasses import dataclass
import statistics


@dataclass
class LogEntry:
    """Parsed log entry with structured data."""
    timestamp: datetime
    level: str
    logger: str
    message: str
    correlation_id: Optional[str] = None
    trading_data: Optional[Dict[str, Any]] = None
    performance_data: Optional[Dict[str, Any]] = None
    exception_data: Optional[Dict[str, Any]] = None
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class TradingMetrics:
    """Trading performance metrics from logs."""
    total_orders: int
    successful_orders: int
    failed_orders: int
    avg_order_latency_ms: float
    max_order_latency_ms: float
    min_order_latency_ms: float
    total_volume: Decimal
    symbols_traded: set
    brokers_used: set
    error_rate: float


@dataclass
class PerformanceReport:
    """System performance report from logs."""
    slow_operations: List[Dict[str, Any]]
    latency_distribution: Dict[str, int]
    error_summary: Dict[str, int]
    throughput_metrics: Dict[str, float]
    resource_usage: Dict[str, Any]


class LogParser:
    """Parser for different log formats."""

    def __init__(self):
        # Regex patterns for different log formats
        self.console_pattern = re.compile(
            r'^(\d{2}:\d{2}:\d{2}\.\d{3})\s+(\w+)\s+(\S+)\s+(.*)$'
        )

        self.old_format_pattern = re.compile(
            r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (.+?) - (\w+)\s+- (.*)$'
        )

    def parse_log_file(self, file_path: str) -> List[LogEntry]:
        """Parse log file and return structured entries."""
        entries = []

        if not os.path.exists(file_path):
            return entries

        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    entry = self.parse_line(line.strip())
                    if entry:
                        entries.append(entry)
                except Exception as e:
                    print(f"Error parsing line {line_num} in {file_path}: {e}")

        return entries

    def parse_line(self, line: str) -> Optional[LogEntry]:
        """Parse a single log line."""
        if not line.strip():
            return None

        # Try JSON format first
        if line.startswith('{'):
            return self._parse_json_line(line)

        # Try console format
        console_match = self.console_pattern.match(line)
        if console_match:
            return self._parse_console_line(console_match)

        # Try old format
        old_match = self.old_format_pattern.match(line)
        if old_match:
            return self._parse_old_format_line(old_match)

        return None

    def _parse_json_line(self, line: str) -> Optional[LogEntry]:
        """Parse JSON formatted log line."""
        try:
            data = json.loads(line)

            # Parse timestamp
            timestamp_str = data.get('@timestamp') or data.get('timestamp')
            timestamp = self._parse_timestamp(timestamp_str)

            # Extract trading data
            trading_data = data.get('trading', {})
            if not trading_data:
                # Look for trading fields in root
                trading_fields = ['user_id', 'symbol', 'order_id', 'amount', 'broker']
                trading_data = {k: data[k] for k in trading_fields if k in data}

            # Extract performance data
            performance_data = data.get('performance', {}) or data.get('metrics', {})
            if not performance_data:
                # Look for performance fields in root
                perf_fields = ['duration_ms', 'latency_ms', 'throughput']
                performance_data = {k: data[k] for k in perf_fields if k in data}

            # Extract exception data
            exception_data = data.get('exception')

            return LogEntry(
                timestamp=timestamp,
                level=data.get('level', 'INFO'),
                logger=data.get('logger', 'unknown'),
                message=data.get('message', ''),
                correlation_id=data.get('correlation_id'),
                trading_data=trading_data if trading_data else None,
                performance_data=performance_data if performance_data else None,
                exception_data=exception_data,
                raw_data=data
            )

        except json.JSONDecodeError:
            return None

    def _parse_console_line(self, match) -> LogEntry:
        """Parse console formatted log line."""
        timestamp_str, level, logger, message = match.groups()

        # Parse timestamp (HH:MM:SS.mmm format)
        now = datetime.now()
        time_parts = timestamp_str.split(':')
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        second_parts = time_parts[2].split('.')
        second = int(second_parts[0])
        microsecond = int(second_parts[1]) * 1000 if len(second_parts) > 1 else 0

        timestamp = now.replace(
            hour=hour, minute=minute, second=second, microsecond=microsecond
        )

        return LogEntry(
            timestamp=timestamp,
            level=level,
            logger=logger,
            message=message
        )

    def _parse_old_format_line(self, match) -> LogEntry:
        """Parse old format log line."""
        timestamp_str, logger, level, message = match.groups()
        timestamp = self._parse_timestamp(timestamp_str)

        return LogEntry(
            timestamp=timestamp,
            level=level,
            logger=logger,
            message=message
        )

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp string in various formats."""
        if not timestamp_str:
            return datetime.now()

        # ISO format with Z
        if timestamp_str.endswith('Z'):
            return datetime.fromisoformat(timestamp_str[:-1])

        # ISO format
        try:
            return datetime.fromisoformat(timestamp_str)
        except ValueError:
            pass

        # Standard format
        try:
            return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass

        return datetime.now()


class TradingAnalyzer:
    """Analyzer for trading-specific log data."""

    def __init__(self):
        self.parser = LogParser()

    def analyze_trading_activity(self, log_entries: List[LogEntry]) -> TradingMetrics:
        """Analyze trading activity from log entries."""
        total_orders = 0
        successful_orders = 0
        failed_orders = 0
        order_latencies = []
        total_volume = Decimal('0')
        symbols_traded = set()
        brokers_used = set()

        for entry in log_entries:
            # Count orders
            if 'order' in entry.message.lower():
                total_orders += 1

                if 'executed' in entry.message.lower() or 'successful' in entry.message.lower():
                    successful_orders += 1
                elif 'failed' in entry.message.lower() or 'rejected' in entry.message.lower():
                    failed_orders += 1

                # Extract latency
                if entry.performance_data and 'duration_ms' in entry.performance_data:
                    order_latencies.append(entry.performance_data['duration_ms'])

            # Extract trading data
            if entry.trading_data:
                if 'symbol' in entry.trading_data:
                    symbols_traded.add(entry.trading_data['symbol'])

                if 'broker' in entry.trading_data:
                    brokers_used.add(entry.trading_data['broker'])

                if 'amount' in entry.trading_data:
                    try:
                        amount = Decimal(str(entry.trading_data['amount']))
                        total_volume += amount
                    except (ValueError, TypeError):
                        pass

        # Calculate metrics
        avg_latency = statistics.mean(order_latencies) if order_latencies else 0
        max_latency = max(order_latencies) if order_latencies else 0
        min_latency = min(order_latencies) if order_latencies else 0
        error_rate = (failed_orders / total_orders * 100) if total_orders > 0 else 0

        return TradingMetrics(
            total_orders=total_orders,
            successful_orders=successful_orders,
            failed_orders=failed_orders,
            avg_order_latency_ms=avg_latency,
            max_order_latency_ms=max_latency,
            min_order_latency_ms=min_latency,
            total_volume=total_volume,
            symbols_traded=symbols_traded,
            brokers_used=brokers_used,
            error_rate=error_rate
        )

    def analyze_user_activity(self, log_entries: List[LogEntry], user_id: str) -> Dict[str, Any]:
        """Analyze activity for a specific user."""
        user_entries = [
            entry for entry in log_entries
            if entry.trading_data and entry.trading_data.get('user_id') == user_id
        ]

        activities = Counter()
        symbols = set()
        total_trades = 0
        total_volume = Decimal('0')

        for entry in user_entries:
            # Count activities
            if 'login' in entry.message.lower():
                activities['logins'] += 1
            elif 'order' in entry.message.lower():
                activities['orders'] += 1
            elif 'trade' in entry.message.lower():
                activities['trades'] += 1
                total_trades += 1

            # Extract trading info
            if entry.trading_data:
                if 'symbol' in entry.trading_data:
                    symbols.add(entry.trading_data['symbol'])

                if 'amount' in entry.trading_data:
                    try:
                        amount = Decimal(str(entry.trading_data['amount']))
                        total_volume += amount
                    except (ValueError, TypeError):
                        pass

        return {
            'user_id': user_id,
            'activities': dict(activities),
            'symbols_traded': list(symbols),
            'total_trades': total_trades,
            'total_volume': str(total_volume),
            'first_activity': min(entry.timestamp for entry in user_entries) if user_entries else None,
            'last_activity': max(entry.timestamp for entry in user_entries) if user_entries else None
        }


class PerformanceAnalyzer:
    """Analyzer for performance metrics from logs."""

    def __init__(self):
        self.parser = LogParser()

    def analyze_performance(self, log_entries: List[LogEntry]) -> PerformanceReport:
        """Analyze system performance from log entries."""
        slow_operations = []
        latency_buckets = defaultdict(int)
        error_counts = Counter()
        operation_times = defaultdict(list)

        for entry in log_entries:
            # Analyze performance data
            if entry.performance_data:
                duration = entry.performance_data.get('duration_ms', 0)
                operation = entry.performance_data.get('operation', 'unknown')

                operation_times[operation].append(duration)

                # Categorize latency
                if duration < 1:
                    latency_buckets['sub_1ms'] += 1
                elif duration < 10:
                    latency_buckets['1_10ms'] += 1
                elif duration < 100:
                    latency_buckets['10_100ms'] += 1
                elif duration < 1000:
                    latency_buckets['100ms_1s'] += 1
                else:
                    latency_buckets['over_1s'] += 1

                # Track slow operations
                if duration > 1000:  # Over 1 second
                    slow_operations.append({
                        'operation': operation,
                        'duration_ms': duration,
                        'timestamp': entry.timestamp.isoformat(),
                        'message': entry.message
                    })

            # Count errors
            if entry.level in ['ERROR', 'CRITICAL']:
                error_type = 'unknown'
                if entry.exception_data:
                    error_type = entry.exception_data.get('type', 'unknown')
                elif 'error' in entry.message.lower():
                    # Try to extract error type from message
                    words = entry.message.split()
                    for i, word in enumerate(words):
                        if 'error' in word.lower() and i > 0:
                            error_type = words[i-1]
                            break

                error_counts[error_type] += 1

        # Calculate throughput metrics
        throughput_metrics = {}
        for operation, times in operation_times.items():
            if times:
                throughput_metrics[operation] = {
                    'avg_duration_ms': statistics.mean(times),
                    'median_duration_ms': statistics.median(times),
                    'p95_duration_ms': statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times),
                    'operations_count': len(times)
                }

        return PerformanceReport(
            slow_operations=sorted(slow_operations, key=lambda x: x['duration_ms'], reverse=True)[:10],
            latency_distribution=dict(latency_buckets),
            error_summary=dict(error_counts),
            throughput_metrics=throughput_metrics,
            resource_usage={}  # Could be expanded with system metrics
        )


class LogAnalyzer:
    """Main log analyzer combining all analysis types."""

    def __init__(self, log_directory: str = 'logs'):
        self.log_directory = log_directory
        self.parser = LogParser()
        self.trading_analyzer = TradingAnalyzer()
        self.performance_analyzer = PerformanceAnalyzer()

    def analyze_all_logs(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Analyze all logs and generate comprehensive report."""
        # Load all log entries
        all_entries = []

        log_files = [
            'trading_app.log',
            'audit.log',
            'performance.log',
            'errors.log'
        ]

        for log_file in log_files:
            file_path = os.path.join(self.log_directory, log_file)
            if os.path.exists(file_path):
                entries = self.parser.parse_log_file(file_path)
                all_entries.extend(entries)

        # Filter by date range if specified
        if start_date or end_date:
            filtered_entries = []
            for entry in all_entries:
                if start_date and entry.timestamp < start_date:
                    continue
                if end_date and entry.timestamp > end_date:
                    continue
                filtered_entries.append(entry)
            all_entries = filtered_entries

        # Generate comprehensive report
        trading_metrics = self.trading_analyzer.analyze_trading_activity(all_entries)
        performance_report = self.performance_analyzer.analyze_performance(all_entries)

        # Generate summary statistics
        log_counts = Counter(entry.level for entry in all_entries)
        logger_counts = Counter(entry.logger for entry in all_entries)

        time_range = {
            'start': min(entry.timestamp for entry in all_entries) if all_entries else None,
            'end': max(entry.timestamp for entry in all_entries) if all_entries else None,
            'total_entries': len(all_entries)
        }

        return {
            'time_range': time_range,
            'log_level_distribution': dict(log_counts),
            'logger_distribution': dict(logger_counts),
            'trading_metrics': trading_metrics,
            'performance_report': performance_report
        }

    def generate_report(self, output_file: str = 'analysis_report.json') -> str:
        """Generate and save comprehensive analysis report."""
        report = self.analyze_all_logs()

        # Convert non-serializable objects
        def serialize_obj(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, Decimal):
                return str(obj)
            elif isinstance(obj, set):
                return list(obj)
            elif hasattr(obj, '__dict__'):
                return {k: serialize_obj(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, (list, tuple)):
                return [serialize_obj(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: serialize_obj(v) for k, v in obj.items()}
            return obj

        serializable_report = serialize_obj(report)

        with open(output_file, 'w') as f:
            json.dump(serializable_report, f, indent=2, default=str)

        return output_file


# CLI interface
def main():
    """Command line interface for log analysis."""
    import argparse

    parser = argparse.ArgumentParser(description='Analyze trading system logs')
    parser.add_argument('--log-dir', default='logs', help='Log directory path')
    parser.add_argument('--output', default='analysis_report.json', help='Output report file')
    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')

    args = parser.parse_args()

    # Parse dates
    start_date = datetime.fromisoformat(args.start_date) if args.start_date else None
    end_date = datetime.fromisoformat(args.end_date) if args.end_date else None

    # Run analysis
    analyzer = LogAnalyzer(args.log_dir)
    report_file = analyzer.generate_report(args.output)

    print(f"Analysis complete! Report saved to: {report_file}")

    # Print summary
    with open(report_file) as f:
        report = json.load(f)

    print("\n=== ANALYSIS SUMMARY ===")
    print(f"Time Range: {report['time_range']['start']} to {report['time_range']['end']}")
    print(f"Total Log Entries: {report['time_range']['total_entries']}")

    if 'trading_metrics' in report and isinstance(report['trading_metrics'], dict):
        tm = report['trading_metrics']
        print(f"Trading Orders: {tm.get('total_orders', 0)} (Success: {tm.get('successful_orders', 0)}, Failed: {tm.get('failed_orders', 0)})")
        print(f"Error Rate: {tm.get('error_rate', 0):.2f}%")
        print(f"Avg Order Latency: {tm.get('avg_order_latency_ms', 0):.1f}ms")

    if 'performance_report' in report and isinstance(report['performance_report'], dict):
        pr = report['performance_report']
        print(f"Slow Operations: {len(pr.get('slow_operations', []))}")
        print(f"Error Types: {len(pr.get('error_summary', {}))}")


if __name__ == '__main__':
    main()