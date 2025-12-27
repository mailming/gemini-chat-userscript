# Gemini Chat Playwright Bridge

A simple and reliable way to interact with Google Gemini chat programmatically using Playwright. No userscripts, no CSP issues, just pure browser automation.

## Why Playwright?

- ✅ **No CSP restrictions** - Direct browser control
- ✅ **More reliable** - No userscript dependencies
- ✅ **Easier to debug** - See the browser in action
- ✅ **Simpler code** - One Python script does everything
- ✅ **Better error handling** - Full control over the browser

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

That's it! No userscripts needed.

## Usage

### Start the Server

```bash
python gemini_playwright.py
```

This will:
1. Start a Flask server on `http://127.0.0.1:8765`
2. Launch a Chrome browser (visible)
3. Navigate to Gemini chat
4. Wait for the page to load

**Note:** If you're not logged in to Google, you'll have 30 seconds to log in manually in the browser window.

### Use the API

Once the server shows "✓ Gemini page ready!", you can make API calls:

```python
import requests

response = requests.post(
    'http://127.0.0.1:8765/v1/models/gemini-pro/generateContent',
    json={
        'contents': [{
            'parts': [{
                'text': 'What is the capital of France?'
            }]
        }]
    }
)

result = response.json()
print(result['candidates'][0]['content']['parts'][0]['text'])
```

### Run the Example Client

```bash
python example_playwright_client.py
```

This will demonstrate:
- Health check
- Simple questions
- Code generation
- Math problems

## API Endpoints

### `GET /health`

Check server and browser status.

**Response:**
```json
{
  "status": "ok",
  "browser_ready": true,
  "pending_requests": 0
}
```

### `POST /v1/models/{model}/generateContent`

Send a message to Gemini (Gemini API compatible format).

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

**Response:**
```json
{
  "candidates": [{
    "content": {
      "parts": [{
        "text": "Response from Gemini"
      }]
    }
  }]
}
```

## How It Works

```
┌─────────────────┐
│   Your Code     │
│  (API Client)   │
└────────┬────────┘
         │ HTTP POST
         ↓
┌─────────────────┐
│  Flask Server   │
│  (Port 8765)    │
└────────┬────────┘
         │ Queue
         ↓
┌─────────────────┐
│   Playwright    │
│  (Browser Auto) │
└────────┬────────┘
         │ DOM Control
         ↓
┌─────────────────┐
│  Gemini Chat    │
│  (Browser)      │
└─────────────────┘
```

1. Your code sends HTTP request to Flask server
2. Server queues the request
3. Playwright types message into Gemini chat
4. Playwright waits for and extracts response
5. Server returns response to your code

## Configuration

### Headless Mode

To run the browser in headless mode (invisible), edit `gemini_playwright.py`:

```python
browser = await p.chromium.launch(
    headless=True,  # Change to True
    args=['--disable-blink-features=AutomationControlled']
)
```

### Timeout

Default timeout is 60 seconds. Change in `gemini_playwright.py`:

```python
REQUEST_TIMEOUT = 60  # Change this value
```

### Port

Default port is 8765. Change in `gemini_playwright.py`:

```python
app.run(host='127.0.0.1', port=8765, ...)  # Change port here
```

## Advantages Over Userscript

| Feature | Playwright | Userscript |
|---------|-----------|------------|
| CSP Issues | ❌ None | ✅ Must bypass |
| Installation | Simple pip install | Browser extension + script |
| Debugging | Easy - see browser | Hard - console only |
| Reliability | High | Medium |
| Login handling | Automatic | Manual |
| Multi-tab | Single controlled tab | Any tab |

## Troubleshooting

### "Browser not ready"

**Solution:** Wait for the browser to fully load. If you see the Gemini login page, log in manually. The script waits 30 seconds for manual login.

### "Could not find input box"

**Solution:**
1. Check if Gemini's UI has changed
2. Update selectors in `find_input_box()` function
3. Make sure you're logged in to Google

### Browser closes immediately

**Solution:** Make sure you're running the script with `python gemini_playwright.py`, not importing it.

### Timeout errors

**Solution:**
1. Increase `REQUEST_TIMEOUT` value
2. Check your internet connection
3. Gemini might be slow - this is normal

## Tips

- **Keep browser window visible** during development for easier debugging
- **Don't close the browser window** - let the script control it
- **One request at a time** - requests are queued automatically
- **Session persists** - your conversation history stays in the browser

## Security Notes

- Runs on localhost only (127.0.0.1)
- Browser runs with your Google account
- No data is stored or logged by the script
- All communication stays on your machine

## License

GNU General Public License v3.0

## Contributing

Issues and pull requests welcome!

