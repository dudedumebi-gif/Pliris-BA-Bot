# Monitoring Guide

## Overview

The monitoring system tracks system performance, usage metrics, and events to ensure optimal operation and identify issues early.

## Metrics

### Query Metrics

- **Total Queries**: Total number of queries processed
- **Queries per Time Period**: Query volume over time
- **Active Users**: Number of unique users
- **Query Types**: Breakdown by query category

### Performance Metrics

- **Average Response Time**: Mean time to process queries
- **Response Time Distribution**: Percentiles (p50, p90, p99)
- **Success Rate**: Percentage of successful queries
- **Error Rate**: Percentage of failed queries

### Quality Metrics

- **Average Confidence**: Mean confidence score of responses
- **Citation Rate**: Percentage of responses with citations
- **Feedback Scores**: User feedback ratings

### System Health

- **API Status**: API service health
- **Database Status**: Database connection health
- **LLM Status**: OpenAI API health
- **Embedding Status**: Embedding service health

### Resource Usage

- **CPU Utilization**: Server CPU usage
- **Memory Usage**: Server memory usage
- **Disk Usage**: Storage disk usage
- **Network I/O**: Network traffic

## Event Logging

### Event Types

#### Query Events
Logged for each user query:
- Query content
- User ID
- Conversation ID
- Timestamp

#### Response Events
Logged for each response:
- Response content (truncated)
- Query ID
- Confidence score
- Citation count
- Timestamp

#### Error Events
Logged for errors:
- Error type
- Error message
- Stack trace
- Context metadata

#### Guardrail Events
Logged for guardrail triggers:
- Guardrail type
- Trigger status
- Query context
- Timestamp

### Viewing Events

Events can be viewed:
- **Monitoring Dashboard**: In the Streamlit UI
- **Database**: Direct database queries
- **Logs**: Application log files

## Dashboard

### Accessing the Dashboard

Navigate to the **Monitoring** page in the Streamlit UI.

### Dashboard Features

#### Time Range Selector
Select time ranges:
- Last 24 Hours
- Last 7 Days
- Last 30 Days
- All Time

#### Key Metrics Display
Real-time display of:
- Total queries
- Average response time
- Success rate
- Average confidence
- Active users

#### Charts
- Query volume over time
- Response time distribution
- Error breakdown

#### System Health
- Service status indicators
- Resource usage gauges
- Recent events log

## API Endpoints

### Get Monitoring Data

```bash
GET /api/monitoring?range=Last%2024%20Hours
```

Response:
```json
{
  "total_queries": 1234,
  "avg_response_time": 2.3,
  "success_rate": 98.5,
  "avg_confidence": 0.87,
  "active_users": 45,
  "query_timeline": [...],
  "response_times": [...],
  "system_health": {...},
  "resources": {...},
  "errors": {...},
  "recent_events": [...]
}
```

### Health Check

```bash
GET /api/health
```

Response:
```json
{
  "status": "healthy",
  "checks": {
    "database": "healthy",
    "llm": "healthy",
    "supabase": "healthy"
  }
}
```

## Alerts

### Setting Up Alerts

Configure alerts for:
- High error rates (> 5%)
- Slow response times (> 5s)
- Low success rates (< 90%)
- Service failures

### Alert Channels

Consider integrating with:
- Email notifications
- Slack/webhook
- PagerDuty
- Custom webhooks

## Troubleshooting

### High Response Times

**Symptoms**: Average response time > 5s

**Possible Causes**:
- High query volume
- Large document corpus
- Slow LLM responses
- Database performance issues

**Solutions**:
- Scale horizontally
- Optimize retrieval
- Cache frequent queries
- Database indexing

### Low Success Rate

**Symptoms**: Success rate < 90%

**Possible Causes**:
- API failures
- Database errors
- LLM rate limits
- Network issues

**Solutions**:
- Check service health
- Review error logs
- Implement retries
- Add rate limiting

### Low Confidence Scores

**Symptoms**: Average confidence < 0.7

**Possible Causes**:
- Poor document quality
- Insufficient context
- Out-of-scope queries
- Weak retrieval

**Solutions**:
- Improve document quality
- Adjust chunking parameters
- Tune retrieval settings
- Add more documents

### High Error Rate

**Symptoms**: Error rate > 5%

**Possible Causes**:
- API key issues
- Database connection problems
- Invalid queries
- System overload

**Solutions**:
- Verify credentials
- Check database connectivity
- Add input validation
- Scale resources

## Performance Optimization

### Database Optimization

- Create appropriate indexes
- Use connection pooling
- Optimize queries
- Monitor query performance

### Caching

- Cache frequent queries
- Cache document embeddings
- Cache LLM responses
- Use Redis for distributed caching

### Rate Limiting

- Implement API rate limits
- Use token buckets
- Prioritize important queries
- Queue overflow traffic

### Load Balancing

- Distribute load across instances
- Use health checks
- Implement circuit breakers
- Auto-scale based on metrics

## Custom Metrics

### Adding Custom Metrics

Extend the metrics collector:

```python
from pliris.monitoring.metrics import MetricsCollector

class CustomMetrics(MetricsCollector):
    async def get_custom_metric(self, time_range: str):
        # Your custom metric calculation
        return {"custom_metric": value}
```

### Custom Events

Log custom events:

```python
from pliris.monitoring.events import EventLogger

event_logger = EventLogger()
await event_logger.log_event("custom_event_type", event_data)
```

## Integration

### External Monitoring Services

Integrate with:
- **Prometheus**: For metrics collection
- **Grafana**: For visualization
- **Datadog**: For comprehensive monitoring
- **Sentry**: For error tracking

### Example: Prometheus Integration

```python
from prometheus_client import Counter, Histogram

query_counter = Counter('queries_total', 'Total queries')
response_time = Histogram('response_time_seconds', 'Response time')

# In your code
query_counter.inc()
response_time.observe(elapsed_time)
```

## Best Practices

### Monitoring Strategy

- Monitor key metrics continuously
- Set appropriate alert thresholds
- Review metrics regularly
- Investigate anomalies promptly

### Data Retention

- Keep raw events for 30 days
- Aggregate metrics for 1 year
- Archive historical data
- Compress old logs

### Privacy

- Anonymize user data
- Mask sensitive information
- Comply with data regulations
- Secure monitoring data

### Documentation

- Document metric definitions
- Maintain runbooks for common issues
- Track configuration changes
- Document incident responses
