import logging

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def get_monitoring_data(
    range: str = Query("Last 24 Hours", description="Time range for data"),
):
    """
    Get monitoring data including metrics, system health, and recent events.
    """
    try:
        from pliris.monitoring.events import EventLogger
        from pliris.monitoring.metrics import MetricsCollector

        metrics = MetricsCollector()
        event_logger = EventLogger()

        # Get metrics
        query_metrics = await metrics.get_query_metrics(range)
        performance_metrics = await metrics.get_performance_metrics(range)
        system_health = await metrics.get_system_health()

        # Get recent events
        recent_events = await event_logger.get_recent_events(limit=50)

        return {
            "total_queries": query_metrics.get("total", 0),
            "queries_change": query_metrics.get("change", 0),
            "avg_response_time": performance_metrics.get("avg_response_time", 0),
            "response_time_change": performance_metrics.get("response_time_change", 0),
            "success_rate": performance_metrics.get("success_rate", 0),
            "success_rate_change": performance_metrics.get("success_rate_change", 0),
            "avg_confidence": performance_metrics.get("avg_confidence", 0),
            "confidence_change": performance_metrics.get("confidence_change", 0),
            "active_users": query_metrics.get("active_users", 0),
            "users_change": query_metrics.get("users_change", 0),
            "query_timeline": query_metrics.get("timeline", []),
            "response_times": performance_metrics.get("distribution", []),
            "system_health": system_health,
            "resources": {
                "cpu_usage": system_health.get("cpu", 0),
                "memory_usage": system_health.get("memory", 0),
                "disk_usage": system_health.get("disk", 0),
            },
            "errors": performance_metrics.get("errors", {}),
            "recent_events": recent_events,
        }

    except Exception as e:
        logger.error(f"Error fetching monitoring data: {e}", exc_info=True)
        return {"error": "Failed to fetch monitoring data", "details": str(e)}
