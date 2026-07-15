# Rubric Mapping

## Evaluation Rubrics

This document maps evaluation criteria to measurable metrics and defines quality standards for the Pliris BA Bot system.

## Retrieval Quality Rubric

### Precision

| Score | Range | Description |
|-------|-------|-------------|
| Excellent | 0.9 - 1.0 | Nearly all retrieved documents are relevant |
| Good | 0.8 - 0.9 | Nearly all retrieved documents are relevant with minor noise |
| Satisfactory | 0.7 - 0.8 | Most retrieved documents are relevant with some noise |
| Needs Improvement | 0.5 - 0.7 | About half of retrieved documents are relevant |
| Poor | < 0.5 | Less than half of retrieved documents are relevant |

### Recall

| Score | Range | Description |
|-------|-------|-------------|
| Excellent | 0.9 - 1.0 | Nearly all relevant documents are retrieved |
| Good | 0.8 - 0.9 | Most relevant documents are retrieved |
| Satisfactory | 0.7 - 0.8 | Many relevant documents are retrieved |
| Needs Improvement | 0.5 - 0.7 | About half of relevant documents are retrieved |
| Poor | < 0.5 | Less than half of relevant documents are retrieved |

### Mean Reciprocal Rank (MRR)

| Score | Range | Description |
|-------|-------|-------------|
| Excellent | 0.8 - 1.0 | First relevant document usually in top 2 results |
| Good | 0.6 - 0.8 | First relevant document usually in top 3 results |
| Satisfactory | 0.4 - 0.6 | First relevant document usually in top 5 results |
| Needs Improvement | 0.2 - 0.4 | First relevant document often in lower rankings |
| Poor | < 0.2 | First relevant document rarely appears early |

## Response Quality Rubric

### Accuracy

| Score | Range | Description |
|-------|-------|-------------|
| Excellent | 0.9 - 1.0 | Information is completely accurate and factual |
| Good | 0.8 - 0.9 | Information is mostly accurate with minor errors |
| Satisfactory | 0.7 - 0.8 | Information is generally accurate with some errors |
| Needs Improvement | 0.5 - 0.7 | Information has significant inaccuracies |
| Poor | < 0.5 | Information is mostly inaccurate |

### Completeness

| Score | Range | Description |
|-------|-------|-------------|
| Excellent | 0.9 - 1.0 | Response covers all expected topics thoroughly |
| Good | 0.8 - 0.9 | Response covers most expected topics well |
| Satisfactory | 0.7 - 0.8 | Response covers many expected topics |
| Needs Improvement | 0.5 - 0.7 | Response covers about half of expected topics |
| Poor | < 0.5 | Response covers few or no expected topics |

### Clarity

| Score | Range | Description |
|-------|-------|-------------|
| Excellent | 0.9 - 1.0 | Response is very clear, well-structured, and easy to understand |
| Good | 0.8 - 0.9 | Response is clear and well-structured |
| Satisfactory | 0.7 - 0.8 | Response is generally clear with minor issues |
| Needs Improvement | 0.5 - 0.7 | Response has clarity issues that affect understanding |
| Poor | < 0.5 | Response is unclear and difficult to understand |

### Citation Quality

| Score | Range | Description |
|-------|-------|-------------|
| Excellent | 0.9 - 1.0 | Citations are accurate, relevant, and comprehensive |
| Good | 0.8 - 0.9 | Citations are accurate and relevant |
| Satisfactory | 0.7 - 0.8 | Citations are mostly accurate and relevant |
| Needs Improvement | 0.5 - 0.7 | Citations have accuracy or relevance issues |
| Poor | < 0.5 | Citations are inaccurate or irrelevant |

## Guardrail Effectiveness Rubric

### Scope Classification

| Score | Range | Description |
|-------|-------|-------------|
| Excellent | 0.95 - 1.0 | Nearly perfect classification accuracy |
| Good | 0.90 - 0.95 | Very high classification accuracy |
| Satisfactory | 0.85 - 0.90 | High classification accuracy |
| Needs Improvement | 0.75 - 0.85 | Moderate classification accuracy |
| Poor | < 0.75 | Low classification accuracy |

