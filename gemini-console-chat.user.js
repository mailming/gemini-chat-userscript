// ==UserScript==
// @name         Gemini Console Chat Interface
// @namespace    userscript://gemini-console-chat
// @version      2.0
// @description  Console interface + WebSocket bridge to interact with Gemini chat via server API
// @author       Your Name
// @match        https://gemini.google.com/app/*
// @grant        none
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';

    console.log('🤖 Gemini Console Chat Interface loaded!');
    console.log('📝 Console Usage:');
    console.log('  - geminiSend("your message") - Send a message to Gemini and wait for response');
    console.log('  - geminiType("your message") - Type message character by character (then send manually)');
    console.log('  - geminiGetLastResponse() - Get the last response from Gemini');
    console.log('  - geminiGetAllMessages() - Get all messages in the current chat');
    console.log('  - geminiDebug() - Show debug information about page elements');
    console.log('');
    console.log('🔌 Server Bridge:');
    console.log('  - geminiConnect() - Connect to local server (ws://localhost:8766)');
    console.log('  - geminiDisconnect() - Disconnect from server');
    console.log('  - geminiServerStatus() - Check server connection status');
    console.log('  - geminiTestConnection() - Test WebSocket connectivity');

    // WebSocket connection management
    let ws = null;
    let reconnectTimer = null;
    let isManualDisconnect = false;
    const WS_URL = 'ws://127.0.0.1:8766';
    const RECONNECT_DELAY = 5000; // 5 seconds

    // Find the input textarea
    function findInputBox() {
        // Common selectors for Gemini's input box
        const selectors = [
            'rich-textarea[placeholder*="Enter"]',
            'rich-textarea',
            'div[contenteditable="true"][role="textbox"]',
            'textarea[placeholder*="Enter"]',
            '.ql-editor[contenteditable="true"]',
            '[data-placeholder*="Enter"]'
        ];

        for (const selector of selectors) {
            const element = document.querySelector(selector);
            if (element) {
                console.log('✅ Found input box:', selector);
                return element;
            }
        }
        return null;
    }

    // Find the send button
    function findSendButton() {
        const selectors = [
            'button[aria-label*="Send"]',
            'button[aria-label*="send"]',
            'button[mattooltip*="Send"]',
            'button[mattooltip*="send"]',
            'button.send-button',
            'button[type="submit"]',
            '[data-test-id="send-button"]',
            'button[jsname]' // Gemini uses jsname attributes
        ];

        for (const selector of selectors) {
            const buttons = document.querySelectorAll(selector);
            for (const button of buttons) {
                // Check if visible and enabled
                if (button.offsetParent !== null && !button.disabled) {
                    // Additional check: button should be near the input box
                    const ariaLabel = button.getAttribute('aria-label') || '';
                    const tooltip = button.getAttribute('mattooltip') || '';
                    const buttonText = button.innerText || '';
                    
                    // Look for send-related text
                    if (ariaLabel.toLowerCase().includes('send') || 
                        tooltip.toLowerCase().includes('send') ||
                        buttonText.toLowerCase().includes('send') ||
                        selector.includes('jsname')) {
                        console.log('✅ Found send button:', selector, ariaLabel || tooltip || 'jsname button');
                        return button;
                    }
                }
            }
        }
        
        // Fallback: find any button near the input that's enabled
        const inputBox = findInputBox();
        if (inputBox) {
            const parent = inputBox.closest('form, div[role="form"], .input-container') || inputBox.parentElement;
            if (parent) {
                const nearbyButtons = parent.querySelectorAll('button');
                for (const button of nearbyButtons) {
                    if (button.offsetParent !== null && !button.disabled) {
                        console.log('✅ Found nearby button (fallback)');
                        return button;
                    }
                }
            }
        }
        
        return null;
    }

    // Get all message elements
    function getAllMessages() {
        const messages = [];
        
        // Try to find message containers - Gemini uses custom elements
        const messageSelectors = [
            'message-content',           // Gemini's message element
            'model-response',            // Gemini's response element
            'user-query',                // User messages
            '[data-test-id*="message"]',
            '.message-content',
            '[role="presentation"] > div > div',
            '.conversation-turn',
            'chat-message'
        ];

        let messageElements = [];
        for (const selector of messageSelectors) {
            messageElements = document.querySelectorAll(selector);
            if (messageElements.length > 0) {
                console.log(`🔍 Found ${messageElements.length} elements with selector: ${selector}`);
                break;
            }
        }

        // If no specific selectors work, try to find all text-containing divs in the chat area
        if (messageElements.length === 0) {
            const chatContainer = document.querySelector('chat-window, [role="main"], main');
            if (chatContainer) {
                // Look for divs that likely contain messages
                const allDivs = chatContainer.querySelectorAll('div[data-message-id], div[jsname], div[data-test-id]');
                messageElements = Array.from(allDivs).filter(el => {
                    const text = el.innerText || el.textContent;
                    return text && text.trim().length > 10; // Filter out empty or very short divs
                });
                console.log(`🔍 Found ${messageElements.length} potential message divs in chat container`);
            }
        }

        messageElements.forEach((element, index) => {
            const text = element.innerText || element.textContent;
            if (text && text.trim()) {
                messages.push({
                    index: index,
                    text: text.trim(),
                    element: element
                });
            }
        });

        return messages;
    }

    // Get the last response from Gemini
    function getLastResponse() {
        const messages = getAllMessages();
        if (messages.length === 0) {
            console.log('⚠️ No messages found');
            return null;
        }

        // The last message is typically Gemini's response
        const lastMessage = messages[messages.length - 1];
        console.log('📨 Last response from Gemini:');
        console.log(lastMessage.text);
        return lastMessage.text;
    }

    // Send a message to Gemini
    async function sendMessage(text) {
        if (!text || text.trim() === '') {
            console.error('❌ Error: Message cannot be empty');
            return false;
        }

        console.log('📤 Sending message:', text);

        const inputBox = findInputBox();
        if (!inputBox) {
            console.error('❌ Error: Could not find input box');
            console.log('💡 Tip: Make sure you are on the Gemini chat page');
            return false;
        }

        // Focus the input box first
        inputBox.focus();
        await new Promise(resolve => setTimeout(resolve, 100));

        // For rich-textarea (Gemini's custom element)
        if (inputBox.tagName.toLowerCase() === 'rich-textarea') {
            // Find the actual editable div inside rich-textarea
            const editableDiv = inputBox.querySelector('[contenteditable="true"]') || 
                               inputBox.querySelector('.ql-editor') ||
                               inputBox.shadowRoot?.querySelector('[contenteditable="true"]');
            
            if (editableDiv) {
                console.log('📝 Found editable div inside rich-textarea');
                editableDiv.focus();
                
                // Clear existing content safely (avoid innerHTML due to Trusted Types)
                while (editableDiv.firstChild) {
                    editableDiv.removeChild(editableDiv.firstChild);
                }
                
                // Create a text node and insert it
                const textNode = document.createTextNode(text);
                const paragraph = document.createElement('p');
                paragraph.appendChild(textNode);
                editableDiv.appendChild(paragraph);
                
                // Set cursor to end
                const range = document.createRange();
                const sel = window.getSelection();
                range.setStart(paragraph, 1);
                range.collapse(true);
                sel.removeAllRanges();
                sel.addRange(range);
                
                // Trigger all necessary events
                editableDiv.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
                editableDiv.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
                editableDiv.dispatchEvent(new InputEvent('input', { bubbles: true, composed: true, data: text }));
                
                // Also trigger on the rich-textarea itself
                inputBox.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
                inputBox.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
            } else {
                // Fallback: try setting value property
                console.log('⚠️ Could not find editable div, trying direct property set');
                if (inputBox.value !== undefined) {
                    inputBox.value = text;
                }
                inputBox.textContent = text;
                inputBox.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
            }
        } else if (inputBox.tagName === 'TEXTAREA' || inputBox.tagName === 'INPUT') {
            inputBox.value = text;
            inputBox.dispatchEvent(new Event('input', { bubbles: true }));
            inputBox.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
            // For contenteditable divs - avoid innerHTML
            while (inputBox.firstChild) {
                inputBox.removeChild(inputBox.firstChild);
            }
            const paragraph = document.createElement('p');
            paragraph.textContent = text;
            inputBox.appendChild(paragraph);
            
            inputBox.dispatchEvent(new Event('input', { bubbles: true }));
            inputBox.dispatchEvent(new Event('change', { bubbles: true }));
        }

        // Wait for UI to update
        await new Promise(resolve => setTimeout(resolve, 800));

        // Find and click the send button (more reliable than Enter key for Gemini)
        const sendButton = findSendButton();
        if (sendButton) {
            console.log('🖱️ Clicking send button...');
            sendButton.click();
            console.log('✅ Message sent!');
            console.log('⏳ Waiting for response...');
        } else {
            console.error('❌ Could not find send button');
            console.log('💡 Try using geminiType() and then manually click send');
            return false;
        }

        // Monitor for new responses
        const initialMessageCount = getAllMessages().length;
        let attempts = 0;
        const maxAttempts = 60; // 30 seconds timeout

        return new Promise((resolve) => {
            const checkInterval = setInterval(() => {
                attempts++;
                const currentMessages = getAllMessages();
                
                if (currentMessages.length > initialMessageCount) {
                    clearInterval(checkInterval);
                    console.log('✅ Response received!');
                    const response = getLastResponse();
                    resolve(response);
                } else if (attempts >= maxAttempts) {
                    clearInterval(checkInterval);
                    console.log('⏱️ Timeout: No response detected after 30 seconds');
                    console.log('💡 Tip: The response might still be generating. Use geminiGetLastResponse() to check manually');
                    resolve(null);
                }
            }, 500);
        });
    }

    // Export functions to window for console access
    window.geminiSend = async function(message) {
        return await sendMessage(message);
    };

    window.geminiGetLastResponse = function() {
        return getLastResponse();
    };

    window.geminiGetAllMessages = function() {
        const messages = getAllMessages();
        console.log(`📋 Found ${messages.length} messages:`);
        messages.forEach((msg, idx) => {
            console.log(`\n--- Message ${idx + 1} ---`);
            console.log(msg.text);
        });
        return messages;
    };

    // Helper function to debug selectors
    window.geminiDebug = function() {
        console.log('🔍 Debug Information:');
        console.log('═══════════════════════════════════════');
        
        const inputBox = findInputBox();
        console.log('📝 Input box:', inputBox);
        if (inputBox) {
            console.log('  - Tag:', inputBox.tagName);
            console.log('  - Has contenteditable child:', !!inputBox.querySelector('[contenteditable="true"]'));
            console.log('  - Shadow root:', !!inputBox.shadowRoot);
        }
        
        console.log('\n🔘 Send button:', findSendButton());
        
        console.log('\n💬 Messages:');
        const messages = getAllMessages();
        console.log('  - Total found:', messages.length);
        
        console.log('\n🔎 Checking custom elements:');
        console.log('  - message-content:', document.querySelectorAll('message-content').length);
        console.log('  - model-response:', document.querySelectorAll('model-response').length);
        console.log('  - user-query:', document.querySelectorAll('user-query').length);
        console.log('  - chat-message:', document.querySelectorAll('chat-message').length);
        
        console.log('\n🌳 DOM Structure sample:');
        const main = document.querySelector('main, [role="main"]');
        if (main) {
            const children = main.children;
            console.log('  - Main container children:', children.length);
            if (children.length > 0) {
                console.log('  - First child:', children[0].tagName, children[0].className);
            }
        }
        
        console.log('═══════════════════════════════════════');
    };

    // Alternative manual typing simulation
    window.geminiType = function(text) {
        console.log('⌨️ Typing message:', text);
        const inputBox = findInputBox();
        if (!inputBox) {
            console.error('❌ Could not find input box');
            return;
        }
        
        const editableDiv = inputBox.querySelector('[contenteditable="true"]') || inputBox;
        editableDiv.focus();
        
        // Clear content safely
        while (editableDiv.firstChild) {
            editableDiv.removeChild(editableDiv.firstChild);
        }
        
        // Simulate typing character by character
        const p = document.createElement('p');
        editableDiv.appendChild(p);
        
        let i = 0;
        const typeInterval = setInterval(() => {
            if (i < text.length) {
                p.textContent += text[i];
                editableDiv.dispatchEvent(new InputEvent('input', { 
                    bubbles: true, 
                    composed: true,
                    data: text[i]
                }));
                i++;
            } else {
                clearInterval(typeInterval);
                console.log('✅ Typing complete! Now press Enter or click Send manually');
            }
        }, 50);
    };

    // WebSocket connection functions
    function connectToServer() {
        if (ws && ws.readyState === WebSocket.OPEN) {
            console.log('✅ Already connected to server');
            return;
        }

        isManualDisconnect = false;
        console.log('🔌 Connecting to server at', WS_URL);

        try {
            ws = new WebSocket(WS_URL);

            ws.onopen = () => {
                console.log('✅ Connected to Gemini Chat Server!');
                console.log('🎯 Server can now send requests to this browser tab');
                
                // Send ping to confirm connection
                try {
                    ws.send(JSON.stringify({
                        type: 'ping',
                        timestamp: Date.now()
                    }));
                } catch (e) {
                    console.error('❌ Error sending ping:', e);
                }
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    handleServerMessage(data);
                } catch (e) {
                    console.error('❌ Error parsing server message:', e);
                }
            };

            ws.onerror = (error) => {
                console.error('❌ WebSocket error:', error);
                console.error('Error details:', {
                    type: error.type,
                    target: error.target,
                    url: WS_URL
                });
                console.log('💡 Possible issues:');
                console.log('   1. Server not running: python server.py');
                console.log('   2. Port blocked by firewall');
                console.log('   3. Check server terminal for errors');
            };

            ws.onclose = (event) => {
                console.log('🔌 Disconnected from server');
                console.log('Close details:', {
                    code: event.code,
                    reason: event.reason || 'No reason provided',
                    wasClean: event.wasClean
                });
                ws = null;

                // Auto-reconnect unless manually disconnected
                if (!isManualDisconnect) {
                    console.log(`🔄 Reconnecting in ${RECONNECT_DELAY/1000} seconds...`);
                    reconnectTimer = setTimeout(connectToServer, RECONNECT_DELAY);
                }
            };

        } catch (e) {
            console.error('❌ Failed to create WebSocket:', e);
            console.error('Exception details:', e.message, e.stack);
            console.log('💡 Make sure the server is running: python server.py');
        }
    }

    function disconnectFromServer() {
        isManualDisconnect = true;
        
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }

        if (ws) {
            ws.close();
            ws = null;
            console.log('🔌 Manually disconnected from server');
        } else {
            console.log('⚠️ Not connected to server');
        }
    }

    function getServerStatus() {
        if (!ws) {
            console.log('🔴 Not connected to server');
            console.log('💡 Use geminiConnect() to connect');
            return 'disconnected';
        }

        const states = {
            [WebSocket.CONNECTING]: '🟡 Connecting...',
            [WebSocket.OPEN]: '🟢 Connected',
            [WebSocket.CLOSING]: '🟡 Closing...',
            [WebSocket.CLOSED]: '🔴 Closed'
        };

        const status = states[ws.readyState] || '❓ Unknown';
        console.log('Server status:', status);
        return status;
    }

    async function handleServerMessage(data) {
        console.log('📨 Received from server:', data.type);

        switch (data.type) {
            case 'connected':
                console.log('✅ Server acknowledged connection');
                break;

            case 'pong':
                // Ping response - connection is alive
                break;

            case 'request':
                // Server is requesting us to send a message to Gemini
                await handleServerRequest(data);
                break;

            default:
                console.log('⚠️ Unknown message type:', data.type);
        }
    }

    async function handleServerRequest(data) {
        const { requestId, message, model } = data;
        
        console.log('📥 Server request:', {
            requestId: requestId,
            message: message.substring(0, 50) + (message.length > 50 ? '...' : ''),
            model: model
        });

        try {
            // Send message to Gemini and wait for response
            const response = await sendMessageForServer(message);

            if (response) {
                // Send response back to server
                sendToServer({
                    type: 'response',
                    requestId: requestId,
                    response: response
                });
                console.log('✅ Response sent to server');
            } else {
                // Send error if no response
                sendToServer({
                    type: 'response',
                    requestId: requestId,
                    error: 'No response received from Gemini'
                });
                console.log('⚠️ No response received from Gemini');
            }

        } catch (error) {
            console.error('❌ Error processing server request:', error);
            sendToServer({
                type: 'response',
                requestId: requestId,
                error: error.message || 'Unknown error'
            });
        }
    }

    function sendToServer(data) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(data));
        } else {
            console.error('❌ Cannot send to server: not connected');
        }
    }

    // Modified sendMessage function for server requests (no console logging spam)
    async function sendMessageForServer(text) {
        if (!text || text.trim() === '') {
            throw new Error('Message cannot be empty');
        }

        const inputBox = findInputBox();
        if (!inputBox) {
            throw new Error('Could not find input box');
        }

        // Focus the input box first
        inputBox.focus();
        await new Promise(resolve => setTimeout(resolve, 100));

        // For rich-textarea (Gemini's custom element)
        if (inputBox.tagName.toLowerCase() === 'rich-textarea') {
            const editableDiv = inputBox.querySelector('[contenteditable="true"]') || 
                               inputBox.querySelector('.ql-editor') ||
                               inputBox.shadowRoot?.querySelector('[contenteditable="true"]');
            
            if (editableDiv) {
                editableDiv.focus();
                
                // Clear existing content safely
                while (editableDiv.firstChild) {
                    editableDiv.removeChild(editableDiv.firstChild);
                }
                
                // Create a text node and insert it
                const textNode = document.createTextNode(text);
                const paragraph = document.createElement('p');
                paragraph.appendChild(textNode);
                editableDiv.appendChild(paragraph);
                
                // Set cursor to end
                const range = document.createRange();
                const sel = window.getSelection();
                range.setStart(paragraph, 1);
                range.collapse(true);
                sel.removeAllRanges();
                sel.addRange(range);
                
                // Trigger all necessary events
                editableDiv.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
                editableDiv.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
                editableDiv.dispatchEvent(new InputEvent('input', { bubbles: true, composed: true, data: text }));
                
                // Also trigger on the rich-textarea itself
                inputBox.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
                inputBox.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
            } else {
                if (inputBox.value !== undefined) {
                    inputBox.value = text;
                }
                inputBox.textContent = text;
                inputBox.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
            }
        } else if (inputBox.tagName === 'TEXTAREA' || inputBox.tagName === 'INPUT') {
            inputBox.value = text;
            inputBox.dispatchEvent(new Event('input', { bubbles: true }));
            inputBox.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
            while (inputBox.firstChild) {
                inputBox.removeChild(inputBox.firstChild);
            }
            const paragraph = document.createElement('p');
            paragraph.textContent = text;
            inputBox.appendChild(paragraph);
            
            inputBox.dispatchEvent(new Event('input', { bubbles: true }));
            inputBox.dispatchEvent(new Event('change', { bubbles: true }));
        }

        // Wait for UI to update
        await new Promise(resolve => setTimeout(resolve, 800));

        // Find and click the send button
        const sendButton = findSendButton();
        if (sendButton) {
            sendButton.click();
        } else {
            throw new Error('Could not find send button');
        }

        // Monitor for new responses
        const initialMessageCount = getAllMessages().length;
        let attempts = 0;
        const maxAttempts = 120; // 60 seconds timeout for server requests

        return new Promise((resolve) => {
            const checkInterval = setInterval(() => {
                attempts++;
                const currentMessages = getAllMessages();
                
                if (currentMessages.length > initialMessageCount) {
                    clearInterval(checkInterval);
                    const lastMsg = currentMessages[currentMessages.length - 1];
                    resolve(lastMsg.text);
                } else if (attempts >= maxAttempts) {
                    clearInterval(checkInterval);
                    resolve(null);
                }
            }, 500);
        });
    }

    // Export WebSocket functions to window
    window.geminiConnect = function() {
        connectToServer();
    };

    window.geminiDisconnect = function() {
        disconnectFromServer();
    };

    window.geminiServerStatus = function() {
        return getServerStatus();
    };

    // Test WebSocket connectivity
    window.geminiTestConnection = function() {
        console.log('🧪 Testing WebSocket connection...');
        console.log('Target URL:', WS_URL);
        console.log('Current ws state:', ws ? ws.readyState : 'null');
        
        // Try to create a test connection
        try {
            const testWs = new WebSocket(WS_URL);
            
            testWs.onopen = () => {
                console.log('✅ Test connection successful!');
                testWs.close();
            };
            
            testWs.onerror = (error) => {
                console.error('❌ Test connection failed:', error);
            };
            
            testWs.onclose = (event) => {
                console.log('Test connection closed:', event.code, event.reason);
            };
            
            setTimeout(() => {
                if (testWs.readyState === WebSocket.CONNECTING) {
                    console.log('⏱️ Still connecting after 5 seconds...');
                    testWs.close();
                }
            }, 5000);
            
        } catch (e) {
            console.error('❌ Cannot create WebSocket:', e);
        }
    };

    // Show welcome message after page loads
    setTimeout(() => {
        console.log('\n🎉 Ready to chat with Gemini via console!');
        console.log('Try: geminiSend("Hello, Gemini!")');
        console.log('');
        console.log('🌐 To enable server bridge:');
        console.log('  1. Run: python server.py');
        console.log('  2. Then: geminiConnect()');
    }, 2000);

    // Auto-connect to server after 3 seconds
    setTimeout(() => {
        console.log('🔄 Auto-connecting to server...');
        connectToServer();
    }, 3000);

})();

