import { useEffect, useRef, useState } from "react";
import AgentsPage from "./components/AgentsPage";
import ChatInput from "./components/ChatInput";
import ChatWindow from "./components/ChatWindow";
import Header from "./components/Header";
import OptionsPanel from "./components/OptionsPanel";
import Sidebar from "./components/Sidebar";
import { PaperclipIcon } from "./components/icons";
import { ChatHistoryProvider, useChatHistory } from "./context/ChatHistoryContext";
import { ThemeProvider } from "./context/ThemeContext";
import { useChat } from "./hooks/useChat";

const DOC_EXT = /\.(pdf|docx?)$/i;

// Builds the display-only attachment records (nothing is uploaded). Filters to
// PDF/Word by extension and de-dupes so drag-drop and the picker stay in sync.
function toAttachments(fileList, existing) {
  const seen = new Set(existing.map((a) => a.id));
  return Array.from(fileList ?? [])
    .filter((f) => DOC_EXT.test(f.name))
    .map((f) => ({ id: `${f.name}-${f.size}-${f.lastModified}`, name: f.name, size: f.size }))
    .filter((a) => !seen.has(a.id));
}

function Chat({ prefill }) {
  const { messages, isStreaming, sendMessage, clarify, regenerate, editAndResend, stopGeneration, mode, setMode } = useChat();
  const { activeConversation } = useChatHistory();
  const [attachments, setAttachments] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const dragDepth = useRef(0);

  useEffect(() => {
    document.title = activeConversation.title === "New chat" ? "NEXUS" : `${activeConversation.title} · NEXUS`;
  }, [activeConversation.title]);

  const addFiles = (fileList) =>
    setAttachments((prev) => [...prev, ...toAttachments(fileList, prev)]);
  const removeAttachment = (id) => setAttachments((prev) => prev.filter((a) => a.id !== id));
  const clearAttachments = () => setAttachments([]);

  // Depth counter avoids the overlay flickering as the drag passes over children.
  const onDragEnter = (e) => {
    if (!e.dataTransfer?.types?.includes("Files")) return;
    dragDepth.current += 1;
    setDragActive(true);
  };
  const onDragLeave = () => {
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setDragActive(false);
  };
  const onDrop = (e) => {
    e.preventDefault();
    dragDepth.current = 0;
    setDragActive(false);
    if (e.dataTransfer?.files?.length) addFiles(e.dataTransfer.files);
  };

  return (
    <div
      className="relative flex flex-1 flex-col overflow-hidden"
      onDragEnter={onDragEnter}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
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
        attachments={attachments}
        onAddFiles={addFiles}
        onRemoveAttachment={removeAttachment}
        onClearAttachments={clearAttachments}
      />
      {dragActive && (
        <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center bg-nexus-bg/70 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-nexus-accent/60 bg-nexus-panel/80 px-8 py-6 text-center">
            <PaperclipIcon className="h-6 w-6 text-nexus-accent" />
            <p className="text-sm font-medium text-nexus-text">Drop PDF or Word documents to attach</p>
            <p className="text-[11px] text-nexus-muted">Preview only — documents are not read yet.</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function App() {
  // Start collapsed on phones so the sidebar (an overlay drawer there) doesn't
  // cover the chat on first load; expanded on desktop where it sits inline.
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => typeof window !== "undefined" && window.innerWidth < 768
  );
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
            <Sidebar collapsed={sidebarCollapsed} onClose={() => setSidebarCollapsed(true)} />
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
