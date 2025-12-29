# Gemini Chat Playwright Script

A Playwright-based automation script to interact with the Gemini chat interface at gemini.google.com.

## Prerequisites

- Node.js (v18 or higher recommended)
- npm (comes with Node.js)

## Installation

1. Install Node.js if you haven't already:
   - Visit [nodejs.org](https://nodejs.org/) and download the installer for your platform
   - Or use a package manager like Homebrew on macOS: `brew install node`

2. Install dependencies:
   ```bash
   npm install
   ```

   This will install Playwright and download the necessary browser binaries.

## Usage

### Basic Usage

Run the script with the default message:
```bash
npm start
```

Or run directly with Node:
```bash
node gemini-chat.js
```

### Custom Message

Pass a custom message as a command-line argument:
```bash
node gemini-chat.js "Your message here"
```

Example:
```bash
node gemini-chat.js "What is the capital of France?"
```

## How It Works

1. Launches a browser with persistent profile (maintains login state)
2. Navigates to `https://gemini.google.com`
3. Waits for the chat input box to be available
4. Types your message (or the default "Hello, Gemini!")
5. Sends the message by clicking the send button or pressing Enter
6. Waits for the response to complete
7. Captures and displays the response in the console
8. Keeps the browser open for 5 seconds so you can verify the interaction
9. Closes the browser (profile is saved for next time)

## Persistent Browser Profile

The script uses a persistent browser context that saves your login state. This means:

- **First run**: You'll need to manually log in to your Google account (mailming@gmail.com) when the browser opens
- **Subsequent runs**: The script will automatically use your logged-in session
- **Profile location**: Browser profile is saved in `browser-profile/` directory (excluded from git)

### First-Time Login

1. Run the script: `npm start`
2. When the browser opens, manually log in to your Google account (mailming@gmail.com) at gemini.google.com
3. The login state will be saved automatically
4. Future runs will use this saved session

## Configuration

### Headless Mode

To run the browser in headless mode (without a visible window), edit `gemini-chat.js` and change:
```javascript
headless: false, // Set to true to run in headless mode
```
to:
```javascript
headless: true,
```

### Adjusting Selectors

The script uses multiple selector strategies to find the chat input and send button, as Gemini's UI may change. If the script fails to find elements, you may need to:

1. Inspect the Gemini page in your browser
2. Update the selectors in `gemini-chat.js` in the `chatInputSelectors` and `sendButtonSelectors` arrays

## Troubleshooting

### Chat input not found
- Make sure you're logged into your Google account
- The page may have changed - check the selectors in the script
- Try running with `headless: false` to see what's happening

### Authentication required
- **First time**: You'll need to manually log in when the browser opens. The login will be saved automatically.
- **Subsequent runs**: The script uses your saved browser profile, so you should already be logged in.
- If you need to log in again, just delete the `browser-profile/` directory and run the script again.

### Browser not launching
- Make sure Playwright browsers are installed: `npx playwright install chromium`
- Check that you have sufficient permissions

## Notes

- The script uses a persistent browser profile to maintain your Google login session
- Response text is automatically captured and displayed in the console
- The browser stays open for 5 seconds after completion so you can verify the interaction
- Browser profile is stored in `browser-profile/` directory (automatically created)

## License

MIT

