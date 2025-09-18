"""
HFT Performance Monitoring System

Comprehensive monitoring and alerting system for HFT Kafka architecture
with sub-millisecond latency tracking and performance optimization.

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import time
import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict
import json
import psutil
import os

from .config import get_hft_kafka_config, ServicePriority

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""
    service_name: str
    timestamp_ns: int
    processing_time_ns: int
    throughput_msg_per_sec: float
    queue_utilization_percent: float
    memory_usage_mb: float
    cpu_usage_percent: float
    error_count: int
    warning_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "service_name": self.service_name,
            "timestamp": self.timestamp_ns,
            "processing_time_ms": self.processing_time_ns / 1_000_000,
            "throughput_msg_per_sec": self.throughput_msg_per_sec,
            "queue_utilization_percent": self.queue_utilization_percent,
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_usage_percent": self.cpu_usage_percent,
            "error_count": self.error_count,
            "warning_count": self.warning_count
        }


@dataclass
class PerformanceThresholds:
    """Performance threshold configuration"""
    latency_warning_ns: int = 1_000_000     # 1ms warning
    latency_critical_ns: int = 5_000_000    # 5ms critical
    throughput_min_msg_per_sec: float = 100.0
    queue_utilization_warning: float = 80.0  # 80%
    queue_utilization_critical: float = 95.0 # 95%
    memory_warning_mb: float = 512.0
    memory_critical_mb: float = 1024.0
    cpu_warning_percent: float = 80.0
    cpu_critical_percent: float = 95.0
    error_rate_warning: float = 0.01        # 1%
    error_rate_critical: float = 0.05       # 5%


@dataclass
class AlertConfig:
    """Alert configuration"""
    enabled: bool = True
    email_alerts: bool = True
    slack_alerts: bool = False
    webhook_url: Optional[str] = None
    alert_cooldown_seconds: int = 300       # 5 minutes
    max_alerts_per_hour: int = 10


class HFTPerformanceMonitor:
    """
    HFT Performance Monitor
    
    Features:
    - Real-time performance tracking
    - Threshold-based alerting
    - Historical metrics storage
    - System health monitoring
    - Performance optimization recommendations
    """
    
    def __init__(self):
        self._config = get_hft_kafka_config()
        self._thresholds = PerformanceThresholds()
        self._alert_config = AlertConfig()
        
        # Metrics storage
        self._metrics_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)  # Keep last 1000 metrics per service
        )
        self._current_metrics: Dict[str, PerformanceMetrics] = {}
        
        # Alert management
        self._alert_history: deque = deque(maxlen=100)
        self._last_alert_time: Dict[str, float] = {}
        self._alert_counts: Dict[str, int] = defaultdict(int)
        
        # Monitoring state
        self._is_running = False
        self._monitoring_interval = 1.0  # 1 second
        self._registered_services: Set[str] = set()
        
        # Performance tracking
        self._system_metrics = {
            "cpu_usage": deque(maxlen=60),      # 1 minute of CPU data
            "memory_usage": deque(maxlen=60),   # 1 minute of memory data
            "disk_io": deque(maxlen=60),        # 1 minute of disk I/O
            "network_io": deque(maxlen=60)      # 1 minute of network I/O
        }
        
        logger.info("HFT Performance Monitor initialized")
    
    async def start_monitoring(self) -> None:
        """Start performance monitoring"""
        self._is_running = True
        
        try:
            # Start monitoring tasks
            tasks = [
                asyncio.create_task(self._metrics_collection_loop()),
                asyncio.create_task(self._system_monitoring_loop()),
                asyncio.create_task(self._alert_processing_loop()),
                asyncio.create_task(self._performance_analysis_loop())
            ]
            
            logger.info("✅ HFT Performance Monitor started")
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"❌ Performance monitor error: {e}")
        finally:
            self._is_running = False
    
    async def stop_monitoring(self) -> None:
        """Stop performance monitoring"""
        self._is_running = False
        logger.info("✅ HFT Performance Monitor stopped")
    
    def register_service(self, service_name: str) -> None:
        """Register a service for monitoring"""
        self._registered_services.add(service_name)
        logger.debug(f"📊 Registered service for monitoring: {service_name}")
    
    async def record_metrics(self, service_name: str, metrics_data: Dict[str, Any]) -> None:
        """Record performance metrics for a service"""
        try:
            # Create performance metrics object
            metrics = PerformanceMetrics(
                service_name=service_name,
                timestamp_ns=time.perf_counter_ns(),
                processing_time_ns=int(metrics_data.get("processing_time_ns", 0)),
                throughput_msg_per_sec=float(metrics_data.get("throughput_msg_per_sec", 0)),
                queue_utilization_percent=float(metrics_data.get("queue_utilization_percent", 0)),
                memory_usage_mb=float(metrics_data.get("memory_usage_mb", 0)),
                cpu_usage_percent=float(metrics_data.get("cpu_usage_percent", 0)),
                error_count=int(metrics_data.get("error_count", 0)),
                warning_count=int(metrics_data.get("warning_count", 0))
            )
            
            # Store metrics
            self._current_metrics[service_name] = metrics
            self._metrics_history[service_name].append(metrics)
            
            # Check for threshold violations
            await self._check_thresholds(metrics)
            
        except Exception as e:
            logger.error(f"❌ Error recording metrics for {service_name}: {e}")
    
    async def _metrics_collection_loop(self) -> None:
        """Collect metrics from registered services"""
        while self._is_running:
            try:
                # Collect metrics from HFT services
                await self._collect_service_metrics()
                await asyncio.sleep(self._monitoring_interval)
            except Exception as e:
                logger.error(f"❌ Metrics collection error: {e}")
    
    async def _collect_service_metrics(self) -> None:
        """Collect metrics from all registered services"""
        try:
            # Collect from producer
            await self._collect_producer_metrics()
            
            # Collect from memory bridge
            await self._collect_memory_bridge_metrics()
            
            # Collect from consumers
            await self._collect_consumer_metrics()
            
        except Exception as e:
            logger.error(f"❌ Service metrics collection error: {e}")
    
    async def _collect_producer_metrics(self) -> None:
        """Collect metrics from HFT Kafka producer"""
        try:
            from .producer import get_hft_producer
            
            producer = await get_hft_producer()
            stats = producer.get_performance_stats()
            
            await self.record_metrics("hft_producer", {
                "processing_time_ns": stats.get("avg_latency_ms", 0) * 1_000_000,
                "throughput_msg_per_sec": stats.get("throughput_msg_per_sec", 0),
                "error_count": stats.get("error_count", 0),
                "memory_usage_mb": stats.get("bytes_sent", 0) / (1024 * 1024)
            })
            
        except ImportError:
            pass  # HFT producer not available
        except Exception as e:
            logger.error(f"❌ Producer metrics collection error: {e}")
    
    async def _collect_memory_bridge_metrics(self) -> None:
        """Collect metrics from HFT memory bridge"""
        try:
            from .memory_bridge import get_hft_memory_bridge
            
            bridge = await get_hft_memory_bridge()
            stats = bridge.get_performance_stats()
            
            await self.record_metrics("hft_memory_bridge", {
                "processing_time_ns": stats.get("avg_processing_time_ms", 0) * 1_000_000,
                "throughput_msg_per_sec": stats.get("memory_writes_per_second", 0),
                "queue_utilization_percent": stats.get("queue_utilization_percent", 0),
                "error_count": stats.get("messages_failed", 0)
            })
            
        except ImportError:
            pass  # HFT memory bridge not available
        except Exception as e:
            logger.error(f"❌ Memory bridge metrics collection error: {e}")
    
    async def _collect_consumer_metrics(self) -> None:
        """Collect metrics from HFT consumers"""
        try:
            # This would collect from registered consumers
            # Implementation depends on consumer registry
            pass
        except Exception as e:
            logger.error(f"❌ Consumer metrics collection error: {e}")
    
    async def _system_monitoring_loop(self) -> None:
        """Monitor system-level metrics"""
        while self._is_running:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(1.0)  # Collect system metrics every second
            except Exception as e:
                logger.error(f"❌ System monitoring error: {e}")
    
    async def _collect_system_metrics(self) -> None:
        """Collect system-level performance metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)
            self._system_metrics["cpu_usage"].append({
                "timestamp": time.time(),
                "value": cpu_percent
            })
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_mb = (memory.total - memory.available) / (1024 * 1024)
            self._system_metrics["memory_usage"].append({
                "timestamp": time.time(),
                "value": memory_mb
            })
            
            # Disk I/O
            disk_io = psutil.disk_io_counters()
            if disk_io:
                self._system_metrics["disk_io"].append({
                    "timestamp": time.time(),
                    "read_bytes": disk_io.read_bytes,
                    "write_bytes": disk_io.write_bytes
                })
            
            # Network I/O
            network_io = psutil.net_io_counters()
            if network_io:
                self._system_metrics["network_io"].append({
                    "timestamp": time.time(),
                    "bytes_sent": network_io.bytes_sent,
                    "bytes_recv": network_io.bytes_recv
                })
            
        except Exception as e:
            logger.error(f"❌ System metrics collection error: {e}")
    
    async def _check_thresholds(self, metrics: PerformanceMetrics) -> None:
        """Check metrics against performance thresholds"""
        try:
            alerts = []
            
            # Check latency thresholds
            if metrics.processing_time_ns > self._thresholds.latency_critical_ns:
                alerts.append({
                    "type": "CRITICAL",
                    "category": "LATENCY",
                    "service": metrics.service_name,
                    "message": f"Critical latency: {metrics.processing_time_ns / 1_000_000:.2f}ms",
                    "value": metrics.processing_time_ns / 1_000_000,
                    "threshold": self._thresholds.latency_critical_ns / 1_000_000
                })
            elif metrics.processing_time_ns > self._thresholds.latency_warning_ns:
                alerts.append({
                    "type": "WARNING",
                    "category": "LATENCY",
                    "service": metrics.service_name,
                    "message": f"High latency: {metrics.processing_time_ns / 1_000_000:.2f}ms",
                    "value": metrics.processing_time_ns / 1_000_000,
                    "threshold": self._thresholds.latency_warning_ns / 1_000_000
                })
            
            # Check queue utilization
            if metrics.queue_utilization_percent > self._thresholds.queue_utilization_critical:
                alerts.append({
                    "type": "CRITICAL",
                    "category": "QUEUE_UTILIZATION",
                    "service": metrics.service_name,
                    "message": f"Critical queue utilization: {metrics.queue_utilization_percent:.1f}%",
                    "value": metrics.queue_utilization_percent,
                    "threshold": self._thresholds.queue_utilization_critical
                })
            elif metrics.queue_utilization_percent > self._thresholds.queue_utilization_warning:
                alerts.append({
                    "type": "WARNING",
                    "category": "QUEUE_UTILIZATION",
                    "service": metrics.service_name,
                    "message": f"High queue utilization: {metrics.queue_utilization_percent:.1f}%",
                    "value": metrics.queue_utilization_percent,
                    "threshold": self._thresholds.queue_utilization_warning
                })
            
            # Check throughput
            if metrics.throughput_msg_per_sec < self._thresholds.throughput_min_msg_per_sec:
                alerts.append({
                    "type": "WARNING",
                    "category": "THROUGHPUT",
                    "service": metrics.service_name,
                    "message": f"Low throughput: {metrics.throughput_msg_per_sec:.1f} msg/sec",
                    "value": metrics.throughput_msg_per_sec,
                    "threshold": self._thresholds.throughput_min_msg_per_sec
                })
            
            # Process alerts
            for alert in alerts:
                await self._process_alert(alert)
                
        except Exception as e:
            logger.error(f"❌ Threshold checking error: {e}")
    
    async def _process_alert(self, alert: Dict[str, Any]) -> None:
        """Process and dispatch alerts"""
        try:
            alert_key = f"{alert['service']}_{alert['category']}"
            current_time = time.time()
            
            # Check alert cooldown
            if alert_key in self._last_alert_time:
                time_since_last = current_time - self._last_alert_time[alert_key]
                if time_since_last < self._alert_config.alert_cooldown_seconds:
                    return  # Skip alert due to cooldown
            
            # Check hourly alert limit
            hour_start = current_time - 3600  # 1 hour ago
            recent_alerts = [
                a for a in self._alert_history 
                if a.get("timestamp", 0) > hour_start and a.get("service") == alert["service"]
            ]
            
            if len(recent_alerts) >= self._alert_config.max_alerts_per_hour:
                return  # Skip alert due to rate limiting
            
            # Add timestamp and dispatch alert
            alert["timestamp"] = current_time
            alert["alert_id"] = f"{alert_key}_{int(current_time)}"
            
            self._alert_history.append(alert)
            self._last_alert_time[alert_key] = current_time
            
            # Log alert
            log_level = logging.CRITICAL if alert["type"] == "CRITICAL" else logging.WARNING
            logger.log(log_level, f"🚨 HFT Alert: {alert['message']}")
            
            # Send notifications
            await self._send_alert_notifications(alert)
            
        except Exception as e:
            logger.error(f"❌ Alert processing error: {e}")
    
    async def _send_alert_notifications(self, alert: Dict[str, Any]) -> None:
        """Send alert notifications via configured channels"""
        try:
            if not self._alert_config.enabled:
                return
            
            # Email alerts
            if self._alert_config.email_alerts:
                await self._send_email_alert(alert)
            
            # Slack alerts
            if self._alert_config.slack_alerts and self._alert_config.webhook_url:
                await self._send_slack_alert(alert)
            
        except Exception as e:
            logger.error(f"❌ Alert notification error: {e}")
    
    async def _send_email_alert(self, alert: Dict[str, Any]) -> None:
        """Send email alert notification"""
        try:
            # Email notification implementation
            # This would integrate with your email service
            logger.debug(f"📧 Email alert sent: {alert['message']}")
        except Exception as e:
            logger.error(f"❌ Email alert error: {e}")
    
    async def _send_slack_alert(self, alert: Dict[str, Any]) -> None:
        """Send Slack alert notification"""
        try:
            # Slack notification implementation
            # This would use webhook or Slack API
            logger.debug(f"📱 Slack alert sent: {alert['message']}")
        except Exception as e:
            logger.error(f"❌ Slack alert error: {e}")
    
    async def _alert_processing_loop(self) -> None:
        """Process and manage alerts"""
        while self._is_running:
            try:
                await self._cleanup_old_alerts()
                await asyncio.sleep(60.0)  # Cleanup every minute
            except Exception as e:
                logger.error(f"❌ Alert processing loop error: {e}")
    
    async def _cleanup_old_alerts(self) -> None:
        """Cleanup old alerts and reset counters"""
        try:
            current_time = time.time()
            
            # Remove old alert cooldowns (older than 1 hour)
            old_alert_keys = [
                key for key, timestamp in self._last_alert_time.items()
                if current_time - timestamp > 3600
            ]
            
            for key in old_alert_keys:
                del self._last_alert_time[key]
                
        except Exception as e:
            logger.error(f"❌ Alert cleanup error: {e}")
    
    async def _performance_analysis_loop(self) -> None:
        """Analyze performance trends and provide recommendations"""
        while self._is_running:
            try:
                await self._analyze_performance_trends()
                await asyncio.sleep(300.0)  # Analyze every 5 minutes
            except Exception as e:
                logger.error(f"❌ Performance analysis error: {e}")
    
    async def _analyze_performance_trends(self) -> None:
        """Analyze performance trends and generate recommendations"""
        try:
            for service_name, metrics_history in self._metrics_history.items():
                if len(metrics_history) < 10:  # Need sufficient data
                    continue
                
                # Analyze latency trends
                recent_latencies = [
                    m.processing_time_ns for m in list(metrics_history)[-10:]
                ]
                avg_latency = sum(recent_latencies) / len(recent_latencies)
                
                # Check for degrading performance
                if len(recent_latencies) >= 5:
                    early_avg = sum(recent_latencies[:5]) / 5
                    late_avg = sum(recent_latencies[-5:]) / 5
                    
                    if late_avg > early_avg * 1.5:  # 50% increase
                        logger.warning(
                            f"📈 Performance degradation detected in {service_name}: "
                            f"latency increased from {early_avg / 1_000_000:.2f}ms "
                            f"to {late_avg / 1_000_000:.2f}ms"
                        )
                
        except Exception as e:
            logger.error(f"❌ Performance trend analysis error: {e}")
    
    def get_service_metrics(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get current metrics for a service"""
        if service_name in self._current_metrics:
            return self._current_metrics[service_name].to_dict()
        return None
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metrics"""
        return {
            service: metrics.to_dict()
            for service, metrics in self._current_metrics.items()
        }
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status"""
        try:
            total_errors = sum(m.error_count for m in self._current_metrics.values())
            total_warnings = sum(m.warning_count for m in self._current_metrics.values())
            
            # Calculate average latency across all services
            latencies = [
                m.processing_time_ns for m in self._current_metrics.values()
                if m.processing_time_ns > 0
            ]
            avg_latency_ms = (sum(latencies) / len(latencies) / 1_000_000) if latencies else 0
            
            # Determine overall health status
            health_status = "healthy"
            if total_errors > 0 or avg_latency_ms > 10:  # > 10ms average
                health_status = "critical"
            elif total_warnings > 0 or avg_latency_ms > 5:  # > 5ms average
                health_status = "warning"
            
            return {
                "status": health_status,
                "services_monitored": len(self._current_metrics),
                "total_errors": total_errors,
                "total_warnings": total_warnings,
                "avg_latency_ms": avg_latency_ms,
                "recent_alerts": len([
                    a for a in self._alert_history
                    if a.get("timestamp", 0) > time.time() - 3600  # Last hour
                ]),
                "system_cpu_percent": self._get_latest_system_metric("cpu_usage"),
                "system_memory_mb": self._get_latest_system_metric("memory_usage"),
                "uptime_seconds": time.time() - (self._system_metrics.get("start_time", time.time()))
            }
            
        except Exception as e:
            logger.error(f"❌ System health calculation error: {e}")
            return {"status": "error", "error": str(e)}
    
    def _get_latest_system_metric(self, metric_name: str) -> float:
        """Get latest value for a system metric"""
        try:
            metric_data = self._system_metrics.get(metric_name, deque())
            if metric_data:
                return metric_data[-1].get("value", 0.0)
            return 0.0
        except Exception:
            return 0.0


# Singleton instance
_hft_monitor: Optional[HFTPerformanceMonitor] = None


def get_hft_monitor() -> HFTPerformanceMonitor:
    """Get singleton HFT Performance Monitor instance"""
    global _hft_monitor
    if _hft_monitor is None:
        _hft_monitor = HFTPerformanceMonitor()
    return _hft_monitor


async def start_hft_monitoring() -> None:
    """Start HFT performance monitoring"""
    monitor = get_hft_monitor()
    await monitor.start_monitoring()


async def stop_hft_monitoring() -> None:
    """Stop HFT performance monitoring"""
    global _hft_monitor
    if _hft_monitor:
        await _hft_monitor.stop_monitoring()


# Export main classes and functions
__all__ = [
    "PerformanceMetrics",
    "PerformanceThresholds",
    "AlertConfig",
    "HFTPerformanceMonitor",
    "get_hft_monitor",
    "start_hft_monitoring",
    "stop_hft_monitoring"
]