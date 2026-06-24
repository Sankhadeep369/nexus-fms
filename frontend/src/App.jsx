import { useEffect, useState } from "react";
import ChatInput from "./components/ChatInput";
import ChatWindow from "./components/ChatWindow";
import Header from "./components/Header";
import OptionsPanel from "./components/OptionsPanel";
import Sidebar from "./components/Sidebar";
import { ChatHistoryProvider, useChatHistory } from "./context/ChatHistoryContext";
import { ThemeProvider } from "./context/ThemeContext";
import { useChat } from "./hooks/useChat";

function Chat() {
  const { messages, isStreaming, sendMessage, regenerate, editAndResend, stopGeneration, mode, setMode } = useChat();
  const { activeConversation } = useChatHistory();

  useEffect(() => {
    document.title = activeConversation.title === "New chat" ? "NEXUS" : `${activeConversation.title} · NEXUS`;
  }, [activeConversation.title]);

  return (
    <div className="relative flex flex-1 flex-col overflow-hidden">
      <ChatWindow
        messages={messages}
        onSend={sendMessage}
        onRegenerate={regenerate}
        onEditResend={editAndResend}
        disabled={isStreaming}
      />
      <ChatInput
        onSend={sendMessage}
        onStop={stopGeneration}
        isStreaming={isStreaming}
        mode={mode}
        onModeChange={setMode}
      />
    </div>
  );
}

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [optionsOpen, setOptionsOpen] = useState(false);

  return (
    <ThemeProvider>
      <ChatHistoryProvider>
        <div className="relative flex h-screen flex-col">
          <div className="aurora" aria-hidden="true" />
          <Header
            onToggleSidebar={() => setSidebarCollapsed((c) => !c)}
            onToggleOptions={() => setOptionsOpen(true)}
          />
          <div className="flex flex-1 overflow-hidden">
            <Sidebar collapsed={sidebarCollapsed} />
            <Chat />
          </div>
          <OptionsPanel open={optionsOpen} onClose={() => setOptionsOpen(false)} />
        </div>
      </ChatHistoryProvider>
    </ThemeProvider>
  );
}
