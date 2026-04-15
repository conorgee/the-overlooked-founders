import { useState, useEffect } from "react";
import { Plus, Pencil, Trash2, X, Check } from "lucide-react";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Textarea } from "../ui/Textarea";
import { SERVICE_URL, apiHeaders } from "../../lib/api";

interface KnowledgeEntry {
  id: string;
  title: string;
  sourceType: string;
  sourceUrl: string | null;
  chunkCount: number;
  topicTags: string[];
  preview: string;
  fullContent: string;
}

interface FormData {
  title: string;
  sourceType: string;
  sourceUrl: string;
  topicTags: string;
  content: string;
}

const emptyForm: FormData = {
  title: "",
  sourceType: "article",
  sourceUrl: "",
  topicTags: "",
  content: "",
};

const sourceTypes = ["podcast", "article", "tweet", "linkedin", "book", "interview"];

export function KnowledgeManager() {
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormData>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  useEffect(() => {
    fetchEntries();
  }, []);

  async function fetchEntries() {
    try {
      const res = await fetch(`${SERVICE_URL}/knowledge`, { headers: apiHeaders() });
      const data = await res.json();
      setEntries(Array.isArray(data) ? data : []);
    } catch {
      setEntries([]);
    }
    setLoading(false);
  }

  function startEdit(entry: KnowledgeEntry) {
    setEditingId(entry.id);
    setForm({
      title: entry.title || "",
      sourceType: entry.sourceType || "article",
      sourceUrl: entry.sourceUrl || "",
      topicTags: (entry.topicTags || []).join(", "),
      content: entry.fullContent || "",
    });
    setShowForm(true);
    setError("");
  }

  function startAdd() {
    setEditingId(null);
    setForm(emptyForm);
    setShowForm(true);
    setError("");
  }

  function cancelForm() {
    setShowForm(false);
    setEditingId(null);
    setForm(emptyForm);
    setError("");
  }

  async function handleSave() {
    if (!form.title.trim() || !form.content.trim()) {
      setError("Title and content are required");
      return;
    }

    setSaving(true);
    setError("");
    const tags = form.topicTags
      .split(",")
      .map((t) => t.trim().toLowerCase())
      .filter(Boolean);

    const body = {
      title: form.title.trim(),
      sourceType: form.sourceType,
      sourceUrl: form.sourceUrl.trim() || null,
      topicTags: tags,
      content: form.content.trim(),
    };

    try {
      const url = editingId
        ? `${SERVICE_URL}/ingest-knowledge/${editingId}`
        : `${SERVICE_URL}/ingest-knowledge`;

      const res = await fetch(url, {
        method: editingId ? "PUT" : "POST",
        headers: apiHeaders(),
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Save failed");
      }

      cancelForm();
      fetchEntries();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(entry: KnowledgeEntry) {
    try {
      await fetch(`${SERVICE_URL}/ingest-knowledge/${entry.id}`, {
        method: "DELETE",
        headers: apiHeaders(),
      });
    } catch {
      // ignore
    }
    setDeleteConfirm(null);
    fetchEntries();
  }

  if (loading) {
    return <p className="text-text-muted text-sm">Loading knowledge base...</p>;
  }

  return (
    <div>
      {/* Add button */}
      {!showForm && (
        <button
          onClick={startAdd}
          className="flex items-center gap-2 text-xs uppercase tracking-[0.1em] bg-accent/20 text-accent px-4 py-2.5 hover:bg-accent/30 transition-all mb-6"
        >
          <Plus className="w-3 h-3" />
          Add Knowledge Entry
        </button>
      )}

      {/* Add/Edit form */}
      {showForm && (
        <div className="bg-dark-card p-6 mb-6 border border-white/10">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-white text-sm font-medium">
              {editingId ? "Edit Entry" : "Add Knowledge Entry"}
            </h3>
            <button onClick={cancelForm} className="text-text-muted hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid sm:grid-cols-2 gap-4 mb-4">
            <Input
              label="Source Title"
              placeholder="e.g. Podcast Ep 42: Growth Hacking"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
            <div>
              <label className="block text-[10px] uppercase tracking-[0.2em] text-text-subtle mb-2">
                Source Type
              </label>
              <select
                value={form.sourceType}
                onChange={(e) => setForm({ ...form, sourceType: e.target.value })}
                className="w-full bg-transparent text-white text-sm border-b border-white/20 pb-2 focus:border-white outline-none"
              >
                {sourceTypes.map((t) => (
                  <option key={t} value={t} className="bg-black">
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="mb-4">
            <Input
              label="Topic Tags (comma-separated)"
              placeholder="e.g. pricing, business model, revenue"
              value={form.topicTags}
              onChange={(e) => setForm({ ...form, topicTags: e.target.value })}
            />
          </div>

          <div className="mb-4">
            <Textarea
              label="Content"
              placeholder="Paste the knowledge content here — long content will be automatically chunked..."
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
            />
          </div>

          <div className="mb-4">
            <Input
              label="Source URL (optional)"
              placeholder="https://..."
              value={form.sourceUrl}
              onChange={(e) => setForm({ ...form, sourceUrl: e.target.value })}
            />
          </div>

          {error && <p className="text-red-400 text-xs mb-3">{error}</p>}

          <div className="flex items-center gap-3">
            <Button size="sm" onClick={handleSave} disabled={saving}>
              {saving ? "Processing..." : editingId ? "Update Entry" : "Save Entry"}
            </Button>
            <Button size="sm" variant="ghost" onClick={cancelForm}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Entry list */}
      {entries.length === 0 ? (
        <p className="text-text-muted text-sm">No knowledge entries yet.</p>
      ) : (
        <div className="space-y-3">
          {entries.map((entry) => (
            <div key={entry.id} className="bg-dark-card p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1.5">
                    <p className="text-white text-sm font-medium">
                      {entry.title || "Untitled"}
                    </p>
                    {entry.sourceType && (
                      <span className="text-[10px] uppercase tracking-[0.15em] px-2 py-0.5 text-accent bg-accent/10">
                        {entry.sourceType}
                      </span>
                    )}
                    {entry.chunkCount > 1 && (
                      <span className="text-[10px] uppercase tracking-[0.15em] px-2 py-0.5 text-blue-400 bg-blue-400/10">
                        {entry.chunkCount} chunks
                      </span>
                    )}
                  </div>

                  {entry.topicTags && entry.topicTags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {entry.topicTags.map((tag) => (
                        <span
                          key={tag}
                          className="text-[10px] text-text-subtle border border-white/10 px-1.5 py-0.5"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}

                  <p className="text-text-muted text-xs leading-relaxed line-clamp-2">
                    {entry.preview}
                  </p>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    onClick={() => startEdit(entry)}
                    className="p-2 text-text-muted hover:text-white transition-colors"
                    title="Edit"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>

                  {deleteConfirm === entry.id ? (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleDelete(entry)}
                        className="p-2 text-red-400 hover:text-red-300 transition-colors"
                        title="Confirm delete"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(null)}
                        className="p-2 text-text-muted hover:text-white transition-colors"
                        title="Cancel"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setDeleteConfirm(entry.id)}
                      className="p-2 text-text-muted hover:text-red-400 transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
