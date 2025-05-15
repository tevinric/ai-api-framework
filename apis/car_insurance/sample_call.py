"""
Example client for the Car Insurance Quotation API
"""
import requests
import json
import argparse

# Configuration (should be stored securely in production)
API_BASE_URL = "https://api-example.com"  # Replace with your actual API base URL
API_TOKEN = "your-token-here"  # Replace with your actual API token


def print_json(data):
    """Print JSON data in a pretty format"""
    print(json.dumps(data, indent=2))


def start_new_conversation(message):
    """Start a new conversation with the car insurance bot"""
    headers = {
        "X-Token": API_TOKEN,
        "Content-Type": "application/json"
    }
    
    data = {
        "user_message": message,
        "temperature": 0.5  # Default temperature
    }
    
    response = requests.post(
        f"{API_BASE_URL}/car-insurance/chat",
        headers=headers,
        json=data
    )
    
    if response.status_code == 200:
        result = response.json()
        print("\n🤖 Bot response:")
        print(result["assistant_message"])
        
        print("\n📊 Extraction data:")
        print_json(result["extraction_data"])
        
        if result["next_question_options"]:
            print("\n📋 Available options for the next question:")
            print_json(result["next_question_options"])
        
        return result["conversation_id"]
    else:
        print(f"Error: {response.status_code}")
        print_json(response.json())
        return None


def continue_conversation(conversation_id, message):
    """Continue an existing conversation with the car insurance bot"""
    headers = {
        "X-Token": API_TOKEN,
        "Content-Type": "application/json"
    }
    
    data = {
        "conversation_id": conversation_id,
        "user_message": message,
        "temperature": 0.5  # Default temperature
    }
    
    response = requests.post(
        f"{API_BASE_URL}/car-insurance/chat",
        headers=headers,
        json=data
    )
    
    if response.status_code == 200:
        result = response.json()
        print("\n🤖 Bot response:")
        print(result["assistant_message"])
        
        print("\n📊 Extraction data:")
        print_json(result["extraction_data"])
        
        if result["next_question_options"]:
            print("\n📋 Available options for the next question:")
            print_json(result["next_question_options"])
        
        if result["is_quote_complete"]:
            print("\n✅ Your quote is complete!")
        
        return result
    else:
        print(f"Error: {response.status_code}")
        print_json(response.json())
        return None


def delete_conversation(conversation_id):
    """Delete a conversation"""
    headers = {
        "X-Token": API_TOKEN
    }
    
    response = requests.delete(
        f"{API_BASE_URL}/car-insurance/chat?conversation_id={conversation_id}",
        headers=headers
    )
    
    if response.status_code == 200:
        result = response.json()
        print("Conversation deleted successfully")
        return True
    else:
        print(f"Error: {response.status_code}")
        print_json(response.json())
        return False


def interactive_session():
    """Run an interactive session with the car insurance bot"""
    print("🚗 Car Insurance Quote Bot - Interactive Session")
    print("Type 'exit' to quit the session")
    
    conversation_id = None
    
    while True:
        if not conversation_id:
            print("\nStart a new conversation:")
            message = input("> ")
            
            if message.lower() == 'exit':
                break
                
            conversation_id = start_new_conversation(message)
            if not conversation_id:
                print("Failed to start conversation. Please try again.")
                continue
        else:
            print("\nContinue conversation (or type 'new' for a new conversation, 'exit' to quit):")
            message = input("> ")
            
            if message.lower() == 'exit':
                break
                
            if message.lower() == 'new':
                # Optionally delete the old conversation
                delete_conversation(conversation_id)
                conversation_id = None
                continue
                
            result = continue_conversation(conversation_id, message)
            if not result:
                print("Failed to continue conversation. Please try again.")
                continue
                
            # If the quote is complete, ask if they want to start a new one
            if result.get("is_quote_complete", False):
                print("\nYour quote is complete! Start a new quote? (yes/no)")
                response = input("> ")
                if response.lower() in ['yes', 'y']:
                    delete_conversation(conversation_id)
                    conversation_id = None
    
    print("Session ended.")


def main():
    parser = argparse.ArgumentParser(description="Car Insurance Quote Bot Client")
    parser.add_argument('--interactive', action='store_true', help='Start an interactive session')
    
    args = parser.parse_args()
    
    if args.interactive:
        interactive_session()
    else:
        # Simple demonstration
        print("Starting demo conversation...")
        conversation_id = start_new_conversation("Hi, I'd like to get a car insurance quote for my Toyota Corolla.")
        
        if conversation_id:
            print("\nContinuing conversation...")
            continue_conversation(conversation_id, "It's a 2020 model in white color.")
            
            print("\nCleaning up...")
            delete_conversation(conversation_id)
            
        print("Demo complete.")


if __name__ == "__main__":
    main()
