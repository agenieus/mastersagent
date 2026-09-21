"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { Conversation, Message } from "@/lib/types";
import Sidebar from "@/components/Sidebar";
import MessageBubble, { TypingIndicator } from "@/components/MessageBubble";
import ChatInput from "@/components/ChatInput";
import MemoryPanel from "@/components/MemoryPanel";
import MemoryBadge from "@/components/MemoryBadge";
import styles from "./chat.module.css";

// Extended Message type to hold client-side memory count
interface ChatMessage extends Message {
  memoryCount?: number;
}

export default function ChatPage() {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [isMemoryPanelOpen, setIsMemoryPanelOpen] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Authentication check
  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [user, isLoading, router]);

  // Load conversations
  useEffect(() => {
    if (user) {
      loadConversations();
    }
  }, [user]);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent, isStreaming]);

  const loadConversations = async () => {
    try {
      const convs = await api.conversations.list();
      setConversations(convs);
    } catch (err) {
      console.error("Failed to load conversations:", err);
    }
  };

  const selectConversation = async (id: number) => {
    setActiveConvId(id);
    try {
      const msgs = await api.conversations.getMessages(id);
      setMessages(msgs);
    } catch (err) {
      console.error("Failed to load messages:", err);
    }
  };

  const startNewChat = async () => {
    try {
      const newConv = await api.conversations.create();
      setConversations([newConv, ...conversations]);
      setActiveConvId(newConv.id);
      setMessages([]);
    } catch (err) {
      console.error("Failed to create conversation:", err);
    }
  };

  const handleSend = async (content: string) => {
    if (!activeConvId && conversations.length === 0) {
      await startNewChat();
      // Wait for React state to update before sending (hacky, but works for now)
      setTimeout(() => handleSend(content), 100);
      return;
    }

    const targetConvId = activeConvId || conversations[0].id;

    // Optimistically add user message
    const optimisticUserMsg: ChatMessage = {
      id: Date.now(),
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUserMsg]);
    setIsStreaming(true);
    setStreamingContent("");

    try {
      await api.chat.stream(
        targetConvId,
        content,
        (token) => setStreamingContent((prev) => prev + token),
        (memoryCount) => {
          // Done! We need to reload messages to get the real DB IDs
          setIsStreaming(false);
          // Load messages and append memoryCount to the last one
          api.conversations.getMessages(targetConvId).then(msgs => {
              if (msgs.length > 0 && memoryCount > 0) {
                  (msgs[msgs.length - 1] as ChatMessage).memoryCount = memoryCount;
              }
              setMessages(msgs);
          });
          loadConversations(); // refresh title if it was auto-generated
        },
        (err) => {
          console.error("Stream error:", err);
          setIsStreaming(false);
          alert("Error: " + err);
        }
      );
    } catch (err) {
      console.error("Failed to send message:", err);
      setIsStreaming(false);
    }
  };

  if (isLoading || !user) return null;

  return (
    <div className={styles.layout}>
      <Sidebar
        conversations={conversations}
        activeId={activeConvId}
        onSelect={selectConversation}
        onNewChat={startNewChat}
      />

      <div className={styles.mainArea}>
        <div style={{ position: "absolute", top: "1rem", right: "2rem", zIndex: 10, display: "flex", gap: "1rem" }}>
          <button
            onClick={() => setIsMemoryPanelOpen(!isMemoryPanelOpen)}
            style={{ color: "var(--accent-color)", fontSize: "0.875rem", background: "none", border: "1px solid var(--accent-color)", padding: "4px 8px", borderRadius: "4px", cursor: "pointer" }}
          >
            🧠 Memory {isMemoryPanelOpen ? "Close" : "Panel"}
          </button>
          <button
            onClick={() => { logout(); router.push("/"); }}
            style={{ color: "var(--text-muted)", fontSize: "0.875rem", background: "none", border: "none", cursor: "pointer" }}
          >
            Logout
          </button>
        </div>

        <div className={styles.chatWindow}>
          {messages.length === 0 && !isStreaming ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}>✨</div>
              <h2>How can I help you today?</h2>
              <p>Send a message to start a new conversation.</p>
            </div>
          ) : (
            <>
              {messages.map((msg) => (
                <div key={msg.id} style={{ display: "flex", flexDirection: "column", alignItems: msg.role === "assistant" ? "flex-start" : "flex-end" }}>
                  {msg.role === "assistant" && msg.memoryCount && msg.memoryCount > 0 && (
                    <MemoryBadge count={msg.memoryCount} />
                  )}
                  <MessageBubble message={msg} />
                </div>
              ))}
              
              {isStreaming && (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
                  {streamingContent ? (
                    <MessageBubble
                      message={{
                        id: 0,
                        role: "assistant",
                        content: streamingContent,
                        created_at: "",
                      }}
                    />
                  ) : (
                    <TypingIndicator />
                  )}
                </div>
              )}
            </>
          )}
          <div ref={messagesEndRef} />
        </div>

        <ChatInput onSend={handleSend} disabled={isStreaming} />
      </div>

      <MemoryPanel isOpen={isMemoryPanelOpen} onClose={() => setIsMemoryPanelOpen(false)} />
    </div>
  );
}
