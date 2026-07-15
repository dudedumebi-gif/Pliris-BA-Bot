# Usage Guide

## Chat Interface

### Starting a Conversation

1. Navigate to the **Chat** page
2. Type your question in the chat input
3. Press Enter or click Send
4. View the response with citations

### Conversation Features

- **Context Awareness**: The system remembers previous messages in the conversation
- **Citations**: Responses include source document references
- **Confidence Scores**: Each response includes a confidence indicator
- **Feedback**: Provide feedback on response quality

### Example Queries

- "What were the Q1 2024 revenue figures?"
- "What is the company's remote work policy?"
- "Compare this year's performance with last year"
- "What are the main risk factors?"

## Document Management

### Viewing Documents

1. Navigate to the **Sources** page
2. View all indexed documents
3. Click on a document to see details

### Uploading Documents

1. Navigate to the **Sources** page
2. Click the **Upload New** tab
3. Select a file (PDF, DOCX, or TXT)
4. Provide metadata (title, source, type, tags)
5. Click Upload

### Supported File Types

- PDF (.pdf)
- Word Documents (.docx)
- Plain Text (.txt)

### Document Status

- **Pending**: Document uploaded, waiting for processing
- **Processing**: Currently being chunked and indexed
- **Indexed**: Document fully processed and searchable

## Feedback

### Providing Feedback

1. Navigate to the **Feedback** page
2. Select a recent conversation
3. Click the helpful/not helpful buttons
4. Optionally provide detailed feedback

### Feedback Categories

- Accuracy
- Completeness
- Clarity
- Relevance
- Citations

## Monitoring

### System Metrics

1. Navigate to the **Monitoring** page
2. View real-time metrics:
   - Total queries processed
   - Average response time
   - Success rate
   - Average confidence
   - Active users

### System Health

- API Service status
- Database connection status
- LLM service status
- Embedding service status

### Resource Usage

- CPU utilization
- Memory usage
- Disk usage

### Recent Events

View recent system events including:
- Query logs
- Error logs
- Guardrail triggers

## API Usage

### Chat Endpoint

```bash
POST /api/chat
Content-Type: application/json

{
  "message": "What were the Q1 revenue figures?",
  "conversation_id": "optional-conversation-id"
}
```

Response:
```json
{
  "response": "According to the Q1 2024 Financial Results...",
  "citations": [
    {
      "source": "Q1 2024 Financial Results",
      "title": "Quarterly Report",
      "text": "The company reported total revenue...",
      "score": 0.95
    }
  ],
  "confidence": 0.92,
  "scope": "financial",
  "conversation_id": "conv-123"
}
```

### Health Check

```bash
GET /api/health
```

### Document Upload

```bash
POST /api/sources/upload
Content-Type: multipart/form-data

file: document.pdf
title: Annual Report 2024
source: Finance Department
type: report
tags: finance,2024
```

## Best Practices

### Query Formulation

- **Be specific**: "What was the Q1 2024 revenue?" vs "What was the revenue?"
- **Use context**: Reference specific documents or time periods
- **Ask follow-ups**: Build on previous responses

### Document Management

- **Use descriptive titles**: "Q1 2024 Financial Results" vs "Report"
- **Add relevant tags**: "finance", "quarterly", "2024"
- **Organize by source**: Specify the document source/author

### Feedback

- **Provide detailed feedback**: Explain what was good or bad
- **Rate consistently**: Use the rating scale accurately
- **Report issues**: Flag incorrect or misleading responses

## Limitations

### Scope

The system is designed for business analysis questions based on indexed documents. It may not handle:
- General knowledge questions
- Real-time data
- Predictive analysis beyond document content
- Personal opinions or recommendations

### Accuracy

- Responses depend on document quality and completeness
- Citations may not cover all information in responses
- Confidence scores indicate but don't guarantee accuracy

### Performance

- Response time depends on document count and query complexity
- Large documents may take longer to process
- Concurrent queries may affect performance

## Troubleshooting

### No Results Found

- Check if documents are indexed
- Verify query terms match document content
- Try broader or different search terms

### Low Confidence Responses

- The query may be outside document scope
- Documents may not contain relevant information
- Try rephrasing the query

### Slow Response Times

- Check system monitoring for resource usage
- Consider indexing fewer documents
- Verify database performance

### Incorrect Citations

- Report feedback on the response
- Check document chunking quality
- Verify document content accuracy
