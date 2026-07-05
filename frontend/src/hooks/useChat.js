import { useCallback, useEffect, useRef, useState } from "react";
import { useChatHistory } from "../context/ChatHistoryContext";
import { parseSSEStream } from "../lib/sse";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

const ARTIFACT_PATTERNS = [
  /\n*This response was assembled from[\s\S]*/i,
  /\n*End of template use[\s\S]*/i,
  /\n*Do not reuse this formatted text[\s\S]*/i,
  /\n*Note:\s*This (?:response|answer|output) (?:was|is)[\s\S]{0,300}template[\s\S]*/i,
];

function stripArtifacts(text) {
  let result = text;
  for (const p of ARTIFACT_PATTERNS) result = result.replace(p, "");
  return result.trimEnd();
}

// Cached answers can return almost instantly. Hold them behind the "thinking"
// indicator for at least this long so the UI doesn't feel like it skipped a step.
const MIN_THINKING_MS = 600;

export const STEP_LABELS = {
  cache_lookup: "Checking cache",
  query_analysis: "Analysing query",
  retrieval: "Searching documents",
  agent_research: "Researching vendor & market data",
  incident_triage: "Triaging incident — classifying, finding vendor, checking SLA",
  synthesis: "Synthesising comparison",
  verification: "Verifying answer",
  generation: "Generating answer",
  refinement: "Refining answer",
};

function newId() {
  return crypto.randomUUID();
}

function freshAssistant(id) {
  return {
    id,
    role: "assistant",
    content: "",
    steps: [],
    cacheHit: null,
    latencyMs: null,
    sources: [],
    agentSynthesized: false,
    agentToolCalls: [],
    isStreaming: true,
    error: null,
    stopped: false,
    clarificationOptions: [],
    originalQuery: "",
  };
}

