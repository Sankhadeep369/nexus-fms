import { AnimatePresence, motion } from "framer-motion";
import { useRef, useState } from "react";
import { useDocuments } from "../context/DocumentsContext";
import { useProfile } from "../context/ProfileContext";
import { CheckIcon, FileTextIcon, TrashIcon, UploadIcon, XIcon } from "./icons";

const ACCEPT = ".pdf,.doc,.docx,.txt,.md,.markdown";

export default function DocumentsPanel({ open, onClose }) {
  const { documents, uploads, upload, remove, dismissUpload } = useDocuments();
  const { profile } = useProfile();
  const fileRef = useRef(null);
  const [drag, setDrag] = useState(false);

  const doUpload = (files) => Array.from(files ?? []).forEach((f) => upload(f));

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-30 bg-black/30"
            onClick={onClose}
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="scroll-thin fixed right-0 top-0 z-40 flex h-full w-96 max-w-[90vw] flex-col overflow-y-auto border-l border-nexus-border bg-nexus-panel p-4 shadow-2xl"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-nexus-text">Knowledge base</h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="rounded-lg p-1.5 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-nexus-text"
              >
                <XIcon className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-1 text-[11px] leading-relaxed text-nexus-muted">
              Uploaded files update the shared knowledge base for all users and are searched in
              chat — and take precedence over the built-in corpus when they overlap.
            </p>

            {/* Upload dropzone */}
            <input
              ref={fileRef}
              type="file"
              accept={ACCEPT}
              multiple
              className="hidden"
              onChange={(e) => {
                doUpload(e.target.files);
                e.target.value = "";
              }}
            />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              onDragEnter={(e) => {
                if (e.dataTransfer?.types?.includes("Files")) setDrag(true);
              }}
              onDragOver={(e) => e.preventDefault()}
              onDragLeave={() => setDrag(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDrag(false);
                if (e.dataTransfer?.files?.length) doUpload(e.dataTransfer.files);
              }}
              className={`mt-3 flex w-full flex-col items-center gap-1.5 rounded-xl border-2 border-dashed px-4 py-6 text-center transition-colors ${
                drag ? "border-nexus-accent bg-nexus-accent/5" : "border-nexus-border hover:border-nexus-accent/50"
              }`}
            >
              <UploadIcon className="h-5 w-5 text-nexus-accent" />
              <span className="text-sm font-medium text-nexus-text">Upload or drop files</span>
              <span className="text-[11px] text-nexus-muted">PDF, Word, TXT, MD · scanned PDFs are OCR&apos;d</span>
            </button>

            {/* In-progress / recent uploads */}
            {uploads.length > 0 && (
              <ul className="mt-3 space-y-1.5">
                {uploads.map((u) => (
                  <li
                    key={u.id}
                    className="flex items-center gap-2 rounded-lg border border-nexus-border bg-nexus-panel2 px-2.5 py-1.5 text-xs"
                  >
                    {u.status === "uploading" && (
                      <span className="h-3 w-3 shrink-0 animate-spin rounded-full border-2 border-nexus-accent border-t-transparent" />
                    )}
                    {u.status === "done" && <CheckIcon className="h-3.5 w-3.5 shrink-0 text-emerald-400" />}
                    {u.status === "error" && <XIcon className="h-3.5 w-3.5 shrink-0 text-red-400" />}
                    <span className="flex-1 truncate text-nexus-text">{u.name}</span>
                    <span className="shrink-0 text-nexus-muted">
                      {u.status === "uploading" ? "Processing…" : u.status === "done" ? "Added" : u.error}
                    </span>
                    {u.status !== "uploading" && (
                      <button
                        type="button"
                        onClick={() => dismissUpload(u.id)}
                        className="shrink-0 rounded p-0.5 text-nexus-muted hover:text-nexus-text"
                        aria-label="Dismiss"
                      >
                        <XIcon className="h-3 w-3" />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}

            {/* Document list */}
            <div className="mt-4 flex-1">
              {documents.length === 0 ? (
                <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-nexus-border py-8 text-center">
                  <FileTextIcon className="h-5 w-5 text-nexus-muted" />
                  <p className="text-xs text-nexus-muted">No documents yet.</p>
                </div>
              ) : (
                <ul className="space-y-2">
                  {documents.map((d) => (
                    <li
                      key={d.id}
                      className="flex items-start gap-2.5 rounded-xl border border-nexus-border bg-nexus-panel px-3 py-2.5"
                    >
                      <FileTextIcon className="mt-0.5 h-4 w-4 shrink-0 text-nexus-accent" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-nexus-text">{d.title || d.filename}</p>
                        {d.summary && <p className="mt-0.5 line-clamp-2 text-[11px] text-nexus-muted">{d.summary}</p>}
                        <p className="mt-0.5 text-[10px] text-nexus-muted">
                          {d.category || "General"} · {d.num_chunks} chunk{d.num_chunks === 1 ? "" : "s"}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => remove(d.id)}
                        title="Delete document"
                        className="shrink-0 rounded-lg p-1.5 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-red-400"
                      >
                        <TrashIcon className="h-3.5 w-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <p className="mt-3 border-t border-nexus-border pt-3 text-[11px] text-nexus-muted">
              {profile?.email
                ? `Saved to ${profile.email}`
                : "Guest — saved to this device only. Sign in to keep documents with your profile."}
            </p>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
