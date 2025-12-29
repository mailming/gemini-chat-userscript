import { chromium } from 'playwright';
import { join } from 'path';
import { mkdirSync } from 'fs';
import { createInterface } from 'readline';

/**
 * Playwright script to interact with Gemini chat interface at gemini.google.com
 * Uses persistent browser context to maintain login state
 */
async function interactWithGemini() {
  // Create user data directory for persistent browser profile
  const userDataDir = join(process.cwd(), 'browser-profile');
  try {
    mkdirSync(userDataDir, { recursive: true });
  } catch (e) {
    // Directory might already exist, that's fine
  }

  // Launch browser with persistent context (maintains login state)
  // This will use your logged-in Google account (mailming@gmail.com) if you've logged in before
  const contextOptions = {
    headless: false, // Set to true to run in headless mode
  };
  
  // Try to use Chrome if available (better compatibility with Google services)
  // Otherwise fall back to Chromium
  let context;
  try {
    context = await chromium.launchPersistentContext(userDataDir, {
      ...contextOptions,
      channel: 'chrome',
    });
    console.log('Using Chrome browser with persistent profile...');
  } catch (e) {
    // Chrome not available, use Chromium
    context = await chromium.launchPersistentContext(userDataDir, contextOptions);
    console.log('Using Chromium browser with persistent profile...');
  }

  try {
    // Get the first page (or create one if none exists)
    const pages = context.pages();
    const page = pages.length > 0 ? pages[0] : await context.newPage();

    // Navigate to Gemini
    console.log('Navigating to gemini.google.com...');
    await page.goto('https://gemini.google.com', {
      waitUntil: 'domcontentloaded', // Faster than 'load'
      timeout: 60000,
    });

    // Wait for the chat input to be available using Promise.race for faster detection
    console.log('Waiting for chat input...');
    
    const chatInputSelectors = [
      'div[contenteditable="true"][role="textbox"]', // Most specific first
      'textarea[placeholder*="chat"]',
      'textarea[aria-label*="chat"]',
      'textarea[data-testid*="input"]',
      'textarea',
    ];

    // Try all selectors in parallel, use the first one that appears
    const chatInputPromises = chatInputSelectors.map(selector =>
      page.waitForSelector(selector, { timeout: 10000 }).catch(() => null)
    );
    
    const results = await Promise.allSettled(chatInputPromises);
    let chatInput = null;
    let usedSelector = null;
    
    for (let i = 0; i < results.length; i++) {
      if (results[i].status === 'fulfilled' && results[i].value) {
        chatInput = results[i].value;
        usedSelector = chatInputSelectors[i];
        console.log(`Found chat input with selector: ${usedSelector}`);
        break;
      }
    }

    if (!chatInput) {
      console.log('\n⚠️  Chat input not found. You may need to log in first.');
      console.log('Please log in to your Google account (mailming@gmail.com) in the browser window.');
      console.log('Once you are logged in and can see the chat interface, press Enter in this terminal to continue...\n');
      
      // Wait for user to press Enter
      const rl = createInterface({
        input: process.stdin,
        output: process.stdout,
      });
      
      await new Promise((resolve) => {
        rl.question('', () => {
          rl.close();
          resolve();
        });
      });
      
      // Try to find chat input again after user confirms they're logged in
      console.log('Checking for chat input again...');
      await page.waitForTimeout(2000); // Give page a moment to update
      
      for (const selector of chatInputSelectors) {
        try {
          chatInput = await page.$(selector);
          if (chatInput) {
            console.log(`Found chat input with selector: ${selector}`);
            break;
          }
        } catch (e) {
          continue;
        }
      }
      
      if (!chatInput) {
        console.log('Chat input still not found. Available page content:');
        const bodyText = await page.textContent('body');
        console.log(bodyText?.substring(0, 500));
        throw new Error('Could not find chat input element after login attempt');
      }
    }

    // Example: Send a message
    const message = process.argv[2] || 'Hello, Gemini!';
    console.log(`Sending message: "${message}"`);

    // Type the message
    await chatInput.fill(message);

    // Find and click the send button - try in parallel
    const sendButtonSelectors = [
      'button[aria-label*="Send"]',
      'button[aria-label*="send"]',
      'button[type="submit"]',
      'button[data-testid*="send"]',
    ];

    // Try to find send button immediately (it should already be on page)
    let sendButton = null;
    for (const selector of sendButtonSelectors) {
      sendButton = await page.$(selector);
      if (sendButton) {
        console.log(`Found send button with selector: ${selector}`);
        break;
      }
    }

    if (sendButton) {
      await sendButton.click();
      console.log('Message sent!');
    } else {
      // Try pressing Enter as fallback
      console.log('Send button not found, trying Enter key...');
      await chatInput.press('Enter');
    }

    // Wait for response to start appearing using efficient waiting
    console.log('Waiting for response...');
    
    const responseIndicators = [
      '[class*="model-response"]',
      '[class*="response"]',
      '[data-message-author="model"]',
      'div[class*="markdown"]',
    ];

    // Wait for any response indicator to appear with text content
    let responseElement = null;
    try {
      // Use waitForFunction to efficiently wait for response to appear
      responseElement = await page.waitForFunction(
        (selectors) => {
          for (const selector of selectors) {
            const elements = document.querySelectorAll(selector);
            if (elements.length > 0) {
              const lastElement = elements[elements.length - 1];
              const text = lastElement.textContent?.trim();
              if (text && text.length > 0) {
                return lastElement;
              }
            }
          }
          return null;
        },
        responseIndicators,
        { timeout: 30000 }
      ).then(el => el.asElement()).catch(() => null);
      
      if (responseElement) {
        console.log('Response detected!');
      }
    } catch (e) {
      console.log('Waiting for response using fallback method...');
    }

    // Wait for response to complete using efficient polling
    console.log('Waiting for response to complete...');
    
    if (responseElement) {
      // Use waitForFunction to detect when response text stabilizes
      try {
        await page.waitForFunction(
          (elementSelector) => {
            const selectors = elementSelector.split(',');
            for (const selector of selectors) {
              const elements = document.querySelectorAll(selector);
              if (elements.length > 0) {
                const lastElement = elements[elements.length - 1];
                const text = lastElement.textContent?.trim();
                if (text && text.length > 0) {
                  // Check if text hasn't changed (response is complete)
                  const currentText = text;
                  // Store in element's dataset to compare
                  const previousText = lastElement.dataset.lastText || '';
                  if (currentText === previousText && previousText.length > 0) {
                    return true; // Text is stable
                  }
                  lastElement.dataset.lastText = currentText;
                  return false; // Text is still changing
                }
              }
            }
            return false;
          },
          responseIndicators.join(','),
          { 
            timeout: 30000,
            polling: 300 // Check every 300ms instead of 500ms
          }
        );
        console.log('Response appears complete.');
      } catch (e) {
        // Fallback: wait a bit for response to finish
        await page.waitForTimeout(2000);
      }
    } else {
      // Fallback: wait for response to appear
      await page.waitForTimeout(3000);
    }

    // Extract and display the response
    console.log('\n=== GEMINI RESPONSE ===');
    let responseText = '';
    
    // Use evaluate to efficiently extract response text
    try {
      responseText = await page.evaluate((selectors) => {
        for (const selector of selectors) {
          const elements = document.querySelectorAll(selector);
          if (elements.length > 0) {
            const lastElement = elements[elements.length - 1];
            const text = lastElement.textContent?.trim();
            if (text && text.length > 0) {
              return text;
            }
          }
        }
        return '';
      }, responseIndicators);
    } catch (e) {
      console.log('Could not extract text from response element');
    }
    
    if (responseText && responseText.trim().length > 0) {
      console.log(responseText.trim());
      console.log('=== END RESPONSE ===\n');
    } else {
      console.log('Could not capture response text. Browser will remain open for inspection...');
      console.log('=== END RESPONSE ===\n');
    }

    console.log('\n✅ Script completed successfully!');
    console.log('Browser will remain open for 30 seconds so you can review the conversation...');
    console.log('(The browser will close automatically, or you can close it manually)\n');
    await page.waitForTimeout(30000);

  } catch (error) {
    console.error('\n❌ Error interacting with Gemini:', error.message);
    console.log('\nBrowser will remain open for 60 seconds so you can troubleshoot...');
    console.log('(The browser will close automatically, or you can close it manually)\n');
    
    // Keep browser open longer on error so user can see what happened
    try {
      const pages = context.pages();
      if (pages.length > 0) {
        await pages[0].waitForTimeout(60000);
      }
    } catch (e) {
      // Ignore errors during cleanup wait
    }
  } finally {
    // Close browser context (saves profile state)
    await context.close();
    console.log('Browser closed. Profile saved for next session.');
  }
}

// Run the script
interactWithGemini().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});

