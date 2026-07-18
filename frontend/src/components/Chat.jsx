import { useState, useRef, useEffect } from "react";
import { useStream } from "../hooks/useStream";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Pre-built chat component with streaming AI responses.
 * Ready to demo immediately — customize the system prompt and styling
 * once the hackathon challenge is revealed.
 */
export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const { streamedText, isStreaming, startStream } = useStream();
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamedText]);

  // Update the assistant message in real time as tokens stream in
  useEffect(() => {
    if (isStreaming && streamedText) {
      setMessages((prev) => {
        const updated = [...prev];
        const lastMsg = updated[updated.length - 1];
        if (lastMsg && lastMsg.role === "assistant") {
          updated[updated.length - 1] = {
            ...lastMsg,
            content: streamedText,
          };
        }
        return updated;
      });
    }
  }, [streamedText, isStreaming]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userMessage = { role: "user", content: input.trim() };
    const newMessages = [...messages, userMessage];

    setMessages([...newMessages, { role: "assistant", content: "" }]);
    setInput("");
    inputRef.current?.focus();

    await startStream(`${API_URL}/api/chat`, {
      messages: newMessages,
    });
  };

  return (
    <div className="chat-container">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>✨ Ready to go. Type a message to start.</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message chat-message--${msg.role}`}>
            <div className="chat-message__role">
              {msg.role === "user" ? "You" : "AI"}
            </div>
            <div className="chat-message__content">
              {msg.content || (isStreaming && i === messages.length - 1 ? (
                <span className="chat-cursor">▍</span>
              ) : null)}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <form className="chat-input-form" onSubmit={handleSubmit}>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message..."
          disabled={isStreaming}
          autoFocus
        />
        <button type="submit" disabled={isStreaming || !input.trim()}>
          {isStreaming ? "..." : "Send"}
        </button>
      </form>
    </div>
  );
}
