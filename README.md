# Gemini Chat API Bridge

Converts the Gemini chat interface (gemini.google.com) into an LLM API server using a userscript bridge. This allows you to interact with Gemini programmatically through a standard API interface, or directly via browser console.

## Architecture

```
Python Client → Flask Server (localhost:8765) → WebSocket → Userscript → Gemini UI
```

The Flask server accepts Gemini API format requests, communicates with a userscript running in your browser via WebSocket, and the userscript interacts with the Gemini chat interface to send messages and extract responses.

## Features

### 🎮 Console Interface
- ✅ Send messages directly from browser console
- ✅ Get responses programmatically
- ✅ Type simulation for manual control
- ✅ Debug tools for troubleshooting

### 🌐 Server Bridge
- ✅ Gemini API compatible request/response format
- ✅ Real-time WebSocket communication
- ✅ Automatic request queuing
- ✅ Auto-reconnect on connection loss
- ✅ Multiple concurrent request support
- ✅ Simple Python client interface

## Prerequisites

- Python 3.7+
- A browser with a userscript manager installed:
  - [Tampermonkey](https://www.tampermonkey.net/) (recommended)
  - [Violentmonkey](https://violentmonkey.github.io/)
- Access to [gemini.google.com](https://gemini.google.com)

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install the Userscript

1. Install a userscript manager (Tampermonkey or Violentmonkey) in your browser
2. Open the userscript manager dashboard
3. Create a new script
4. Copy the entire contents of `gemini-console-chat.user.js` into the editor
5. Save the script (Ctrl+S or Cmd+S)
6. Make sure the script is enabled

### 3. Start the Server

```bash
python server.py
```

The server will start on `http://localhost:8765`

### 4. Open Gemini in Your Browser

1. Open [gemini.google.com](https://gemini.google.com) in a new tab
2. The userscript will automatically connect to the server
3. You should see connection messages in the browser console (F12)

## Usage

### Console Commands (Direct Browser Interaction)

Open the browser console (F12) on Gemini chat page:

```javascript
// Send a message and wait for response
await geminiSend("What is the capital of France?")

// Type a message character by character (manual send)
geminiType("Hello Gemini!")

// Get the last response
geminiGetLastResponse()

// Get all messages in the chat
geminiGetAllMessages()

// Debug information
geminiDebug()

// Server bridge commands
geminiConnect()        // Connect to local server
geminiServerStatus()   // Check connection status
geminiDisconnect()     // Disconnect from server
```

**Note:** The userscript auto-connects to the server 3 seconds after page load if server is running.

### Check Server Status

```bash
curl http://localhost:8765/health
```

Or use the example client:

```bash
python example_client.py
```

### Make API Calls

The server accepts requests in Gemini API format:

```python
import requests

response = requests.post(
    'http://localhost:8765/v1/models/gemini-pro/generateContent',
    json={
        'contents': [{
            'parts': [{
                'text': 'Hello, how are you?'
            }]
        }]
    }
)

data = response.json()
print(data['candidates'][0]['content']['parts'][0]['text'])
```

### Example Client

Run the included example client:

```bash
python example_client.py
```

This will demonstrate:
- Health check
- Simple questions
- Code generation
- Multiple concurrent requests

## API Reference

### Endpoint: `POST /v1/models/{model}/generateContent`

**Request:**
```json
{
  "contents": [{
    "parts": [{
      "text": "Your message here"
    }]
  }]
}
```

**Response (Success):**
```json
{
  "candidates": [{
    "content": {
      "parts": [{
        "text": "Response text here"
      }]
    }
  }]
}
```

**Response (Error):**
```json
{
  "error": {
    "message": "Error description",
    "code": 500
  }
}
```

### Endpoint: `GET /health`

Check server status and connection state.

**Response:**
```json
{
  "status": "ok",
  "connected_clients": 1,
  "pending_requests": 0
}
```

## Configuration

### Server Ports

- HTTP server: Default port is `8765`
- WebSocket server: Default port is `8766`

To change ports, modify `server.py`:

```python
# Change HTTP port
app.run(host='127.0.0.1', port=YOUR_HTTP_PORT, ...)

# Change WebSocket port  
ws_server = await websockets.serve(handle_websocket, "127.0.0.1", YOUR_WS_PORT)
```

And update `WS_URL` in `gemini-chat.user.js`:

```javascript
const WS_URL = 'ws://localhost:YOUR_WS_PORT';
```

### Request Timeout

Default timeout is 60 seconds. Modify `REQUEST_TIMEOUT` in `server.py`.

## Troubleshooting

### "No userscript client connected"

**Solution:**
1. Make sure the userscript is installed and enabled
2. Open gemini.google.com in your browser
3. Check browser console (F12) for connection messages
4. Verify the server is running

### "Request timeout"

**Solution:**
1. Check if Gemini is responding in the browser
2. The page might need to be refreshed
3. Check browser console for errors
4. Increase timeout in `server.py` if needed

### WebSocket connection fails

**Solution:**
1. Verify server is running: `curl http://localhost:8765/health`
2. Check firewall settings
3. Make sure port 8765 is not in use by another application
4. Try restarting both server and browser

### Input field not found

**Solution:**
1. Gemini's UI may have changed
2. Open browser DevTools (F12) and inspect the page
3. Update selectors in `findInputField()` function in `gemini-chat.user.js`
4. Check console for error messages

## How It Works

1. **Python Client** makes HTTP POST request to Flask server
2. **Flask Server** queues the request and generates a unique requestId
3. **Server** sends request to userscript via WebSocket
4. **Userscript** receives request, finds input field in Gemini UI
5. **Userscript** fills input and submits message (simulates Enter key)
6. **Userscript** monitors DOM for response using MutationObserver
7. **Userscript** extracts response text and sends back to server
8. **Server** matches response to original request and returns to client

## Limitations

- Requires browser to be open with gemini.google.com tab
- One request processed at a time (others are queued)
- Response time depends on Gemini's response speed
- DOM selectors may need updates if Gemini UI changes

## Security Notes

- Server only accepts connections from localhost
- CORS is enabled for localhost development only
- Do not expose this server to the internet without proper security measures

## Contributing

Feel free to submit issues and pull requests!

## License

MIT License
