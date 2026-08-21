import { useEffect, useRef, useState } from "react";
import AgentsPage from "./components/AgentsPage";
import AnalysisPage from "./components/AnalysisPage";
import DashboardPage from "./components/DashboardPage";
import ChatInput from "./components/ChatInput";
import ChatWindow from "./components/ChatWindow";
import DocumentsPanel from "./components/DocumentsPanel";
import GuideModal from "./components/GuideModal";
import Header from "./components/Header";
import OptionsPanel from "./components/OptionsPanel";
import ProfilePanel from "./components/ProfilePanel";
import Sidebar from "./components/Sidebar";
import { UploadIcon } from "./components/icons";
import { ChatHistoryProvider, useChatHistory } from "./context/ChatHistoryContext";
import { DensityProvider } from "./context/DensityContext";
import { DocumentsProvider, useDocuments } from "./context/DocumentsContext";
import { LanguageProvider } from "./context/LanguageContext";
import { ProfileProvider } from "./context/ProfileContext";
import { ThemeProvider } from "./context/ThemeContext";
import { useChat } from "./hooks/useChat";

const GUIDE_SEEN_KEY = "nexus-guide-seen";

function Chat({ prefill, onOpenGuide, onExample, onOpenDocuments }) {
  const { messages, isStreaming, sendMessage, clarify, regenerate, editAndResend, stopGeneration, sendFeedback, mode, setMode } = useChat();
  const { activeConversation } = useChatHistory();
  const { upload } = useDocuments();
  const [dragActive, setDragActive] = useState(false);
  const dragDepth = useRef(0);

  useEffect(() => {
    document.title = activeConversation.title === "New chat" ? "NEXUS" : `${activeConversation.title} · NEXUS`;
  }, [activeConversation.title]);

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
    const files = Array.from(e.dataTransfer?.files ?? []);
    if (files.length) {
      files.forEach(upload); // add to the knowledge base (validated in DocumentsContext)
      onOpenDocuments();
    }
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
        onFeedback={sendFeedback}
        onOpenGuide={onOpenGuide}
        onExample={onExample}
        mode={mode}
        disabled={isStreaming}
      />
      <ChatInput
        onSend={sendMessage}
        onStop={stopGeneration}
        isStreaming={isStreaming}
        mode={mode}
        onModeChange={setMode}
        prefill={prefill}
        onOpenDocuments={onOpenDocuments}
      />
      {dragActive && (
        <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center bg-nexus-bg/70 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-nexus-accent/60 bg-nexus-panel/80 px-8 py-6 text-center">
            <UploadIcon className="h-6 w-6 text-nexus-accent" />
            <p className="text-sm font-medium text-nexus-text">Drop files to add to your knowledge base</p>
            <p className="text-[11px] text-nexus-muted">PDF, Word, TXT, MD — searched in chat</p>
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
  const [guideOpen, setGuideOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [documentsOpen, setDocumentsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("chat");
  const [chatPrefill, setChatPrefill] = useState(null);
  const [analysisPrefill, setAnalysisPrefill] = useState(null);

  // Show the guide once, automatically, on a user's first visit.
  useEffect(() => {
    if (!localStorage.getItem(GUIDE_SEEN_KEY)) {
      setGuideOpen(true);
      localStorage.setItem(GUIDE_SEEN_KEY, "1");
    }
  }, []);

  const prefillChat = (text) => {
    setChatPrefill({ text, nonce: Date.now() });
    setActiveTab("chat");
  };

  const investigateKpi = (text) => {
    setAnalysisPrefill({ text, nonce: Date.now() });
    setActiveTab("analysis");
  };

  return (
    <ThemeProvider>
      <LanguageProvider>
        <DensityProvider>
          <ProfileProvider>
            <DocumentsProvider>
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
                    <Sidebar
                      collapsed={sidebarCollapsed}
                      onClose={() => setSidebarCollapsed(true)}
                      onOpenProfile={() => setProfileOpen(true)}
                    />
                    {activeTab === "chat" ? (
                      <Chat
                        prefill={chatPrefill}
                        onOpenGuide={() => setGuideOpen(true)}
                        onExample={prefillChat}
                        onOpenDocuments={() => setDocumentsOpen(true)}
                      />
                    ) : activeTab === "analysis" ? (
                      <AnalysisPage prefill={analysisPrefill} />
                    ) : activeTab === "dashboard" ? (
                      <DashboardPage onInvestigate={investigateKpi} />
                    ) : (
                      <AgentsPage onAskVendorQuestion={prefillChat} />
                    )}
                  </div>
                  <OptionsPanel
                    open={optionsOpen}
                    onClose={() => setOptionsOpen(false)}
                    onOpenGuide={() => setGuideOpen(true)}
                  />
                  <ProfilePanel open={profileOpen} onClose={() => setProfileOpen(false)} />
                  <DocumentsPanel open={documentsOpen} onClose={() => setDocumentsOpen(false)} />
                  <GuideModal open={guideOpen} onClose={() => setGuideOpen(false)} />
                </div>
              </ChatHistoryProvider>
            </DocumentsProvider>
          </ProfileProvider>
        </DensityProvider>
      </LanguageProvider>
    </ThemeProvider>
  );
}
