-- Create file_uploads table to store uploaded file information
USE AIAPISDEV;

CREATE TABLE file_uploads (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    original_filename NVARCHAR(255) NOT NULL,
    blob_name NVARCHAR(255) NOT NULL,
    blob_url NVARCHAR(MAX) NOT NULL,
    content_type NVARCHAR(100) NOT NULL,
    file_size BIGINT NOT NULL,
    upload_date DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    last_accessed DATETIME2,
    access_count INT DEFAULT 0,
    CONSTRAINT FK_file_uploads_users FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Create index for faster lookups by user_id
CREATE INDEX IX_file_uploads_user_id ON file_uploads(user_id);