### Prompt Injection Detection

| Score | Range | Description |
|-------|-------|-------------|
| Excellent | 0.95 - 1.0 | Detects nearly all prompt injection attempts |
| Good | 0.90 - 0.95 | Detects most prompt injection attempts |
| Satisfactory | 0.85 - 0.90 | Detects many prompt injection attempts |
| Needs Improvement | 0.75 - 0.85 | Detects some prompt injection attempts |
| Poor | < 0.75 | Fails to detect most prompt injection attempts |

### Evidence Checking

| Score | Range | Description |
|-------|-------|-------------|
| Excellent | 0.9 - 1.0 | Accurately validates evidence in responses |
| Good | 0.8 - 0.9 | Mostly accurate evidence validation |
| Satisfactory | 0.7 - 0.8 | Generally accurate evidence validation |
| Needs Improvement | 0.5 - 0.7 | Inconsistent evidence validation |
| Poor | < 0.5 | Poor evidence validation |

## Performance Rubric

### Response Time

| Score | Range | Description |
|-------|-------|-------------|
| Excellent | < 2s | Very fast response time |
| Good | 2s - 3s | Fast response time |
| Satisfactory | 3s - 5s | Acceptable response time |
| Needs Improvement | 5s - 10s | Slow response time |
| Poor | > 10s | Unacceptable response time |

### System Availability

| Score | Range | Description |
|-------|-------|-------------|
| Excellent | > 99.9% | Near-perfect uptime |
| Good | 99.5% - 99.9% | High availability |
| Satisfactory | 99% - 99.5% | Good availability |
| Needs Improvement | 95% - 99% | Moderate availability |
| Poor | < 95% | Poor availability |

## Overall Quality Score

### Calculation

```
Overall Score = (0.3 × Retrieval) + (0.4 × Response) + (0.2 × Guardrails) + (0.1 × Performance)
```

Where each component is the average of its sub-metrics.

### Overall Quality Levels

| Level | Score Range | Description |
|-------|------------|-------------|
| Excellent | 0.9 - 1.0 | System performs exceptionally well across all dimensions |
| Good | 0.8 - 0.9 | System performs well with minor areas for improvement |
| Satisfactory | 0.7 - 0.8 | System performs adequately with some areas needing improvement |
| Needs Improvement | 0.6 - 0.7 | System has significant areas needing improvement |
| Poor | < 0.6 | System requires major improvements |

## Quality Gates

### Pre-Production Gate

Before deploying to production, the system must meet:
- Retrieval: ≥ 0.8
- Response Quality: ≥ 0.8
- Guardrails: ≥ 0.9
- Performance: ≥ 0.8
- Overall: ≥ 0.8

### Continuous Monitoring

In production, monitor for:
- Retrieval: ≥ 0.7
- Response Quality: ≥ 0.75
- Guardrails: ≥ 0.85
- Performance: ≥ 0.75
- Overall: ≥ 0.75

Alert if metrics fall below thresholds.

## Improvement Priorities

### High Priority

1. **Guardrail Effectiveness**: Critical for safety and security
2. **Response Accuracy**: Direct impact on user trust
3. **System Availability**: Essential for usability

### Medium Priority

1. **Retrieval Quality**: Improves response relevance
2. **Response Completeness**: Improves user satisfaction
3. **Response Time**: Improves user experience

### Low Priority

1. **Response Clarity**: Can be addressed through prompt engineering
2. **Citation Quality**: Enhancement rather than core functionality

## Benchmarking

### Industry Benchmarks

Compare against:
- RAG system performance standards
- LLM application benchmarks
- Industry-specific use cases
- Competitor systems

### Historical Benchmarks

Track against:
- Previous system versions
- Baseline measurements
- Target improvements
- SLA requirements