export function useChat() {
  const { activeId, activeConversation, commitMessages } = useChatHistory();
  const [messages, setMessages] = useState(activeConversation.messages);
  const [isStreaming, setIsStreaming] = useState(false);
  const [mode, setMode] = useState("simple");
  const conversationIdRef = useRef(activeId);
  const abortControllerRef = useRef(null);

  // Switching conversations swaps the working message list to the selected one.
  useEffect(() => {
    conversationIdRef.current = activeId;
    setMessages(activeConversation.messages);
  }, [activeId]); // eslint-disable-line react-hooks/exhaustive-deps

  const stopGeneration = useCallback(() => {
    abortControllerRef.current?.abort();
  }, []);

  // Sends `userMsg` (already appended to `baseMessages`) and streams the response
  // into a fresh assistant message identified by `assistantId`.
  const runStream = useCallback(
    async (baseMessages, userMsg, assistantId) => {
      const conversationId = conversationIdRef.current;
      const withUser = [...baseMessages, userMsg, freshAssistant(assistantId)];
      setMessages(withUser);
      commitMessages(conversationId, [...baseMessages, userMsg]);
      setIsStreaming(true);

      let finalMessages = withUser;
      const applyUpdate = (updater) => {
        setMessages((prev) => {
          const next = prev.map((m) => (m.id === assistantId ? updater(m) : m));
          finalMessages = next;
          return next;
        });
      };

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        // Send last max_history_turns * 2 messages as conversation context.
        // Exclude the fresh assistant placeholder we just appended.
        const historyMessages = [...baseMessages, userMsg]
          .filter((m) => m.role === "user" || (m.role === "assistant" && m.content))
          .slice(-8)
          .map(({ role, content }) => ({ role, content }));

        const response = await fetch(`${API_BASE}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: userMsg.content, mode, history: historyMessages }),
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`Request failed (${response.status})`);
        }

        const streamStart = Date.now();
        let cacheHit = false;
        let pendingContent = "";

        for await (const evt of parseSSEStream(response)) {
          const payload = JSON.parse(evt.data);

          if (payload.type === "step") {
            if (payload.name === "cache_lookup" && payload.status === "done") {
              cacheHit = Boolean(payload.detail?.hit);
            }
            applyUpdate((msg) => {
              const steps = [...msg.steps];
              const idx = steps.findIndex((s) => s.name === payload.name);
              const step = {
                name: payload.name,
                label: STEP_LABELS[payload.name] ?? payload.name,
                status: payload.status,
                detail: payload.detail,
              };
              if (idx === -1) steps.push(step);
              else steps[idx] = step;
              return { ...msg, steps };
            });
          } else if (payload.type === "token") {
            if (cacheHit) {
              // Buffer cached output so it doesn't flash in instantly.
              pendingContent += payload.text;
            } else {
              applyUpdate((msg) => ({ ...msg, content: msg.content + payload.text }));
            }
          } else if (payload.type === "done") {
            if (cacheHit) {
              const elapsed = Date.now() - streamStart;
              if (elapsed < MIN_THINKING_MS) {
                await new Promise((resolve) => setTimeout(resolve, MIN_THINKING_MS - elapsed));
              }
              applyUpdate((msg) => ({ ...msg, content: msg.content + pendingContent }));
            }
            if (payload.needs_clarification) {
              applyUpdate((msg) => ({
                ...msg,
                content: payload.clarification_question ?? payload.final_answer ?? "",
                clarificationOptions: payload.clarification_options ?? [],
                originalQuery: userMsg.content,
                latencyMs: payload.latency_ms?.total ?? null,
                isStreaming: false,
              }));
            } else if (payload.valid === false) {
              applyUpdate((msg) => ({
                ...msg,
                content: payload.fallback ?? "NEXUS couldn't produce a reliable answer. Please try rephrasing.",
                latencyMs: payload.latency_ms?.total ?? null,
                cacheHit: null,
                sources: [],
                validationFailed: true,
                isStreaming: false,
              }));
            } else {
              // Prefer final_answer (Groq-rewritten) over raw streamed content.
              // On cache hits, final_answer equals the cached text; on fresh
              // generations it is the Groq-cleaned version of what was streamed.
              applyUpdate((msg) => ({
                ...msg,
                content: payload.final_answer
                  ? stripArtifacts(payload.final_answer)
                  : stripArtifacts(msg.content),
                latencyMs: payload.latency_ms?.total ?? null,
                cacheHit: payload.cache_hit ?? null,
                sources: payload.retrieved_sources ?? [],
                agentSynthesized: payload.agent_synthesized ?? false,
                agentToolCalls: payload.agent_tool_calls ?? [],
                isStreaming: false,
              }));
            }
          }
        }
      } catch (err) {
        if (err.name === "AbortError") {
          applyUpdate((msg) => ({ ...msg, isStreaming: false, stopped: true }));
        } else {
          applyUpdate((msg) => ({ ...msg, isStreaming: false, error: err.message }));
        }
      } finally {
        abortControllerRef.current = null;
        setIsStreaming(false);
        commitMessages(conversationId, finalMessages);
      }
    },
    [commitMessages, mode]
  );

  const sendMessage = useCallback(
    (query) => {
      const trimmed = query.trim();
      if (!trimmed || isStreaming) return;
      const userMsg = { id: newId(), role: "user", content: trimmed };
      runStream(messages, userMsg, newId());
    },
    [isStreaming, messages, runStream]
  );

  // Re-runs the user message that produced `assistantId`, replacing that answer.
  const regenerate = useCallback(
    (assistantId) => {
      if (isStreaming) return;
      const idx = messages.findIndex((m) => m.id === assistantId);
      if (idx <= 0) return;
      const userMsg = messages[idx - 1];
      if (userMsg.role !== "user") return;
      runStream(messages.slice(0, idx - 1), userMsg, assistantId);
    },
    [isStreaming, messages, runStream]
  );

  // Edits a previously sent user message and re-sends it, discarding everything
  // that came after it (including the old response).
  const editAndResend = useCallback(
    (userMsgId, newContent) => {
      const trimmed = newContent.trim();
      if (!trimmed || isStreaming) return;
      const idx = messages.findIndex((m) => m.id === userMsgId);
      if (idx === -1) return;
      const userMsg = { ...messages[idx], content: trimmed };
      runStream(messages.slice(0, idx), userMsg, newId());
    },
    [isStreaming, messages, runStream]
  );

  // Called when the user taps a clarification chip.  Combines the original
  // ambiguous query with the chosen scope so the full pipeline runs with
  // clear intent on the second pass.
  const clarify = useCallback(
    (originalQuery, selectedOption) => {
      sendMessage(`${originalQuery.trim()} — specifically: ${selectedOption}`);
    },
    [sendMessage]
  );

  return { messages, isStreaming, sendMessage, clarify, regenerate, editAndResend, stopGeneration, mode, setMode };
}
