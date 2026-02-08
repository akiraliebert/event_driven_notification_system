-- PostgreSQL initialization for notifications database
-- Executed once on first container start via docker-entrypoint-initdb.d

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Verify setup
DO $$
BEGIN
    RAISE NOTICE 'Database "notifications" initialized with uuid-ossp extension';
END
$$;
