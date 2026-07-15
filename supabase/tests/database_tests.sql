-- Database tests for Supabase

-- Test 1: Check if pgvector extension is installed
SELECT has_extension('vector') AS pgvector_installed;

-- Test 2: Check if all tables exist
SELECT 
    tablename 
FROM pg_tables 
WHERE schemaname = 'public'
AND tablename IN ('documents', 'chunks', 'conversations', 'messages', 'feedback', 'monitoring_events');

-- Test 3: Check if indexes exist
SELECT 
    indexname,
    tablename
FROM pg_indexes
WHERE schemaname = 'public'
AND indexname LIKE '%_idx';

-- Test 4: Test semantic search function
SELECT match_documents(
    '[0.1,0.2,0.3]'::vector,  -- This is a dummy embedding for testing
    5
);

-- Test 5: Check triggers
SELECT 
    trigger_name,
    event_manipulation,
    event_object_table
FROM information_schema.triggers
WHERE trigger_schema = 'public';

-- Test 6: Verify foreign key constraints
SELECT
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND tc.table_schema = 'public';
