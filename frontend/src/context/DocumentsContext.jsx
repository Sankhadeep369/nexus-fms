import { createContext, useCallback, useContext, useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const ACCEPT = /\.(pdf|docx?|txt|md|markdown)$/i;

// Document upload is an admin-only privilege that updates the shared knowledge base
// for every user, so it always targets the "global" owner (which retrieval treats as
// eligible for all users).
const GLOBAL_OWNER = "global";

const DocumentsContext = createContext(null);

export function DocumentsProvider({ children }) {
  const owner = GLOBAL_OWNER;
  const [documents, setDocuments] = useState([]);
  const [uploads, setUploads] = useState([]); // { id, name, status: "uploading"|"done"|"error", error }

  const refresh = useCallback(() => {
    fetch(`${API_BASE}/documents?owner=${encodeURIComponent(owner)}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => Array.isArray(d) && setDocuments(d))
      .catch(() => {});
  }, [owner]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const upload = useCallback(
    async (file) => {
      if (!ACCEPT.test(file.name)) {
        return { ok: false, error: "Unsupported file (PDF, Word, TXT or MD only)." };
      }
      const id = `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      setUploads((u) => [{ id, name: file.name, status: "uploading" }, ...u]);
      try {
        const fd = new FormData();
        fd.append("file", file);
        fd.append("owner", owner);
        const res = await fetch(`${API_BASE}/documents`, { method: "POST", body: fd });
        if (!res.ok) {
          const d = await res.json().catch(() => ({}));
          throw new Error(d.detail || `Upload failed (${res.status})`);
        }
        setUploads((u) => u.map((x) => (x.id === id ? { ...x, status: "done" } : x)));
        refresh();
        return { ok: true };
      } catch (e) {
        setUploads((u) => u.map((x) => (x.id === id ? { ...x, status: "error", error: e.message } : x)));
        return { ok: false, error: e.message };
      }
    },
    [owner, refresh]
  );

  const remove = useCallback(
    async (docId) => {
      await fetch(`${API_BASE}/documents/${docId}?owner=${encodeURIComponent(owner)}`, {
        method: "DELETE",
      }).catch(() => {});
      refresh();
    },
    [owner, refresh]
  );

  const dismissUpload = (id) => setUploads((u) => u.filter((x) => x.id !== id));

  return (
    <DocumentsContext.Provider value={{ owner, documents, uploads, upload, remove, refresh, dismissUpload }}>
      {children}
    </DocumentsContext.Provider>
  );
}

export function useDocuments() {
  return useContext(DocumentsContext);
}
