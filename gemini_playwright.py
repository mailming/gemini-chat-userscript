#!/usr/bin/env python3
"""
Gemini Chat Playwright Bridge
Uses Playwright to control Gemini chat interface directly.
Much simpler than userscript + bypasses all CSP issues.
"""

import asyncio
import json
import uuid
import threading
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from playwright.async_api import async_playwright, Page, Browser
from datetime import datetime
from queue import Queue

app = Flask(__name__)
CORS(app)

# Request queue
request_queue = Queue()
response_dict = {}
response_lock = threading.Lock()

# Playwright browser and page
browser: Browser = None
page: Page = None
playwright_ready = False

# Request timeout
REQUEST_TIMEOUT = 60


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    try:
        browser_status = bool(playwright_ready)
        pending = request_queue.qsize()
        
        # Debug logging
        print(f"[Health Check] browser_ready={browser_status}, pending={pending}")
        
        return jsonify({
            'status': 'ok',
            'browser_ready': browser_status,
            'pending_requests': pending
        })
    except Exception as e:
        print(f"[Health Check Error] {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'browser_ready': False,
            'pending_requests': 0
        }), 500


@app.route('/debug', methods=['GET'])
def debug():
    """Debug endpoint to check page state"""
    return jsonify({
        'browser_ready': playwright_ready,
        'pending_requests': request_queue.qsize(),
        'page_exists': page is not None,
        'message': 'Check browser window and console output for details'
    })


@app.route('/v1/models/<model>/generateContent', methods=['POST'])
def generate_content(model):
    """
    Gemini API compatible endpoint
    Accepts: {contents: [{parts: [{text: "message"}]}]}
    Returns: {candidates: [{content: {parts: [{text: "response"}]}}]}
    """
    try:
        data = request.get_json()
        
        # Validate request
        if not data or 'contents' not in data:
            return jsonify({
                'error': {
                    'message': 'Invalid request format. Expected {contents: [...]}',
                    'code': 400
                }
            }), 400
        
        # Extract message
        contents = data.get('contents', [])
        if not contents or not contents[0].get('parts'):
            return jsonify({
                'error': {
                    'message': 'No message content found',
                    'code': 400
                }
            }), 400
        
        message_text = contents[0]['parts'][0].get('text', '')
        if not message_text:
            return jsonify({
                'error': {
                    'message': 'Empty message text',
                    'code': 400
                }
            }), 400
        
        # Check if browser is ready
        if not playwright_ready:
            return jsonify({
                'error': {
                    'message': 'Browser not ready. Please wait for Playwright to initialize.',
                    'code': 503
                }
            }), 503
        
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Queue the request
        request_queue.put({
            'request_id': request_id,
            'message': message_text,
            'model': model
        })
        
        print(f"[{request_id[:8]}] Queued: {message_text[:50]}...")
        
        # Wait for response
        start_time = time.time()
        while time.time() - start_time < REQUEST_TIMEOUT:
            with response_lock:
                if request_id in response_dict:
                    result = response_dict.pop(request_id)
                    
                    if 'error' in result:
                        return jsonify({
                            'error': {
                                'message': result['error'],
                                'code': 500
                            }
                        }), 500
                    
                    # Success
                    return jsonify({
                        'candidates': [{
                            'content': {
                                'parts': [{
                                    'text': result['response']
                                }]
                            }
                        }]
                    })
            
            time.sleep(0.1)
        
        # Timeout
        return jsonify({
            'error': {
                'message': f'Request timeout after {REQUEST_TIMEOUT} seconds',
                'code': 504
            }
        }), 504
        
    except Exception as e:
        return jsonify({
            'error': {
                'message': str(e),
                'code': 500
            }
        }), 500


