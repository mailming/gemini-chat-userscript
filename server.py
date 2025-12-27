#!/usr/bin/env python3
"""
Gemini Chat Userscript Server
Converts Gemini chat interface into an LLM API server via userscript bridge.
"""

import json
import uuid
import threading
import time
import asyncio
from flask import Flask, request, jsonify
from flask_cors import CORS
import websockets
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Allow all origins for localhost development

# Request queue: {requestId: {request_data, response_data, event, timestamp}}
request_queue = {}
request_lock = threading.Lock()

# Connected userscript clients (WebSocket connections)
connected_clients = set()
clients_lock = threading.Lock()

# Request timeout (seconds)
REQUEST_TIMEOUT = 60

# WebSocket server
ws_server = None
ws_loop = None


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    with clients_lock:
        client_count = len(connected_clients)
    with request_lock:
        pending_count = len(request_queue)
    
    return jsonify({
        'status': 'ok',
        'connected_clients': client_count,
        'pending_requests': pending_count
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
        
        # Check if userscript is connected
        with clients_lock:
            if not connected_clients:
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
                'model': model
            }
        
        # Send request to userscript via WebSocket
        send_to_clients({
            'type': 'request',
            'requestId': request_id,
            'message': message_text,
            'model': model
        })
        
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


def send_to_clients(message):
    """Send message to all connected WebSocket clients"""
    if ws_loop is None:
        return
    
    message_json = json.dumps(message)
    with clients_lock:
        clients_copy = list(connected_clients)  # Copy to avoid modification during iteration
    
    disconnected = []
    for client in clients_copy:
        try:
            # Schedule coroutine in the WebSocket event loop
            future = asyncio.run_coroutine_threadsafe(client.send(message_json), ws_loop)
            future.result(timeout=1)  # Wait up to 1 second
        except Exception as e:
            print(f"Error sending to client: {e}")
            disconnected.append(client)
    
    # Remove disconnected clients
    with clients_lock:
        for client in disconnected:
            connected_clients.discard(client)


async def handle_websocket(websocket, path):
    """Handle WebSocket connections from userscript"""
    print(f"Userscript connected: {websocket.remote_address}")
    
    with clients_lock:
        connected_clients.add(websocket)
    
    # Send connection confirmation
    await websocket.send(json.dumps({'type': 'connected', 'status': 'ok'}))
    
    # Send any pending requests
    with request_lock:
        for req_id, req_data in request_queue.items():
            if req_data.get('response_data') is None:
                await websocket.send(json.dumps({
                    'type': 'request',
                    'requestId': req_id,
                    'message': req_data['request_data']['contents'][0]['parts'][0].get('text', ''),
                    'model': req_data.get('model', 'gemini-pro')
                }))
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                
                if data.get('type') == 'response':
                    handle_response(data)
                elif data.get('type') == 'ping':
                    await websocket.send(json.dumps({
                        'type': 'pong',
                        'timestamp': time.time()
                    }))
                    
            except json.JSONDecodeError:
                print(f"Invalid JSON received: {message}")
            except Exception as e:
                print(f"Error handling message: {e}")
                
    except websockets.exceptions.ConnectionClosed:
        print(f"Userscript disconnected: {websocket.remote_address}")
    finally:
        with clients_lock:
            connected_clients.discard(websocket)


def handle_response(data):
    """Handle response from userscript"""
    request_id = data.get('requestId')
    response_text = data.get('response')
    error = data.get('error')
    
    if not request_id:
        print("Warning: Received response without requestId")
        return
    
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
        else:
            print(f"Warning: Received response for unknown requestId: {request_id}")


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


def start_websocket_server():
    """Start WebSocket server in a separate thread"""
    global ws_loop, ws_server
    
    async def run_server():
        global ws_server
        ws_server = await websockets.serve(handle_websocket, "127.0.0.1", 8766)
        print("WebSocket server started on ws://127.0.0.1:8766")
        await ws_server.wait_closed()
    
    ws_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(ws_loop)
    ws_loop.run_until_complete(run_server())


if __name__ == '__main__':
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_old_requests, daemon=True)
    cleanup_thread.start()
    
    # Start WebSocket server in separate thread
    ws_thread = threading.Thread(target=start_websocket_server, daemon=True)
    ws_thread.start()
    
    # Give WebSocket server time to start
    time.sleep(1)
    
    print("Starting Gemini Chat Userscript Server")
    print("HTTP server: http://localhost:8765")
    print("WebSocket server: ws://localhost:8766")
    print("Make sure the userscript is installed and running on gemini.google.com")
    
    # Run Flask app
    app.run(host='127.0.0.1', port=8765, debug=False, use_reloader=False)
