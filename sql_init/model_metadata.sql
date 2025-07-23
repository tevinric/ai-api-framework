-- Create model_metadata table to store LLM model information
CREATE TABLE model_metadata (
    id INT IDENTITY(1,1) PRIMARY KEY,
    modelName NVARCHAR(100) NOT NULL UNIQUE,
    modelFamily NVARCHAR(50) NOT NULL, -- e.g., 'OpenAI', 'Meta', 'Mistral'
    modelDescription NTEXT NOT NULL,
    modelCostIndicator INT NOT NULL CHECK (modelCostIndicator >= 1 AND modelCostIndicator <= 5),
    promptTokens DECIMAL(10,2) NULL, -- Cost per 1M tokens (e.g., 2.50 for $2.50/1M)
    completionTokens DECIMAL(10,2) NULL, -- Cost per 1M tokens
    cachedTokens DECIMAL(10,2) NULL, -- Cost per 1M cached tokens
    estimateCost DECIMAL(10,2) NULL, -- Estimated cost per 1M tokens
    modelInputs NVARCHAR(500) NULL, -- Comma-separated list (e.g., 'Text,Images (PNG, JPG),Context Files')
    deploymentRegions NVARCHAR(200) NULL, -- Comma-separated list (e.g., 'ZA,EU,US')
    isActive BIT DEFAULT 1, -- To enable/disable models
    supportsMultimodal BIT DEFAULT 0, -- Whether model supports images/multimodal
    supportsJsonOutput BIT DEFAULT 0, -- Whether model supports JSON output
    supportsContextFiles BIT DEFAULT 0, -- Whether model supports context files
    supportsReasoning BIT DEFAULT 0, -- Whether model supports Reasoning
    supportsTools BIT DEFAULT 0, -- Whether model supports tooling and function calling
    maxContextTokens INT NULL, -- Maximum context window size
    apiEndpoint NVARCHAR(200) NULL, -- API endpoint reference
    created_at DATETIME2 DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    modified_at DATETIME2 DEFAULT DATEADD(HOUR, 2, GETUTCDATE())
);

-- Create index for efficient lookups
CREATE INDEX IX_model_metadata_modelName ON model_metadata(modelName);
CREATE INDEX IX_model_metadata_modelFamily ON model_metadata(modelFamily);
CREATE INDEX IX_model_metadata_isActive ON model_metadata(isActive);

-- -- Insert sample data based on the models in llm.html
-- INSERT INTO model_metadata (
--     modelName, modelFamily, modelDescription, modelCostIndicator, 
--     promptTokens, completionTokens, cachedTokens, estimateCost,
--     modelInputs, deploymentRegions, supportsMultimodal, supportsJsonOutput, supportsContextFiles
-- ) VALUES 
-- -- OpenAI Models
-- ('GPT-4o', 'OpenAI', 'OpenAI''s gpt-4o is engineered for speed and efficiency. Its advanced ability to handle complex queries with minimal resources can translate into cost savings and performance.', 3, 2.50, 10.00, 1.25, 4.38, 'Text,Images (PNG, JPG),Context Files', 'ZA,EU', 1, 1, 1),

-- ('GPT-4o-mini', 'OpenAI', 'A fast, cost-effective version of GPT-4o designed for high-volume applications. Maintains strong performance across text and image understanding while offering significantly reduced costs. Ideal for chatbots, content generation, and applications requiring quick responses without compromising quality. GPT-4o mini enables a broad range of tasks with its low cost and latency, such as applications that chain or parallelize multiple model calls (e.g., calling multiple APIs), pass a large volume of context to the model (e.g., full code base or conversation history), or interact with customers through fast, real-time text responses (e.g., customer support chatbots). Today, GPT-4o mini supports text and vision in the API, with support for text, image, video and audio inputs and outputs coming in the future. The model has a context window of 128K tokens and knowledge up to October 2023. Thanks to the improved tokenizer shared with GPT-4o, handling non-English text is now even more cost effective.', 1, 0.15, 0.60, 0.075, 0.26, 'Text,Images (PNG, JPG),Context Files', 'ZA,EU', 1, 1, 1),

-- ('GPT-4.1', 'OpenAI', 'An enhanced version of GPT-4 with improved reasoning capabilities and better instruction following. Offers superior performance on complex tasks while maintaining reliability and consistency. Perfect for enterprise applications requiring high-quality text generation and analysis.', 4, NULL, NULL, NULL, NULL, 'Text,System Prompts,Structured Outputs', 'ZA,EU,US', 0, 0, 0),

-- ('GPT-4.1-mini', 'OpenAI', 'A streamlined version of GPT-4.1 optimized for speed and cost-effectiveness. Provides excellent performance for most text-based tasks while maintaining the improved reasoning capabilities of the 4.1 series. Great for production applications requiring consistent, high-quality outputs.', 1, NULL, NULL, NULL, NULL, 'Text,System Prompts,JSON Mode', 'ZA,EU,US', 0, 0, 0),

-- ('O1-mini', 'OpenAI', 'A specialized reasoning model designed for complex problem-solving tasks. Features advanced chain-of-thought capabilities and excels at mathematical problems, coding challenges, and logical reasoning. Optimized for tasks requiring deep analytical thinking and step-by-step problem decomposition.', 5, NULL, NULL, NULL, NULL, 'Text,System Prompts,Complex Problems', 'ZA,EU,US', 0, 0, 0),

-- ('O3-mini', 'OpenAI', 'Latest reasoning model with configurable thinking time and enhanced problem-solving capabilities. Features adjustable reasoning modes (high, medium, low) allowing optimization for different task complexities. Excellent for research, analysis, and applications requiring variable reasoning depth.', 4, NULL, NULL, NULL, NULL, 'Text,System Prompts,Reasoning Modes,JSON Output', 'ZA,EU,US', 0, 1, 0),

-- -- Meta Models
-- ('Llama 3.2 Vision Instruct', 'Meta', 'Meta''s multimodal Llama model with vision capabilities for image understanding and analysis. Combines powerful text generation with image comprehension, making it ideal for applications requiring both visual and textual analysis. Open-source foundation with commercial-grade performance.', 2, NULL, NULL, NULL, NULL, 'Text,Images,System Prompts', 'ZA,EU,US', 1, 0, 0),

-- ('Llama 3.1 (405B)', 'Meta', 'Meta''s largest and most capable open-source language model with 405 billion parameters. Offers exceptional performance across diverse tasks including creative writing, code generation, mathematical reasoning, and multilingual capabilities. Perfect for applications requiring high-quality, versatile AI assistance.', 3, NULL, NULL, NULL, NULL, 'Text,System Prompts,Temperature Control,JSON Output', 'ZA,EU,US', 0, 1, 0),

-- ('Llama 4 Maverick 17B', 'Meta', 'Advanced Llama 4 variant optimized for creative and unconventional problem-solving. Features enhanced reasoning capabilities with a focus on innovative approaches and out-of-the-box thinking. Ideal for creative applications, brainstorming, and tasks requiring novel solutions.', 5, NULL, NULL, NULL, NULL, 'Text,System Prompts,Creative Tasks', 'ZA,EU,US', 0, 0, 0),

-- ('Llama 4 Scout 17B', 'Meta', 'Reconnaissance-focused Llama 4 model designed for information gathering, analysis, and exploration tasks. Excels at research, data analysis, and systematic investigation of complex topics. Perfect for applications requiring thorough exploration and detailed information synthesis.', 4, NULL, NULL, NULL, NULL, 'Text,System Prompts,Research Tasks', 'ZA,EU,US', 0, 0, 0);