async def find_input_box(page: Page):
    """Find the Gemini input box"""
    selectors = [
        'rich-textarea',
        'rich-textarea[placeholder*="Enter"]',
        'rich-textarea[placeholder*="enter"]',
        'textarea[placeholder*="Enter"]',
        'textarea[placeholder*="enter"]',
        'div[contenteditable="true"][role="textbox"]',
        '[contenteditable="true"]',
        'div[data-placeholder*="Enter"]',
    ]
    
    print("  Trying to find input box...")
    for i, selector in enumerate(selectors, 1):
        try:
            print(f"    [{i}/{len(selectors)}] Trying: {selector}")
            element = await page.wait_for_selector(selector, timeout=5000)
            if element:
                is_visible = await element.is_visible()
                print(f"    ✓ Found element! Visible: {is_visible}")
                if is_visible:
                    return element
                else:
                    print(f"    ✗ Element found but not visible")
        except Exception as e:
            print(f"    ✗ Not found: {str(e)[:50]}")
            continue
    
    # Try to find editable div inside rich-textarea
    try:
        print("  Trying to find editable div inside rich-textarea...")
        rich_textarea = await page.query_selector('rich-textarea')
        if rich_textarea:
            editable = await rich_textarea.query_selector('[contenteditable="true"]')
            if editable:
                is_visible = await editable.is_visible()
                print(f"    ✓ Found editable div! Visible: {is_visible}")
                if is_visible:
                    return editable
    except Exception as e:
        print(f"    ✗ Error: {str(e)[:50]}")
    
    print("  ✗ Could not find input box with any selector")
    return None


async def find_send_button(page: Page):
    """Find the send button"""
    selectors = [
        'button[aria-label*="Send"]',
        'button[aria-label*="send"]',
    ]
    
    for selector in selectors:
        try:
            element = await page.wait_for_selector(selector, timeout=2000)
            if element and await element.is_visible() and await element.is_enabled():
                return element
        except:
            continue
    
    return None


async def send_message(page: Page, message: str):
    """Send a message to Gemini and wait for response"""
    try:
        # Find input box
        input_box = await find_input_box(page)
        if not input_box:
            return None, "Could not find input box"
        
        # Get initial message count
        initial_messages = await page.query_selector_all('message-content, model-response')
        initial_count = len(initial_messages)
        
        # Click and focus the input box
        await input_box.click()
        await page.wait_for_timeout(300)
        
        # For rich-textarea, we need to find the editable div inside
        tag_name = await input_box.evaluate('el => el.tagName.toLowerCase()')
        
        if tag_name == 'rich-textarea':
            # Find the editable div inside
            editable_div = await input_box.query_selector('[contenteditable="true"]')
            if editable_div:
                await editable_div.click()
                await page.wait_for_timeout(200)
                
                # Clear existing content
                await page.keyboard.press('Control+A')
                await page.wait_for_timeout(100)
                await page.keyboard.press('Backspace')
                await page.wait_for_timeout(100)
                
                # Type message into the editable div
                await editable_div.type(message, delay=10)
            else:
                # Fallback: type into rich-textarea directly
                await input_box.type(message, delay=10)
        else:
            # Regular textarea or input
            # Clear existing content
            await page.keyboard.press('Control+A')
            await page.wait_for_timeout(100)
            await page.keyboard.press('Backspace')
            await page.wait_for_timeout(100)
            
            # Type message
            await input_box.type(message, delay=10)
        
        await page.wait_for_timeout(500)
        
        # Find and click send button
        send_button = await find_send_button(page)
        if not send_button:
            return None, "Could not find send button"
        
        await send_button.click()
        print(f"  ✓ Message sent, waiting for response...")
        
        # Wait for response (look for new message-content or model-response)
        max_wait = 60  # 60 seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            await page.wait_for_timeout(500)
            
            # Check for new messages
            current_messages = await page.query_selector_all('message-content, model-response')
            
            if len(current_messages) > initial_count:
                # New message appeared, get the last one
                last_message = current_messages[-1]
                response_text = await last_message.inner_text()
                
                if response_text and response_text.strip():
                    print(f"  ✓ Response received ({len(response_text)} chars)")
                    return response_text.strip(), None
            
            # Check if still generating
            generating = await page.query_selector('[aria-label*="Stop"]')
            if not generating:
                # Not generating anymore, check if we have a response
                await page.wait_for_timeout(1000)
                current_messages = await page.query_selector_all('message-content, model-response')
                if len(current_messages) > initial_count:
                    last_message = current_messages[-1]
                    response_text = await last_message.inner_text()
                    if response_text and response_text.strip():
                        return response_text.strip(), None
        
        return None, "Timeout waiting for response"
        
    except Exception as e:
        return None, f"Error: {str(e)}"


