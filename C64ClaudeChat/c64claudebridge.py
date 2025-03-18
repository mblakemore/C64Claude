def sanitize_for_c64(text):
    """Sanitize text to ensure it can be displayed on a C64.
    Removes non-ASCII characters and replaces them with approximations.
    Converts line breaks to spaces."""
    # Replace line breaks with spaces
    text = text.replace('\n', ' ').replace('\r', ' ')
    
    # Replace multiple spaces with a single space
    while '  ' in text:
        text = text.replace('  ', ' ')
    
    result = ""
    for char in text:
        # Only include ASCII characters (0-127)
        if ord(char) < 128:
            result += char
        # Replace common Unicode characters with ASCII approximations
        elif char in "''""":
            result += "'"  # Replace curly quotes with straight quotes
        elif char == "—":
            result += "-"  # Replace em dash with hyphen
        elif char == "…":
            result += "..."  # Replace ellipsis with dots
        else:
            result += "?"  # Replace any other non-ASCII with question mark
    return result#!/usr/bin/env python3
"""
C64 Claude Chat Python Client

This script interfaces with VICE emulator through the vice_monitor.py module
to communicate with the C64 chat client and connects to Claude 3.7 Sonnet API.

Usage:
  python c64_claude_client.py [YOUR_API_KEY]

  The API key can also be set via the ANTHROPIC_API_KEY environment variable.
  If set, the command-line argument is not needed.

Commands:
  - Type a message to send it to Claude and C64
  - /read     - Read the outgoing message buffer from C64
  - /clear    - Clear the incoming message buffer
  - /reset    - Reset the conversation with Claude
  - /quit     - Exit the chat client
  - /help     - Show available commands
"""

import sys
import time
import os
import threading
import requests
import json
from typing import List, Dict, Any, Optional

# Import the vice_monitor module
# Make sure vice_monitor.py is in the same directory or in your Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import vice_monitor

# Memory locations
INCOMING_MSG_ADDR = 49152  # $C000 - Where we write messages to the C64
OUTGOING_MSG_ADDR = 49408  # $C100 - Where the C64 writes outgoing messages
MESSAGE_STATUS_ADDR = 49664  # $C200 - Status byte for message chunking
                            # 0 = no message, 1 = message chunk, 2 = last chunk

# Flag to control the background thread
running = True

# Control how often we poll for messages (in seconds)
CHECK_INTERVAL = 0.5      # Check more frequently for chunks
TIMEOUT_BETWEEN_CHECKS = 0.2  # Time to wait between checks for proper exiting

# Maximum message length - increased to support longer messages
MAX_MESSAGE_LENGTH = 500   # Keep at 500 characters

# Conversation history with Claude (maintain last 10 messages)
conversation_history = []
MAX_HISTORY_LENGTH = 10

# System prompt to inform Claude about C64 constraints
DEFAULT_SYSTEM_PROMPT = """You are communicating through a Commodore 64 computer from the 1980s.
The C64 has extremely limited display capabilities.
You can mention how neat it is, but you don't need to pretent to be a C64, the user is on one.
VERY IMPORTANT: Keep ALL responses under 200 characters maximum total.
Use extremely concise language - think telegram style.
The user will see your responses on a 40-column display with only 3-4 lines visible.
Only use standard ASCII characters - no Unicode, emojis, or special symbols.
Do not use line breaks or paragraph formatting."""

