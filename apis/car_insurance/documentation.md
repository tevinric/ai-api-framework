# Car Insurance Quotation Chatbot API

This API provides a conversational interface for collecting car insurance quote information. The chatbot guides users through a series of questions to gather all necessary information for generating an insurance quote.

## Features

- Conversational AI interface using GPT-4o
- Step-by-step guidance through the quoting process
- Data validation at each step
- Provides options for selection to the frontend
- Maintains conversation state between requests
- Off-topic detection to keep conversations focused
- Complete data extraction for quote generation

## API Endpoints

### Start/Continue Conversation

**Endpoint:** `POST /car-insurance/chat`

This endpoint handles both starting a new conversation and continuing an existing one.

**Request Headers:**
- `X-Token`: Authentication token (required)
- `Content-Type`: application/json (required)

**Request Body:**
```json
{
  "conversation_id": "unique-conversation-id",  // Optional - include to continue an existing conversation
  "user_message": "Hello, I want to insure my Toyota",  // Required
  "temperature": 0.5  // Optional - controls randomness of responses (0.0-1.0)
}
```

**Response:**
```json
{
  "conversation_id": "unique-conversation-id",
  "assistant_message": "Hi there! I'd be happy to help you get a car insurance quote for your Toyota. Can you tell me which model it is?",
  "extraction_data": {
    "make": "Toyota",
    "model": null,
    "year": null,
    // ... other collected fields
  },
  "is_off_topic": false,
  "is_quote_complete": false,
  "valid_models": ["Corolla", "Camry", "RAV4", "Fortuner", "Hilux", "Land Cruiser", "Avanza", "Yaris"],
  "next_question_options": {
    "model": ["Corolla", "Camry", "RAV4", "Fortuner", "Hilux", "Land Cruiser", "Avanza", "Yaris"]
  },
  "prompt_tokens": 521,
  "completion_tokens": 127,
  "total_tokens": 648,
  "model_used": "gpt-4o"
}
```

### Delete Conversation

**Endpoint:** `DELETE /car-insurance/chat`

Deletes a conversation from the system.

**Request Headers:**
- `X-Token`: Authentication token (required)

**Query Parameters:**
- `conversation_id`: ID of the conversation to delete (required)

**Response:**
```json
{
  "message": "Conversation deleted successfully",
  "conversation_id": "unique-conversation-id"
}
```

## Data Collection Flow

The chatbot collects information in this order:

1. **Vehicle details**
   - Make (Toyota, BMW, etc.)
   - Year (2020, 2021, etc.)
   - Model (Corolla, X5, etc.)
   - Type (Sedan, SUV, etc.)
   - Color
   - Usage (Private, Business, etc.)
   - Registration status (SA registered)
   - Financing status

2. **Coverage details**
   - Cover type (Comprehensive, Third Party, etc.)
   - Insured value preference (Market, Retail, etc.)

3. **Risk information**
   - Night parking area/suburb
   - Night parking location type
   - Night parking security
   - Day parking area/suburb
   - Day parking location type
   - Day parking security
   - Tracking device status

4. **Personal information**
   - ID number
   - Gender
   - Full name
   - Phone number
   - Email address
   - Marital status
   - Employment status
   - Regular driver status

## Frontend Integration Guide

### Best Practices

1. **Present Options**: When the API returns `next_question_options`, present these as selectable options to the user rather than requiring free-form typing.

2. **Progressive Disclosure**: Only show the current question being asked, not the entire form at once.

3. **Show Extraction Data**: Consider showing a summary of the data collected so far.

4. **Handle Off-Topic**: If `is_off_topic` is true, consider showing a gentle reminder to stay on topic.

5. **Completion Handling**: When `is_quote_complete` becomes true, show a summary and next steps.

### Example Implementation

```javascript
// Example of handling a response on the frontend
function handleResponse(response) {
  // Display the chatbot message
  displayMessage('bot', response.assistant_message);
  
  // If we have options for the next question, show them as buttons
  if (response.next_question_options) {
    const fieldName = Object.keys(response.next_question_options)[0];
    const options = response.next_question_options[fieldName];
    
    if (options && options.length > 0) {
      displayOptions(fieldName, options);
    }
  }
  
  // Update the extraction data display
  updateExtractionDataSummary(response.extraction_data);
  
  // If the quote is complete, show a completion message
  if (response.is_quote_complete) {
    showQuoteCompletionMessage();
  }
  
  // Save the conversation ID for the next message
  savedConversationId = response.conversation_id;
}
```

## Error Handling

The API may return various error codes:

- **400 Bad Request**: Missing required parameters
- **401 Unauthorized**: Invalid or expired token
- **402 Payment Required**: Insufficient API credits
- **403 Forbidden**: Access denied to the endpoint
- **404 Not Found**: Conversation ID not found
- **500 Server Error**: Unexpected server-side error

Each error response includes an error message with details.

## Notes on Data Validation

- The API validates inputs against predefined lists
- When invalid data is provided, the API suggests alternatives
- South African ID numbers are validated for format
- Email addresses and phone numbers are validated
- Multi-select fields like security options properly handle multiple values
