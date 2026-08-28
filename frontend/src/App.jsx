import { useEffect, useRef, useState } from "react";
import AdminPanel from "./components/AdminPanel";
import AgentsPage from "./components/AgentsPage";
import AnalysisPage from "./components/AnalysisPage";
import ChatInput from "./components/ChatInput";
import ChatSidePanel from "./components/ChatSidePanel";
import ChatWindow from "./components/ChatWindow";
import DashboardPage from "./components/DashboardPage";
import DocumentsPanel from "./components/DocumentsPanel";
import GuidedTour from "./components/GuidedTour";
import Header from "./components/Header";
import HelpCenter from "./components/HelpCenter";
import HomePage from "./components/HomePage";
import LoginScreen from "./components/LoginScreen";
import OptionsPanel from "./components/OptionsPanel";
import ProfilePanel from "./components/ProfilePanel";
import Sidebar from "./components/Sidebar";
import { UploadIcon } from "./components/icons";
import { AppConfigProvider, useAppConfig } from "./context/AppConfigContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ChatHistoryProvider, useChatHistory } from "./context/ChatHistoryContext";
import { DensityProvider } from "./context/DensityContext";
import { DocumentsProvider, useDocuments } from "./context/DocumentsContext";
import { LanguageProvider } from "./context/LanguageContext";
import { ProfileProvider } from "./context/ProfileContext";
import { ThemeProvider } from "./context/ThemeContext";
import { useChat } from "./hooks/useChat";

const GUIDE_SEEN_KEY = "nexus-guide-seen";

function Chat({ prefill, onOpenGuide, onExample, onOpenDocuments, canDocuments }) {
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
    if (!canDocuments || !e.dataTransfer?.types?.includes("Files")) return;
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
    if (!canDocuments) return;
    const files = Array.from(e.dataTransfer?.files ?? []);
    if (files.length) {
      files.forEach(upload); // add to the knowledge base (validated in DocumentsContext)
      onOpenDocuments();
    }
  };

  return (
    <div
      className="relative flex flex-1 overflow-hidden"
      onDragEnter={onDragEnter}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
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
          showDocuments={canDocuments}
        />
      </div>
      <ChatSidePanel messages={messages} onSend={sendMessage} onFeedback={sendFeedback} disabled={isStreaming} />
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

function Shell() {
  const { canTool, isAdmin } = useAuth();
  const { featureEnabled, announcement } = useAppConfig();
  const { createConversation } = useChatHistory();
  const allow = (id) => canTool(id) && featureEnabled(id);

  // Start collapsed on phones so the sidebar (an overlay drawer there) doesn't
  // cover the chat on first load; expanded on desktop where it sits inline.
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => typeof window !== "undefined" && window.innerWidth < 768
  );
  const [optionsOpen, setOptionsOpen] = useState(false);
  const [help, setHelp] = useState({ open: false, section: "getting-started" });
  const [tourOpen, setTourOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const openHelp = (section = "getting-started") => setHelp({ open: true, section });
  const [documentsOpen, setDocumentsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("chat");
  const [chatPrefill, setChatPrefill] = useState(null);
  const [analysisPrefill, setAnalysisPrefill] = useState(null);

  const canDocuments = allow("documents");
  const allowed = ["home", ...["chat", "agents", "analysis", "dashboard"].filter(allow)];
  if (isAdmin) allowed.push("admin");
  const effectiveTab = allowed.includes(activeTab) ? activeTab : allowed[0];

  // Run the guided tour once, automatically, on a user's first visit.
  useEffect(() => {
    if (!localStorage.getItem(GUIDE_SEEN_KEY)) {
      setTourOpen(true);
      localStorage.setItem(GUIDE_SEEN_KEY, "1");
    }
  }, []);

  const prefillChat = (text) => {
    setChatPrefill({ text, nonce: Date.now() });
    setActiveTab("chat");
  };
  // Agents answer in their own fresh thread so the user's current chat is untouched.
  const askInNewConversation = (text) => {
    createConversation();
    setChatPrefill({ text, nonce: Date.now(), autoSend: true });
    setActiveTab("chat");
  };
  const investigateKpi = (text) => {
    setAnalysisPrefill({ text, nonce: Date.now() });
    setActiveTab("analysis");
  };

  return (
    <div className="relative flex h-screen flex-col">
      <div className="aurora" aria-hidden="true" />
      <Header
        onToggleSidebar={() => setSidebarCollapsed((c) => !c)}
        onToggleOptions={() => setOptionsOpen(true)}
        onOpenHelp={() => openHelp("getting-started")}
        activeTab={effectiveTab}
        onTabChange={setActiveTab}
      />
      {announcement?.enabled && announcement.text && (
        <div className={`shrink-0 px-4 py-2 text-center text-xs font-medium ${announcement.level === "warn" ? "bg-amber-500/15 text-amber-300" : "bg-nexus-accent/10 text-nexus-accent"}`}>
          {announcement.text}
        </div>
      )}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          collapsed={sidebarCollapsed}
          onClose={() => setSidebarCollapsed(true)}
          onOpenProfile={() => setProfileOpen(true)}
        />
        {effectiveTab === "home" ? (
          <HomePage onNavigate={setActiveTab} onOpenProfile={() => setProfileOpen(true)} />
        ) : effectiveTab === "chat" ? (
          <Chat
            prefill={chatPrefill}
            onOpenGuide={() => openHelp("chat")}
            onExample={prefillChat}
            onOpenDocuments={() => setDocumentsOpen(true)}
            canDocuments={canDocuments}
          />
        ) : effectiveTab === "analysis" ? (
          <AnalysisPage prefill={analysisPrefill} />
        ) : effectiveTab === "dashboard" ? (
          <DashboardPage onInvestigate={investigateKpi} />
        ) : effectiveTab === "admin" ? (
          <AdminPanel />
        ) : (
          <AgentsPage onAskVendorQuestion={askInNewConversation} onHelp={openHelp} />
        )}
      </div>
      <OptionsPanel open={optionsOpen} onClose={() => setOptionsOpen(false)} onOpenGuide={() => openHelp("getting-started")} />
      <ProfilePanel open={profileOpen} onClose={() => setProfileOpen(false)} />
      {canDocuments && <DocumentsPanel open={documentsOpen} onClose={() => setDocumentsOpen(false)} />}
      <HelpCenter
        open={help.open}
        section={help.section}
        onClose={() => setHelp((h) => ({ ...h, open: false }))}
        onStartTour={() => {
          setHelp((h) => ({ ...h, open: false }));
          setTourOpen(true);
        }}
      />
      {tourOpen && <GuidedTour onClose={() => setTourOpen(false)} />}
    </div>
  );
}

function Gate() {
  const { user } = useAuth();
  if (!user) return <LoginScreen />;
  return (
    <LanguageProvider>
      <DensityProvider>
        <ProfileProvider>
          <DocumentsProvider>
            <ChatHistoryProvider>
              <Shell />
            </ChatHistoryProvider>
          </DocumentsProvider>
        </ProfileProvider>
      </DensityProvider>
    </LanguageProvider>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AppConfigProvider>
        <AuthProvider>
          <Gate />
        </AuthProvider>
      </AppConfigProvider>
    </ThemeProvider>
  );
}
