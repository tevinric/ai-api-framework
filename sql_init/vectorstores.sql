-- SQL Schema for the vectorstores table
-- Execute this on your database

CREATE TABLE vectorstores (
    id UNIQUEIDENTIFIER PRIMARY KEY,
    user_id UNIQUEIDENTIFIER NOT NULL,
    name NVARCHAR(255) NOT NULL,
    path NVARCHAR(255) NOT NULL,
    file_count INT NOT NULL DEFAULT 0,
    document_count INT NOT NULL DEFAULT 0,
    chunk_count INT NOT NULL DEFAULT 0,
    chunk_size INT NOT NULL DEFAULT 1000,
    chunk_overlap INT NOT NULL DEFAULT 200,
    created_at DATETIME2 NOT NULL,
    last_accessed DATETIME2 NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Index for faster queries by user_id
CREATE INDEX idx_vectorstores_user_id ON vectorstores(user_id);

-- Index for faster lookup by path
CREATE INDEX idx_vectorstores_path ON vectorstores(path);
