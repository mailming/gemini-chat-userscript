#!/usr/bin/env python3
"""
Example client for Gemini Chat API Bridge
Demonstrates how to use the API server that bridges to Gemini chat interface.
"""

import requests
import json
import time

# Server URL
BASE_URL = 'http://localhost:8765'

def check_health():
    """Check if server is running and userscript is connected"""
    try:
        response = requests.get(f'{BASE_URL}/health', timeout=5)
        data = response.json()
        print(f"Server Status: {data.get('status')}")
        print(f"Connected Clients: {data.get('connected_clients')}")
        print(f"Pending Requests: {data.get('pending_requests')}")
        return data.get('connected_clients', 0) > 0
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to server: {e}")
        print("Make sure the server is running: python server.py")
        return False

def generate_content(message, model='gemini-pro'):
    """
    Send a message to Gemini and get response
    
    Args:
        message: The message text to send
        model: Model name (default: gemini-pro)
    
    Returns:
        Response text or None if error
    """
    url = f'{BASE_URL}/v1/models/{model}/generateContent'
    
    payload = {
        'contents': [{
            'parts': [{
                'text': message
            }]
        }]
    }
    
    try:
        print(f"\nSending message: {message}")
        print("Waiting for response...")
        
        response = requests.post(url, json=payload, timeout=70)
        
        if response.status_code == 200:
            data = response.json()
            if 'candidates' in data and len(data['candidates']) > 0:
                result_text = data['candidates'][0]['content']['parts'][0]['text']
                print(f"\nResponse received:")
                print(f"{'='*60}")
                print(result_text)
                print(f"{'='*60}")
                return result_text
            else:
                print("Error: No candidates in response")
                print(f"Response: {json.dumps(data, indent=2)}")
                return None
        else:
            error_data = response.json()
            print(f"Error {response.status_code}: {error_data.get('error', {}).get('message', 'Unknown error')}")
            return None
            
    except requests.exceptions.Timeout:
        print("Error: Request timed out (60+ seconds)")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None

def main():
    """Example usage"""
    print("Gemini Chat API Bridge - Example Client")
    print("=" * 60)
    
    # Check server health
    if not check_health():
        print("\n⚠️  Warning: No userscript clients connected!")
        print("Make sure:")
        print("1. The userscript is installed in Tampermonkey/Violentmonkey")
        print("2. You have gemini.google.com open in your browser")
        print("3. The userscript is enabled")
        return
    
    # Example 1: Simple question
    print("\n" + "=" * 60)
    print("Example 1: Simple Question")
    print("=" * 60)
    generate_content("What is the capital of France?")
    
    time.sleep(2)
    
    # Example 2: Code generation
    print("\n" + "=" * 60)
    print("Example 2: Code Generation")
    print("=" * 60)
    generate_content("Write a Python function to calculate fibonacci numbers")
    
    time.sleep(2)
    
    # Example 3: Multiple requests (will be queued)
    print("\n" + "=" * 60)
    print("Example 3: Multiple Requests")
    print("=" * 60)
    
    messages = [
        "Say hello in 3 different languages",
        "What is 2+2?",
        "Name a famous scientist"
    ]
    
    for i, msg in enumerate(messages, 1):
        print(f"\n--- Request {i}/{len(messages)} ---")
        generate_content(msg)
        time.sleep(1)

if __name__ == '__main__':
    main()

