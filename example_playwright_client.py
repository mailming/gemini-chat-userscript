#!/usr/bin/env python3
"""
Example client for Gemini Playwright Bridge
"""

import requests
import time

SERVER_URL = 'http://127.0.0.1:8765'


def check_health():
    """Check if server is ready"""
    try:
        response = requests.get(f'{SERVER_URL}/health', timeout=5)
        response.raise_for_status()  # Raise exception for bad status codes
        data = response.json()
        print(f"Server Status: {data.get('status', 'unknown')}")
        print(f"Browser Ready: {data.get('browser_ready', False)}")
        print(f"Pending Requests: {data.get('pending_requests', 0)}")
        return data.get('browser_ready', False)
    except requests.exceptions.RequestException as e:
        print(f"Connection Error: {e}")
        return False
    except KeyError as e:
        print(f"Missing key in response: {e}")
        print(f"Response was: {response.text if 'response' in locals() else 'No response'}")
        return False
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        if 'response' in locals():
            print(f"Response status: {response.status_code}")
            print(f"Response text: {response.text[:200]}")
        return False


def send_message(message):
    """Send a message to Gemini"""
    try:
        response = requests.post(
            f'{SERVER_URL}/v1/models/gemini-pro/generateContent',
            json={
                'contents': [{
                    'parts': [{
                        'text': message
                    }]
                }]
            },
            timeout=70
        )
        
        if response.status_code == 200:
            data = response.json()
            return data['candidates'][0]['content']['parts'][0]['text']
        else:
            error_data = response.json()
            print(f"Error: {error_data.get('error', {}).get('message', 'Unknown error')}")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    print("=" * 60)
    print("Gemini Playwright Client Example")
    print("=" * 60)
    print()
    
    # Check health
    print("Checking server health...")
    if not check_health():
        print("\n⚠️  Browser not ready. Please wait for Playwright to initialize.")
        print("Waiting 10 seconds...")
        time.sleep(10)
        
        if not check_health():
            print("❌ Browser still not ready. Exiting.")
            return
    
    print("\n✓ Server ready!\n")
    
    # Example 1: Simple question
    print("=" * 60)
    print("Example 1: Simple Question")
    print("=" * 60)
    question = "What is the capital of France?"
    print(f"Q: {question}")
    response = send_message(question)
    if response:
        print(f"A: {response}\n")
    
    # Example 2: Code generation
    print("=" * 60)
    print("Example 2: Code Generation")
    print("=" * 60)
    question = "Write a Python function to calculate fibonacci numbers"
    print(f"Q: {question}")
    response = send_message(question)
    if response:
        print(f"A: {response}\n")
    
    # Example 3: Math problem
    print("=" * 60)
    print("Example 3: Math Problem")
    print("=" * 60)
    question = "What is 15% of 240?"
    print(f"Q: {question}")
    response = send_message(question)
    if response:
        print(f"A: {response}\n")
    
    print("=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == '__main__':
    main()

