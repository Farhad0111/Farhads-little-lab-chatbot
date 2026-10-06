document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');
    const statusIndicator = document.querySelector('.status-indicator');

    // Clean assistant text without removing the line breaks used by lists.
    function sanitizeText(text) {
        if (!text) return "";
        let cleaned = text;
        // Remove thinking tags
        cleaned = cleaned.replace(/<think>[\s\S]*?<\/think>/g, '');
        // Remove markdown emphasis but keep list markers for structured rendering.
        cleaned = cleaned.replace(/\*{1,3}([^*]+)\*{1,3}/g, '$1');
        cleaned = cleaned.replace(/^\s*\*\s+/gm, '- ');
        // Remove emojis and pictographs
        cleaned = cleaned.replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F780}-\u{1F7FF}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{2300}-\u{23FF}\u{2B50}\u{200D}\u{FE0F}]/gu, '');
        // Remove standalone quote marks if wrapped or hanging
        cleaned = cleaned.replace(/^["']+|["']+$/g, '');
        // Normalize horizontal whitespace but preserve paragraph and list breaks.
        cleaned = cleaned.replace(/\r\n?/g, '\n');
        cleaned = cleaned.replace(/[ \t]+/g, ' ');
        cleaned = cleaned.replace(/\n{3,}/g, '\n\n').trim();
        return cleaned;
    }

    function appendTextWithLinks(element, text) {
        const linkPattern = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s<]+)/g;
        let lastIndex = 0;
        let match;

        while ((match = linkPattern.exec(text)) !== null) {
            element.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));

            const url = match[2] || match[3];
            const trailingPunctuation = url.match(/[.,!?;:]+$/);
            const cleanUrl = trailingPunctuation ? url.slice(0, -trailingPunctuation[0].length) : url;
            const link = document.createElement('a');
            link.href = cleanUrl;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.textContent = 'Click here';
            element.appendChild(link);

            if (trailingPunctuation) {
                element.appendChild(document.createTextNode(trailingPunctuation[0]));
            }
            lastIndex = match.index + match[0].length;
        }

        element.appendChild(document.createTextNode(text.slice(lastIndex)));
    }

    function appendFormattedText(container, text) {
        const lines = text.split('\n');
        let activeList = null;
        let activeListType = null;

        lines.forEach(line => {
            const listMatch = line.match(/^\s*(?:([-+•])|(\d+)[.)])\s+(.+)$/);
            if (listMatch) {
                const listType = listMatch[2] ? 'ol' : 'ul';
                if (!activeList || activeListType !== listType) {
                    activeList = document.createElement(listType);
                    activeListType = listType;
                    container.appendChild(activeList);
                }
                const item = document.createElement('li');
                appendTextWithLinks(item, listMatch[3]);
                activeList.appendChild(item);
                return;
            }

            activeList = null;
            activeListType = null;
            if (!line.trim()) return;

            const paragraph = document.createElement('p');
            appendTextWithLinks(paragraph, line.trim());
            container.appendChild(paragraph);
        });
    }

    // Add a message to the chat
    function addMessage(message, isUser = false) {
        let cleanedMessage = message;
        if (!isUser) {
            cleanedMessage = sanitizeText(message);
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        const icon = document.createElement('i');
        icon.className = isUser ? 'fas fa-user' : 'fas fa-robot';
        avatar.appendChild(icon);
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        if (isUser) {
            const messageText = document.createElement('p');
            messageText.textContent = cleanedMessage;
            messageContent.appendChild(messageText);
        } else {
            appendFormattedText(messageContent, cleanedMessage);
        }
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(messageContent);
        chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Show typing indicator while waiting for response
    function showTypingIndicator() {
        const typingIndicator = document.createElement('div');
        typingIndicator.className = 'typing-indicator';
        typingIndicator.id = 'typing-indicator';
        typingIndicator.innerHTML = '<span></span><span></span><span></span>';
        chatMessages.appendChild(typingIndicator);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Hide typing indicator when response arrives
    function hideTypingIndicator() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    // Clean thinking content, emojis, and asterisks for speech synthesis
    function cleanThinkingContent(message) {
        const withoutLinks = message
            .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '$1')
            .replace(/https?:\/\/[^\s<]+/g, 'Click here');
        return sanitizeText(withoutLinks).replace(/\n+/g, ' ');
    }

    // Send a message to the Groq-powered API
    async function sendMessage(message) {
        try {
            const response = await fetch('/api/v1/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message
                }),
            });

            const data = await response.json();
            
            if (data.success) {
                // Store original response for possible debugging
                const originalResponse = data.response;
                
                // Add cleaned response to chat
                addMessage(data.response);
                
                // Return the cleaned response for speech synthesis
                return cleanThinkingContent(data.response);
            } else {
                console.error('API Error:', data.error);
                addMessage("I'm sorry, I encountered an error processing your request. Please try again.");
                return null;
            }
        } catch (error) {
            console.error('Error:', error);
            addMessage("I'm sorry, I couldn't connect to the server. Please try again later.");
            return null;
        }
    }

    // Check API status and update indicator
    async function checkApiStatus() {
        try {
            const response = await fetch('/api/v1/models');
            if (response.ok) {
                const data = await response.json();
                
                if (statusIndicator) {
                    if (data.using_groq && data.groq_api_configured) {
                        statusIndicator.innerHTML = `<span class="status-dot online"></span> Using Groq: ${data.groq_model}`;
                        statusIndicator.classList.remove('offline');
                        statusIndicator.classList.add('online');
                    } else {
                        statusIndicator.innerHTML = '<span class="status-dot offline"></span> API Not Configured';
                        statusIndicator.classList.remove('online');
                        statusIndicator.classList.add('offline');
                    }
                }
            }
        } catch (error) {
            console.error('Failed to check API status:', error);
            if (statusIndicator) {
                statusIndicator.innerHTML = '<span class="status-dot offline"></span> API Offline';
                statusIndicator.classList.remove('online');
                statusIndicator.classList.add('offline');
            }
        }
    }

    // Handle form submission
    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const message = userInput.value.trim();
        if (!message) return;
        
        // Add user message to chat
        addMessage(message, true);
        
        // Clear input
        userInput.value = '';
        
        // Show typing indicator
        showTypingIndicator();
        
        // Send message and get response
        await sendMessage(message);
        
        // Hide typing indicator
        hideTypingIndicator();
    });

    // Check API status on page load and periodically
    checkApiStatus();
    setInterval(checkApiStatus, 30000);
    
    // Make these functions accessible globally for voice.js
    window.addMessage = addMessage;
    window.cleanThinkingContent = cleanThinkingContent;
});