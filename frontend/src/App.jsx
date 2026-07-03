import { useEffect, useState } from "react";
import AgentsPage from "./components/AgentsPage";
import ChatInput from "./components/ChatInput";
import ChatWindow from "./components/ChatWindow";
import Header from "./components/Header";
import OptionsPanel from "./components/OptionsPanel";
import Sidebar from "./components/Sidebar";
import { ChatHistoryProvider, useChatHistory } from "./context/ChatHistoryContext";
import { ThemeProvider } from "./context/ThemeContext";
import { useChat } from "./hooks/useChat";

function Chat({ prefill }) {
  const { messages, isStreaming, sendMessage, clarify, regenerate, editAndResend, stopGeneration, mode, setMode } = useChat();
  const { activeConversation } = useChatHistory();

  useEffect(() => {
    document.title = activeConversation.title === "New chat" ? "NEXUS" : `${activeConversation.title} · NEXUS`;
  }, [activeConversation.title]);

  return (
    <div className="relative flex flex-1 flex-col overflow-hidden">
      <ChatWindow
        messages={messages}
        onSend={sendMessage}
        onClarify={clarify}
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
        prefill={prefill}
      />
    </div>
  );
}

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [optionsOpen, setOptionsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("chat");
  const [chatPrefill, setChatPrefill] = useState(null);

  const askInChat = (text) => {
    setChatPrefill({ text, nonce: Date.now() });
    setActiveTab("chat");
  };

  return (
    <ThemeProvider>
      <ChatHistoryProvider>
        <div className="relative flex h-screen flex-col">
          <div className="aurora" aria-hidden="true" />
          <Header
            onToggleSidebar={() => setSidebarCollapsed((c) => !c)}
            onToggleOptions={() => setOptionsOpen(true)}
            activeTab={activeTab}
            onTabChange={setActiveTab}
          />
          <div className="flex flex-1 overflow-hidden">
            <Sidebar collapsed={sidebarCollapsed} />
            {activeTab === "chat" ? (
              <Chat prefill={chatPrefill} />
            ) : (
              <AgentsPage onAskVendorQuestion={askInChat} />
            )}
          </div>
          <OptionsPanel open={optionsOpen} onClose={() => setOptionsOpen(false)} />
        </div>
      </ChatHistoryProvider>
    </ThemeProvider>
  );
}
