-- Database Initialization Script for Healthcare Agent Platform
-- This script runs automatically when PostgreSQL container starts

-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Create additional indexes for performance
-- These will be created on top of SQLAlchemy models

-- Indexes for note_drafts (high query volume)
CREATE INDEX IF NOT EXISTS idx_note_drafts_status_created
    ON note_drafts(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_note_drafts_patient_created
    ON note_drafts(patient_id, created_at DESC);

-- Indexes for appointments (scheduling queries)
CREATE INDEX IF NOT EXISTS idx_appointments_therapist_date
    ON appointments(therapist_id, scheduled_start);

CREATE INDEX IF NOT EXISTS idx_appointments_patient_date
    ON appointments(patient_intake_id, scheduled_start DESC);

CREATE INDEX IF NOT EXISTS idx_appointments_facility_status
    ON appointments(facility_id, status);

-- Indexes for claims (revenue cycle queries)
CREATE INDEX IF NOT EXISTS idx_claims_status_date
    ON claims(status, date_of_service DESC);

CREATE INDEX IF NOT EXISTS idx_claims_patient_date
    ON claims(patient_intake_id, date_of_service DESC);

CREATE INDEX IF NOT EXISTS idx_claims_payer_status
    ON claims(payer_id, status);

-- Indexes for reminders (time-based queries)
CREATE INDEX IF NOT EXISTS idx_reminders_time_status
    ON appointment_reminders(reminder_time, sent_at);

-- Full-text search indexes
CREATE INDEX IF NOT EXISTS idx_patients_name_search
    ON patient_intakes USING gin(to_tsvector('english', first_name || ' ' || last_name));

CREATE INDEX IF NOT EXISTS idx_therapists_name_search
    ON therapists USING gin(to_tsvector('english', first_name || ' ' || last_name));

-- Vector similarity index (for pgvector)
-- CREATE INDEX IF NOT EXISTS idx_case_memory_embedding
--     ON case_memory USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- Create audit log function (HIPAA compliance)
CREATE OR REPLACE FUNCTION log_data_access()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_logs (
        table_name,
        action,
        user_id,
        old_data,
        new_data,
        timestamp
    ) VALUES (
        TG_TABLE_NAME,
        TG_OP,
        current_user,
        row_to_json(OLD),
        row_to_json(NEW),
        NOW()
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Performance optimization settings
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';

-- Connection pooling
ALTER SYSTEM SET max_connections = 200;

-- Reload configuration
SELECT pg_reload_conf();
