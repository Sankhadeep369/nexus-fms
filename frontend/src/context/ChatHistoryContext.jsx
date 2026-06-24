import { createContext, useContext, useEffect, useState } from "react";

const ChatHistoryContext = createContext(null);

const CONVERSATIONS_KEY = "nexus-conversations";
const ACTIVE_KEY = "nexus-active-conversation";
const TITLE_MAX_LEN = 40;

function newId() {
  return crypto.randomUUID();
}

function emptyConversation() {
  return { id: newId(), title: "New chat", messages: [], updatedAt: Date.now() };
}

function deriveTitle(messages) {
  const firstUser = messages.find((m) => m.role === "user");
  if (!firstUser) return "New chat";
  const text = firstUser.content.trim().replace(/\s+/g, " ");
  return text.length > TITLE_MAX_LEN ? `${text.slice(0, TITLE_MAX_LEN)}…` : text;
}

function loadConversations() {
  try {
    const raw = window.localStorage.getItem(CONVERSATIONS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (Array.isArray(parsed) && parsed.length > 0) return parsed;
  } catch {
    // ignore malformed storage
  }
  return [emptyConversation()];
}

function loadActiveId(conversations) {
  const stored = window.localStorage.getItem(ACTIVE_KEY);
  if (stored && conversations.some((c) => c.id === stored)) return stored;
  return conversations[0].id;
}

export function ChatHistoryProvider({ children }) {
  const [conversations, setConversations] = useState(loadConversations);
  const [activeId, setActiveId] = useState(() => loadActiveId(loadConversations()));

  useEffect(() => {
    window.localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations));
  }, [conversations]);

  useEffect(() => {
    window.localStorage.setItem(ACTIVE_KEY, activeId);
  }, [activeId]);

  const createConversation = () => {
    const conv = emptyConversation();
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.id);
    return conv.id;
  };

  const selectConversation = (id) => setActiveId(id);

  const deleteConversation = (id) => {
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id);
      if (next.length === 0) {
        const conv = emptyConversation();
        setActiveId(conv.id);
        return [conv];
      }
      if (id === activeId) setActiveId(next[0].id);
      return next;
    });
  };

  const commitMessages = (id, messages) => {
    setConversations((prev) =>
      prev.map((c) =>
        c.id === id
          ? { ...c, messages, updatedAt: Date.now(), title: c.title === "New chat" ? deriveTitle(messages) : c.title }
          : c
      )
    );
  };

  const clearAll = () => {
    const conv = emptyConversation();
    setConversations([conv]);
    setActiveId(conv.id);
  };

  const activeConversation = conversations.find((c) => c.id === activeId) ?? conversations[0];

  return (
    <ChatHistoryContext.Provider
      value={{
        conversations,
        activeConversation,
        activeId: activeConversation.id,
        createConversation,
        selectConversation,
        deleteConversation,
        commitMessages,
        clearAll,
      }}
    >
      {children}
    </ChatHistoryContext.Provider>
  );
}

export function useChatHistory() {
  const ctx = useContext(ChatHistoryContext);
  if (!ctx) throw new Error("useChatHistory must be used within a ChatHistoryProvider");
  return ctx;
}
