#!/usr/bin/env python3
"""
Gemini Chat Userscript Server (HTTP Polling Version)
Converts Gemini chat interface into an LLM API server via userscript bridge using HTTP polling.
This version bypasses WebSocket CSP restrictions.
"""

import json
import uuid
import threading
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Allow all origins for localhost development

# Request queue: {requestId: {request_data, response_data, event, timestamp, assigned}}
request_queue = {}
request_lock = threading.Lock()

# Request timeout (seconds)
REQUEST_TIMEOUT = 60

# Last poll time to track connected clients
last_poll_time = None
poll_lock = threading.Lock()


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    with poll_lock:
        is_client_connected = last_poll_time and (time.time() - last_poll_time) < 10
    
    with request_lock:
        pending_count = len(request_queue)
    
    return jsonify({
        'status': 'ok',
        'connected_clients': 1 if is_client_connected else 0,
        'pending_requests': pending_count
    })


@app.route('/poll', methods=['GET'])
def poll():
    """
    Polling endpoint for userscript to check for pending requests
    Returns the oldest unassigned request if available
    """
    # Update last poll time
    with poll_lock:
        global last_poll_time
        last_poll_time = time.time()
    
    # Find an unassigned request
    with request_lock:
        for req_id, req_data in request_queue.items():
            if not req_data.get('assigned', False) and req_data.get('response_data') is None:
                # Mark as assigned
                req_data['assigned'] = True
                
                # Extract message from request data
                contents = req_data['request_data'].get('contents', [])
                message_text = ''
                if contents and contents[0].get('parts'):
                    message_text = contents[0]['parts'][0].get('text', '')
                
                return jsonify({
                    'request': {
                        'requestId': req_id,
                        'message': message_text,
                        'model': req_data.get('model', 'gemini-pro')
                    }
                })
    
    # No pending requests
    return jsonify({'request': None})


@app.route('/response', methods=['POST'])
def receive_response():
    """
    Endpoint for userscript to send back responses
    """
    try:
        data = request.get_json()
        request_id = data.get('requestId')
        response_text = data.get('response')
        error = data.get('error')
        
        if not request_id:
            return jsonify({'error': 'Missing requestId'}), 400
        
        with request_lock:
            if request_id in request_queue:
                if error:
                    request_queue[request_id]['error_data'] = {
                        'message': error,
                        'code': 500
                    }
                else:
                    request_queue[request_id]['response_data'] = response_text
                
                # Signal waiting thread
                request_queue[request_id]['event'].set()
                
                return jsonify({'status': 'ok'})
            else:
                return jsonify({'error': 'Unknown requestId'}), 404
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/v1/models/<model>/generateContent', methods=['POST'])
def generate_content(model):
    """
    Gemini API compatible endpoint
    Accepts: {contents: [{parts: [{text: "message"}]}]}
    Returns: {candidates: [{content: {parts: [{text: "response"}]}}]}
    """
    try:
        data = request.get_json()
        
        # Validate request format
        if not data or 'contents' not in data:
            return jsonify({
                'error': {
                    'message': 'Invalid request format. Expected {contents: [...]}',
                    'code': 400
                }
            }), 400
        
        # Extract message text
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
        
        # Check if userscript is polling (connected)
        with poll_lock:
            is_client_connected = last_poll_time and (time.time() - last_poll_time) < 10
        
        if not is_client_connected:
            return jsonify({
                'error': {
                    'message': 'No userscript client connected. Please ensure the userscript is running on gemini.google.com',
                    'code': 503
                }
            }), 503
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Create event for waiting on response
        event = threading.Event()
        
        # Store request
        with request_lock:
            request_queue[request_id] = {
                'request_data': data,
                'response_data': None,
                'event': event,
                'timestamp': datetime.now(),
                'model': model,
                'assigned': False
            }
        
        print(f"New request queued: {request_id} - {message_text[:50]}...")
        
        # Wait for response (with timeout)
        if event.wait(timeout=REQUEST_TIMEOUT):
            with request_lock:
                response_data = request_queue[request_id].get('response_data')
                error_data = request_queue[request_id].get('error_data')
                if request_id in request_queue:
                    del request_queue[request_id]
            
            if error_data:
                return jsonify(error_data), 500
            
            if response_data:
                # Format as Gemini API response
                return jsonify({
                    'candidates': [{
                        'content': {
                            'parts': [{
                                'text': response_data
                            }]
                        }
                    }]
                })
            else:
                return jsonify({
                    'error': {
                        'message': 'Empty response from userscript',
                        'code': 500
                    }
                }), 500
        else:
            # Timeout
            with request_lock:
                if request_id in request_queue:
                    del request_queue[request_id]
            
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


def cleanup_old_requests():
    """Background task to cleanup timed-out requests"""
    while True:
        time.sleep(30)  # Run every 30 seconds
        now = datetime.now()
        with request_lock:
            to_remove = []
            for req_id, req_data in request_queue.items():
                if (now - req_data['timestamp']).total_seconds() > REQUEST_TIMEOUT + 10:
                    to_remove.append(req_id)
            
            for req_id in to_remove:
                del request_queue[req_id]
                print(f"Cleaned up timed-out request: {req_id}")


if __name__ == '__main__':
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_old_requests, daemon=True)
    cleanup_thread.start()
    
    print("Starting Gemini Chat Userscript Server (HTTP Polling)")
    print("HTTP server: http://localhost:8765")
    print("Make sure the userscript is installed and running on gemini.google.com")
    print("")
    print("Endpoints:")
    print("  GET  /health - Health check")
    print("  GET  /poll - Userscript polling endpoint")
    print("  POST /response - Userscript response endpoint")
    print("  POST /v1/models/{model}/generateContent - Gemini API endpoint")
    print("")
    
    # Run Flask app
    app.run(host='127.0.0.1', port=8765, debug=False, use_reloader=False)

