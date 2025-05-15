-- Create context_files table
CREATE TABLE context_files (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    name NVARCHAR(255) NULL,
    description NVARCHAR(MAX) NULL,
    path NVARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT GETUTCDATE(),
    modified_at DATETIME NOT NULL DEFAULT GETUTCDATE(),
    file_size BIGINT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Add index for faster lookups by user_id
CREATE INDEX idx_context_files_user_id ON context_files (user_id);
