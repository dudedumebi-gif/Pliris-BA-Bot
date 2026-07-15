-- Seed data for development and testing

-- Insert sample documents
INSERT INTO documents (title, source, type, status, tags, metadata) VALUES
    ('Annual Report 2024', 'Finance Department', 'report', 'indexed', ARRAY['finance', 'annual', '2024'], '{"year": 2024, "category": "financial"}'),
    ('Employee Handbook 2024', 'HR Department', 'policy', 'indexed', ARRAY['hr', 'policy', '2024'], '{"year": 2024, "category": "hr"}'),
    ('Strategic Plan 2025', 'Executive Team', 'strategy', 'indexed', ARRAY['strategy', '2025', 'planning'], '{"year": 2025, "category": "strategy"}'),
    ('Q1 2024 Financial Results', 'Finance Department', 'report', 'indexed', ARRAY['finance', 'quarterly', '2024'], '{"year": 2024, "quarter": 1, "category": "financial"}')
ON CONFLICT DO NOTHING;

-- Insert sample conversation
INSERT INTO conversations (user_id, title) VALUES
    ('demo_user', 'Sample Conversation about Financial Results')
ON CONFLICT DO NOTHING;

-- Insert sample messages
INSERT INTO messages (conversation_id, role, content, metadata) VALUES
    (
        (SELECT id FROM conversations WHERE user_id = 'demo_user' LIMIT 1),
        'user',
        'What were the Q1 2024 revenue figures?',
        '{}'
    ),
    (
        (SELECT id FROM conversations WHERE user_id = 'demo_user' LIMIT 1),
        'assistant',
        'According to the Q1 2024 Financial Results, the total revenue for Q1 2024 was $125.3 million, representing a 15% increase year-over-year.',
        '{"citations": [{"source": "Q1 2024 Financial Results", "page": 5}], "confidence": 0.92}'
    )
ON CONFLICT DO NOTHING;

-- Insert sample feedback
INSERT INTO feedback (conversation_id, message_id, user_id, rating, helpful, categories, comments)
SELECT
    (SELECT id FROM conversations WHERE user_id = 'demo_user' LIMIT 1),
    (SELECT id FROM messages WHERE role = 'assistant' LIMIT 1),
    'demo_user',
    5,
    'Yes',
    ARRAY['accuracy', 'completeness'],
    'Very helpful response with good citations'
ON CONFLICT DO NOTHING;
