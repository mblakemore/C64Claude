#!/usr/bin/env python3
"""
C64 llama.cpp Bridge Python Client

This script interfaces with VICE emulator through the vice_monitor.py module
to communicate with the C64 chat client and connects to DeepSeek-R1 or other
models running on llama.cpp server.

Usage:
  python c64llamacppbridge.py [HOST] [PORT]

  The host defaults to 127.0.0.1 and port defaults to 3000 if not specified.

Commands:
  - Type a message to send it to llama.cpp and C64
  - /read     - Read the outgoing message buffer from C64
  - /clear    - Clear the incoming message buffer
  - /reset    - Reset the conversation
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

# Maximum message length
MAX_MESSAGE_LENGTH = 500   # Keep at 500 characters

# Conversation history (maintain last 10 messages)
conversation_history = []
MAX_HISTORY_LENGTH = 10

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
    return result

class LlamaCppClient:
    """Python implementation of llama.cpp client"""
    def __init__(self, host: str = "127.0.0.1", port: int = 3000):
        self.base_url = f"http://{host}:{port}"
        self.max_retries = 3
        self.initial_retry_delay_ms = 1000
        self.headers = {
            "Content-Type": "application/json"
        }
        self.timeout = 60  # seconds
    
    def format_prompt(self, message: str) -> str:
        """Format the message with the appropriate tokens"""
        return f"<｜User｜>{message}<｜Assistant｜>"
    
    def send_message(self, message: str, temperature: float = 0.5) -> str:
        """Send a message to llama.cpp server and get the response"""
        prompt = self.format_prompt(message)
        
        request_data = {
            "prompt": prompt,
            "n_predict": -1,
            "temperature": temperature,
            "min_p": 0.2,
            "stream": True,
            "stop": ["</s>", "<｜User｜>"]
        }
            
        request_json = json.dumps(request_data)
        
        retry_count = 0
        delay_ms = self.initial_retry_delay_ms
        
        full_response = ""
        
        while True:
            try:
                # Create request message to use ResponseHeadersRead
                response = requests.post(
                    f"{self.base_url}/completion",
                    headers=self.headers,
                    data=request_json,
                    stream=True,
                    timeout=self.timeout
                )
                
                if not response.ok:
                    error_content = response.text
                    print(f"API Error: {response.status_code} - {error_content}")
                    
                    should_retry = (
                        response.status_code == 429 or  # Too many requests
                        response.status_code == 503     # Service unavailable
                    )
                    
                    if should_retry and retry_count < self.max_retries:
                        retry_count += 1
                        print(f"Retrying ({retry_count}/{self.max_retries}) in {delay_ms}ms...")
                        time.sleep(delay_ms / 1000)  # Convert ms to seconds
                        delay_ms *= 2  # Exponential backoff
                        continue
                    
                    raise Exception(f"llama.cpp API error: {response.status_code} - {error_content}")
                
                # Process the streaming response
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith("data: "):
                            try:
                                json_data = json.loads(line[6:])  # Skip "data: " prefix
                                if 'content' in json_data:
                                    content = json_data['content']
                                    print(content, end='', flush=True)
                                    full_response += content
                                
                                if json_data.get('stop', False):
                                    print()  # Add newline after completion
                                    return full_response
                            except json.JSONDecodeError:
                                print(f"Error parsing JSON: {line}")
                
                return full_response
            
            except Exception as ex:
                # If we've exhausted retries
                if retry_count >= self.max_retries:
                    raise Exception(f"Error communicating with llama.cpp server: {str(ex)}") from ex
                retry_count += 1
                print(f"Retrying ({retry_count}/{self.max_retries}) in {delay_ms}ms...")
                time.sleep(delay_ms / 1000)
                delay_ms *= 2

def add_message_to_history(role: str, content: str):
    """Add a message to the conversation history, maintaining the last 10 messages."""
    global conversation_history
    
    # Create a message object
    message = {
        "role": role,
        "content": content
    }
    
    # Add to history
    conversation_history.append(message)
    
    # Trim history if needed
    if len(conversation_history) > MAX_HISTORY_LENGTH:
        conversation_history = conversation_history[-MAX_HISTORY_LENGTH:]

def reset_conversation():
    """Reset the conversation history."""
    global conversation_history
    conversation_history = []
    print("Conversation has been reset.")

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

def process_user_message(message, llama_client):
    """Process a user message: send to llama.cpp and get a response."""
    global conversation_history
    
    print(f"You: {message}")
    
    # Add user message to history
    add_message_to_history("user", message)
    
    try:
        # Get response from llama.cpp server
        print("Model is thinking...")
        llama_response = llama_client.send_message(message)
        
        # Add model's response to history
        add_message_to_history("assistant", llama_response)
        
        # Print model's response
        print(f"Model: {llama_response}")
        
        # Send model's raw response to C64
        send_message_to_c64(f"{llama_response}")
        
        return llama_response
    except Exception as e:
        error_msg = f"Error communicating with llama.cpp: {e}"
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

def check_for_messages(llama_client):
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
                    
                    # Process the message with llama.cpp if it's not a command
                    if not full_message.startswith('/'):
                        process_user_message(full_message, llama_client)
                    
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
    print("\nC64 llama.cpp Chat Client Commands:")
    print("  Just type to send a message to llama.cpp and C64")
    print(f"  (Maximum message length: {MAX_MESSAGE_LENGTH} characters)")
    print("  /read     - Read any message from the C64")
    print("  /clear    - Clear the incoming message buffer")
    print("  /reset    - Reset the conversation")
    print("  /quit     - Exit the chat client")
    print("  /help     - Show this help message")
    print("\nNote: Messages are word-wrapped to fit the C64's display.")

def main():
    global running
    
    # Default host and port
    host = "127.0.0.1"
    port = 3000
    
    # Get host and port from command line if provided
    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            port = int(sys.argv[2])
        except ValueError:
            print(f"Invalid port number: {sys.argv[2]}. Using default port 3000.")
    
    llama_client = LlamaCppClient(host, port)
    
    clear_screen()
    print("C64 llama.cpp Chat Client")
    print("========================")
    print("Connecting to VICE emulator...")
    
    try:
        # Test connection
        sock = vice_monitor.get_socket()
        vice_monitor.monitor_ping()
        vice_monitor.monitor_exit()  # Properly exit after ping
        
        print("Connected!")
        print(f"Connected to llama.cpp server at {host}:{port}")
        print(f"Messages up to {MAX_MESSAGE_LENGTH} characters are supported")
        print("Maintaining last 10 messages in conversation history")
        print("Type /help for available commands")
        
        # Initialize the message status byte to 0
        sock = vice_monitor.get_socket()
        vice_monitor.write_memory(MESSAGE_STATUS_ADDR, bytes([0]))
        vice_monitor.monitor_exit()
        
        # Start background thread to check for messages
        message_thread = threading.Thread(target=check_for_messages, args=(llama_client,))
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
                process_user_message(user_input, llama_client)
                
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