async def process_requests(page: Page):
    """Process requests from the queue"""
    global playwright_ready
    
    print("✓ Request processor started")
    
    while True:
        try:
            # Check if there's a request (non-blocking)
            if not request_queue.empty():
                req = request_queue.get()
                request_id = req['request_id']
                message = req['message']
                
                print(f"[{request_id[:8]}] Processing: {message[:50]}...")
                
                # Send message and get response
                response, error = await send_message(page, message)
                
                # Store result
                with response_lock:
                    if error:
                        response_dict[request_id] = {'error': error}
                        print(f"[{request_id[:8]}] Error: {error}")
                    else:
                        response_dict[request_id] = {'response': response}
                        print(f"[{request_id[:8]}] Success!")
            
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"Error in request processor: {e}")
            await asyncio.sleep(1)


async def init_browser():
    """Initialize Playwright browser"""
    global browser, page, playwright_ready
    
    print("Starting Playwright browser...")
    
    async with async_playwright() as p:
        # Launch browser (headless=False to see what's happening)
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # Create context and page
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = await context.new_page()
        
        print("Navigating to Gemini...")
        await page.goto('https://gemini.google.com/app', timeout=60000)
        
        # Wait for page to load
        print("Waiting for page to load...")
        try:
            await page.wait_for_load_state('networkidle', timeout=60000)
        except:
            print("Network idle timeout - continuing anyway...")
            await page.wait_for_timeout(3000)
        
        # Wait for input box to appear
        print("Waiting for input box...")
        print("  (This may take a while if you need to log in)")
        
        # Try multiple times with increasing delays
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            print(f"\n  Attempt {attempt}/{max_attempts}...")
            input_box = await find_input_box(page)
            
            if input_box:
                print("\n✓ Gemini page ready!")
                playwright_ready = True
                
                # Verify we can interact with it
                try:
                    await input_box.click()
                    await page.wait_for_timeout(500)
                    print("✓ Input box is interactive!")
                except Exception as e:
                    print(f"⚠ Warning: Could not interact with input box: {e}")
                
                # Start processing requests
                await process_requests(page)
                return
            
            if attempt < max_attempts:
                wait_time = 10 * attempt  # 10, 20, 30, 40 seconds
                print(f"  Waiting {wait_time} seconds before retry...")
                print(f"  (You can log in manually in the browser window)")
                await page.wait_for_timeout(wait_time * 1000)
        
        # Final attempt
        print("\n✗ Could not find input box after all attempts.")
        print("  Please check:")
        print("    1. Are you logged in to Google?")
        print("    2. Is the Gemini page fully loaded?")
        print("    3. Try refreshing the page in the browser")
        print("\n  Browser window will stay open. You can:")
        print("    - Log in manually")
        print("    - Refresh the page")
        print("    - Then restart this script")
        
        # Keep browser open for manual inspection
        print("\n  Press Ctrl+C to exit...")
        try:
            await asyncio.sleep(3600)  # Wait 1 hour
        except KeyboardInterrupt:
            print("\nExiting...")


def run_playwright():
    """Run Playwright in asyncio event loop"""
    asyncio.run(init_browser())


def run_flask():
    """Run Flask server"""
    print("Starting Flask server on http://127.0.0.1:8765")
    app.run(host='127.0.0.1', port=8765, debug=False, use_reloader=False)


if __name__ == '__main__':
    print("=" * 60)
    print("Gemini Chat Playwright Bridge")
    print("=" * 60)
    print()
    
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Give Flask time to start
    time.sleep(1)
    
    print()
    print("Server ready at: http://127.0.0.1:8765")
    print("Endpoints:")
    print("  GET  /health")
    print("  POST /v1/models/{model}/generateContent")
    print()
    
    # Run Playwright in main thread
    try:
        run_playwright()
    except KeyboardInterrupt:
        print("\nShutting down...")

