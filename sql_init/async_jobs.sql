-- Create the async_jobs table for job tracking
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[async_jobs]') AND type in (N'U'))
BEGIN
    CREATE TABLE [dbo].[async_jobs] (
        [id] UNIQUEIDENTIFIER PRIMARY KEY,
        [user_id] UNIQUEIDENTIFIER NOT NULL,
        [file_id] UNIQUEIDENTIFIER NULL,
        [status] VARCHAR(20) NOT NULL, -- 'pending', 'processing', 'completed', 'failed'
        [created_at] DATETIME2 NOT NULL,
        [started_at] DATETIME2 NULL,
        [completed_at] DATETIME2 NULL,
        [error_message] NVARCHAR(MAX) NULL,
        [job_type] VARCHAR(50) NOT NULL, -- 'stt', 'stt_diarize', etc.
        [result_data] NVARCHAR(MAX) NULL, -- JSON string with results
        [endpoint_id] UNIQUEIDENTIFIER NULL, -- Reference to the endpoint
        [parameters] NVARCHAR(MAX) NULL -- JSON string with input parameters
    );
    
    PRINT 'Created table: async_jobs';
END
ELSE
BEGIN
    PRINT 'Table async_jobs already exists';
END

-- Create index on user_id for faster job listing
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_async_jobs_user_id' AND object_id = OBJECT_ID('async_jobs'))
BEGIN
    CREATE INDEX IX_async_jobs_user_id ON async_jobs (user_id);
    PRINT 'Created index: IX_async_jobs_user_id';
END

-- Create index on status for faster job processing
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_async_jobs_status' AND object_id = OBJECT_ID('async_jobs'))
BEGIN
    CREATE INDEX IX_async_jobs_status ON async_jobs (status);
    PRINT 'Created index: IX_async_jobs_status';
END

-- Create index on job_type for job filtering
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_async_jobs_job_type' AND object_id = OBJECT_ID('async_jobs'))
BEGIN
    CREATE INDEX IX_async_jobs_job_type ON async_jobs (job_type);
    PRINT 'Created index: IX_async_jobs_job_type';
END

-- Create composite index on status and job_type for filtered job processing
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_async_jobs_status_job_type' AND object_id = OBJECT_ID('async_jobs'))
BEGIN
    CREATE INDEX IX_async_jobs_status_job_type ON async_jobs (status, job_type);
    PRINT 'Created index: IX_async_jobs_status_job_type';
END

-- Create index on created_at for time-based sorting
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_async_jobs_created_at' AND object_id = OBJECT_ID('async_jobs'))
BEGIN
    CREATE INDEX IX_async_jobs_created_at ON async_jobs (created_at);
    PRINT 'Created index: IX_async_jobs_created_at';
END

-- Add any additional related endpoints to the endpoints table if needed
-- Make sure to check if the endpoints table exists first
IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[endpoints]') AND type in (N'U'))
BEGIN
    -- Check if job management endpoints exist, add them if they don't
    IF NOT EXISTS (SELECT * FROM endpoints WHERE endpoint_path = '/jobs/status')
    BEGIN
        INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active)
        VALUES (NEWID(), '/jobs/status', 'Job Status Check', 0, 'Check the status of an asynchronous job', 1);
        PRINT 'Added endpoint: /jobs/status';
    END

    IF NOT EXISTS (SELECT * FROM endpoints WHERE endpoint_path = '/jobs/result')
    BEGIN
        INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active)
        VALUES (NEWID(), '/jobs/result', 'Job Result Retrieval', 0, 'Retrieve the result of a completed job', 1);
        PRINT 'Added endpoint: /jobs/result';
    END

    IF NOT EXISTS (SELECT * FROM endpoints WHERE endpoint_path = '/jobs')
    BEGIN
        INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active)
        VALUES (NEWID(), '/jobs', 'List Jobs', 0, 'List all jobs for the authenticated user', 1);
        PRINT 'Added endpoint: /jobs';
    END
END
ELSE
BEGIN
    PRINT 'Table endpoints does not exist, skipping endpoint registration';
END

PRINT 'Database setup for async job processing completed';