class ClaudeApiClient:
    """Python implementation of Claude API client"""
    def __init__(self, api_key: str):
        self.api_base_url = "https://api.anthropic.com/v1/messages"
        self.max_retries = 3
        self.initial_retry_delay_ms = 1000
        self.headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        self.timeout = 60  # seconds
    
    def send_message(self, messages: List[Dict[str, Any]], system_prompt: Optional[str] = None, temperature: float = 0.7) -> str:
        """Send a message to Claude and get the response"""
        request_data = {
            "model": "claude-3-7-sonnet-20250219",
            "max_tokens": 1000,
            "messages": messages,
            "temperature": temperature
        }
        
        if system_prompt:
            request_data["system"] = system_prompt
            
        request_json = json.dumps(request_data)
        
        retry_count = 0
        delay_ms = self.initial_retry_delay_ms
        
        while True:
            try:
                response = requests.post(
                    self.api_base_url,
                    headers=self.headers,
                    data=request_json,
                    timeout=self.timeout
                )
                
                if not response.ok:
                    error_content = response.text
                    print(f"API Error: {response.status_code} - {error_content}")
                    
                    should_retry = (
                        response.status_code == 429 or  # Too many requests
                        response.status_code == 529 or  # Service overloaded
                        "overloaded_error" in error_content
                    )
                    
                    if should_retry and retry_count < self.max_retries:
                        retry_count += 1
                        print(f"Retrying ({retry_count}/{self.max_retries}) in {delay_ms}ms...")
                        time.sleep(delay_ms / 1000)  # Convert ms to seconds
                        delay_ms *= 2  # Exponential backoff
                        continue
                    
                    raise Exception(f"Claude API error: {response.status_code} - {error_content}")
                
                response_json = response.json()
                
                # Extract the text from the response
                response_text = ""
                for content_block in response_json.get("content", []):
                    if content_block.get("type") == "text":
                        response_text = content_block.get("text", "")
                        break
                
                return response_text
            
            except Exception as ex:
                # If we've exhausted retries or it's not a retryable error
                if retry_count >= self.max_retries or "overloaded" not in str(ex):
                    raise Exception(f"Error communicating with Claude API: {str(ex)}") from ex
                # Otherwise continue the retry loop

def add_message_to_history(role: str, content: str):
    """Add a message to the conversation history, maintaining the last 10 messages."""
    global conversation_history
    
    # Create a message object
    message = {
        "role": role,
        "content": [
            {
                "type": "text",
                "text": content
            }
        ]
    }
    
    # Add to history
    conversation_history.append(message)
    
    # Trim history if needed
    if len(conversation_history) > MAX_HISTORY_LENGTH:
        conversation_history = conversation_history[-MAX_HISTORY_LENGTH:]

def reset_conversation():
    """Reset the conversation history with Claude."""
    global conversation_history
    conversation_history = []
    print("Conversation with Claude has been reset.")

def clear_screen():
    """Clear the console screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def send_message_to_c64(message):
    """Send a message to the C64 by writing to memory at $C000."""
    # First byte is length, followed by ASCII values
    if not message:
        return
    
    # Sanitize the message for C64 compatibility
    message = sanitize_for_c64(message)
    
    # Convert message to uppercase to match C64 keyboard
    message = message.upper()
    
    # Message length check - stricter limit to ensure it works
    #if len(message) > 100:
    #    print(f"Message truncated to 100 characters (was {len(message)})")
    #    message = message[:100]
    
    try:
        # Create a fresh connection for each operation
        sock = vice_monitor.get_socket()
        
        # Prepare message bytes: length byte + ASCII values
        message_bytes = [len(message)] + [ord(c) for c in message]
        
        # Write message to memory as a single chunk
        vice_monitor.write_memory(INCOMING_MSG_ADDR, bytes(message_bytes))
        
        # Reset status and wait to ensure message is processed
        vice_monitor.write_memory(MESSAGE_STATUS_ADDR, bytes([0]))
        vice_monitor.monitor_exit()
        
        # Wait to ensure C64 processes the message
        time.sleep(1.0)
        
        print(f"Sent to C64 ({len(message)} chars): {message}")
    except Exception as e:
        print(f"Error sending message to C64: {e}")
        try:
            # Try to close the connection even if there was an error
            vice_monitor.monitor_exit()
        except:
            pass

def process_user_message(message, claude_client):
    """Process a user message: send to Claude and get a response."""
    global conversation_history
    
    print(f"You: {message}")
    
    # Add user message to history
    add_message_to_history("user", message)
    
    # Send message to C64
    # send_message_to_c64(f"YOU: {message}")
    
    try:
        # Get response from Claude
        print("Claude is thinking...")
        claude_response = claude_client.send_message(conversation_history, DEFAULT_SYSTEM_PROMPT)
        
        # Add Claude's response to history
        add_message_to_history("assistant", claude_response)
        
        # Print Claude's response
        print(f"Claude: {claude_response}")
        
        # Send Claude's raw response to C64 (without prefixing "CLAUDE:")
        send_message_to_c64(f"{claude_response}")
        
        return claude_response
    except Exception as e:
        error_msg = f"Error communicating with Claude: {e}"
        print(error_msg)
        send_message_to_c64(f"ERROR: {error_msg}")
        return None

def read_outgoing_message():
    """Read a message from the C64 from memory at $C100."""
    try:
        # Create a fresh connection
        sock = vice_monitor.get_socket()
        
        # First read just the length byte
        length_data = vice_monitor.read_memory(OUTGOING_MSG_ADDR, OUTGOING_MSG_ADDR + 1).data
        length = length_data[0]
        
        if length == 0:
            # Properly exit the monitor
            vice_monitor.monitor_exit()
            print("No message from C64")
            return None
        
        # Now read exactly the number of bytes specified by the length
        # This prevents reading garbage characters
        data = vice_monitor.read_memory(OUTGOING_MSG_ADDR + 1, 
                                      OUTGOING_MSG_ADDR + length + 1).data
            
        # Convert bytes to string (only up to the specified length)
        message = "".join(chr(b) for b in data[:length])
        
        # Clear the message buffer by writing 0 length
        vice_monitor.write_memory(OUTGOING_MSG_ADDR, bytes([0]))
        
        # Properly exit the monitor
        vice_monitor.monitor_exit()
        
        return message
    except Exception as e:
        print(f"Error reading message: {e}")
        try:
            # Try to close the connection even if there was an error
            vice_monitor.monitor_exit()
        except:
            pass
        return None

def clear_incoming_buffer():
    """Clear the incoming message buffer by writing 0 length."""
    try:
        # Create a fresh connection
        sock = vice_monitor.get_socket()
        
        # Clear buffer by writing 0 length
        vice_monitor.write_memory(INCOMING_MSG_ADDR, bytes([0]))
        
        # Properly exit the monitor
        vice_monitor.monitor_exit()
        
        print("Incoming message buffer cleared")
    except Exception as e:
        print(f"Error clearing buffer: {e}")
        try:
            # Try to close the connection even if there was an error
            vice_monitor.monitor_exit()
        except:
            pass

def check_for_messages(claude_client):
    """Background thread that periodically checks for messages from the C64.
    Includes debounce mechanism to ensure complete messages are received."""
    global running
    full_message = ""
    last_change_time = 0
    last_data_length = 0
    
    # Debounce time in seconds - wait this long after data stops changing
    DEBOUNCE_TIME = 0.5
    
    while running:
        try:
            # Create a fresh connection
            sock = vice_monitor.get_socket()
            
            # Check if there's a message at the outgoing address (just read the length byte)
            data = vice_monitor.read_memory(OUTGOING_MSG_ADDR, OUTGOING_MSG_ADDR + 1).data
            length = data[0]
            
            current_time = time.time()
            
            # If there's a new message with valid length
            if length > 0 and length <= 255:  # Max 255 per chunk from C64
                # Read status byte to determine if this is part of a multi-chunk message
                status_data = vice_monitor.read_memory(MESSAGE_STATUS_ADDR, MESSAGE_STATUS_ADDR + 1).data
                status = status_data[0]
                
                # If data length changed or status changed, reset the debounce timer
                if length != last_data_length or (status != 0 and status != 2):
                    last_change_time = current_time
                    last_data_length = length
                    
                    # Just properly exit the monitor for now - don't read data yet
                    vice_monitor.monitor_exit()
                    time.sleep(CHECK_INTERVAL)
                    continue
                
                # Check if we've waited long enough since last change
                if current_time - last_change_time < DEBOUNCE_TIME:
                    # Not enough time has passed - wait longer
                    vice_monitor.monitor_exit()
                    time.sleep(CHECK_INTERVAL)
                    continue
                
                # We've waited long enough - proceed with reading the data
                # Read exactly the number of bytes specified by the length
                data = vice_monitor.read_memory(OUTGOING_MSG_ADDR + 1, 
                                              OUTGOING_MSG_ADDR + length + 1).data
                
                # Convert to string
                chunk = "".join(chr(b) for b in data[:length])
                
                # Append to full message
                full_message += chunk
                
                # Clear the message buffer immediately
                vice_monitor.write_memory(OUTGOING_MSG_ADDR, bytes([0]))
                
                # Clear junk character
                full_message = full_message.replace('ÿ', '')
                
                # If status is 0 or 2, this is the last or only chunk
                if status == 0 or status == 2:
                    # Display the complete message
                    print(f"\nC64: {full_message}")
                    
                    # Process the message with Claude if it's not a command
                    if not full_message.startswith('/'):
                        process_user_message(full_message, claude_client)
                    
                    print("> ", end="", flush=True)  # Redisplay prompt
                    
                    # Reset full message and debounce-related variables
                    full_message = ""
                    last_data_length = 0
                    last_change_time = 0
                    
                    # Reset status byte
                    vice_monitor.write_memory(MESSAGE_STATUS_ADDR, bytes([0]))
            else:
                # Reset debounce when no message is present
                if last_data_length > 0:
                    last_data_length = 0
                    last_change_time = 0
            
            # Always properly exit the monitor
            vice_monitor.monitor_exit()
            
            # Wait before next check
            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            # If we encounter an error, try to close the connection and wait
            try:
                vice_monitor.monitor_exit()
            except:
                pass
            
            # Wait before retrying
            time.sleep(TIMEOUT_BETWEEN_CHECKS)

def show_help():
    """Display help information."""
    print("\nC64 Claude Chat Client Commands:")
    print("  Just type to send a message to Claude and C64")
    print(f"  (Maximum message length: {MAX_MESSAGE_LENGTH} characters)")
    print("  /read     - Read any message from the C64")
    print("  /clear    - Clear the incoming message buffer")
    print("  /reset    - Reset the conversation with Claude")
    print("  /quit     - Exit the chat client")
    print("  /help     - Show this help message")
    print("\nNote: Messages are word-wrapped to fit the C64's display.")

def main():
    global running
    
    # Try to get API key from environment variable first
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    # If not found in environment, try command line argument
    if not api_key and len(sys.argv) > 1:
        api_key = sys.argv[1]
    
    # If still no API key, show error and exit
    if not api_key:
        print("Please provide your Claude API key either:")
        print("1. As an environment variable: ANTHROPIC_API_KEY")
        print("2. As a command-line argument: python c64_claude_client.py YOUR_API_KEY")
        return
    
    claude_client = ClaudeApiClient(api_key)
    
    clear_screen()
    print("C64 Claude Chat Client")
    print("=====================")
    print("Connecting to VICE emulator...")
    
    try:
        # Test connection
        sock = vice_monitor.get_socket()
        vice_monitor.monitor_ping()
        vice_monitor.monitor_exit()  # Properly exit after ping
        
        print("Connected!")
        print("Connected to Claude 3.7 Sonnet API")
        print(f"Messages up to {MAX_MESSAGE_LENGTH} characters are supported")
        print("Maintaining last 10 messages in conversation history")
        print("Type /help for available commands")
        
        # Initialize the message status byte to 0
        sock = vice_monitor.get_socket()
        vice_monitor.write_memory(MESSAGE_STATUS_ADDR, bytes([0]))
        vice_monitor.monitor_exit()
        
        # Start background thread to check for messages
        message_thread = threading.Thread(target=check_for_messages, args=(claude_client,))
        message_thread.daemon = True
        message_thread.start()
        
        # Main input loop
        while True:
            user_input = input("> ")
            
            if user_input.lower() == "/quit":
                break
                
            elif user_input.lower() == "/help":
                show_help()
                
            elif user_input.lower() == "/read":
                message = read_outgoing_message()
                if message:
                    print(f"C64: {message}")
                
            elif user_input.lower() == "/clear":
                clear_incoming_buffer()
                
            elif user_input.lower() == "/reset":
                reset_conversation()
                
            else:
                process_user_message(user_input, claude_client)
                
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure VICE is running with the -binarymonitor option")
    finally:
        running = False
        print("Disconnecting...")
        # Make a best effort to send 'x' command to exit the monitor
        try:
            vice_monitor.monitor_exit()
        except:
            pass
        print("Disconnected")

if __name__ == "__main__":
    main()