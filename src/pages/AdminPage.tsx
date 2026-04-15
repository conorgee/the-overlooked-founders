import { useEffect, useState } from "react";
import { useAuth } from "../lib/auth";
import { supabase } from "../lib/supabase";
import { Navigate } from "react-router-dom";
import { ChevronDown, ChevronUp, RotateCw } from "lucide-react";
import { KnowledgeManager } from "../components/admin/KnowledgeManager";
import { SERVICE_URL, apiHeaders } from "../lib/api";
import type { Application, Submission } from "../lib/types";

interface Stats {
  totalApplications: number;
  pending: number;
  accepted: number;
  rejected: number;
  totalChats: number;
  totalSubmissions: number;
}

const stageLabels: Record<string, string> = {
  idea: "Just an idea",
  mvp: "Building MVP",
  launched: "Launched, early customers",
  growing: "Growing, looking to scale",
};

export function AdminPage() {
  const { profile, loading: authLoading } = useAuth();
  const [applications, setApplications] = useState<Application[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"applications" | "submissions" | "knowledge">("applications");
  const [stats, setStats] = useState<Stats>({
    totalApplications: 0,
    pending: 0,
    accepted: 0,
    rejected: 0,
    totalChats: 0,
    totalSubmissions: 0,
  });
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState<string | null>(null);

  async function retrySubmission(submissionId: string) {
    setRetrying(submissionId);
    try {
      await fetch(`${SERVICE_URL}/process`, {
        method: "POST",
        headers: apiHeaders(),
        body: JSON.stringify({ submissionId }),
      });
      // Refresh data after a short delay to pick up status change
      setTimeout(fetchData, 2000);
    } catch {
      // Silently fail — admin can try again
    } finally {
      setRetrying(null);
    }
  }

  useEffect(() => {
    if (!profile || profile.role !== "admin") return;
    fetchData();
  }, [profile]);

  async function fetchData() {
    const [appsRes, chatsRes, subsRes] = await Promise.all([
      supabase
        .from("applications")
        .select("*")
        .order("created_at", { ascending: false }),
      supabase
        .from("chat_messages")
        .select("id", { count: "exact", head: true })
        .eq("role", "user"),
      supabase
        .from("weekly_submissions")
        .select("id, user_id, week_number, video_url, status, created_at")
        .order("created_at", { ascending: false }),
    ]);

    const apps = appsRes.data || [];
    const subs = subsRes.data || [];

    // Fetch profile info for submissions
    if (subs.length > 0) {
      const userIds = [...new Set(subs.map((s) => s.user_id))];
      const { data: profiles } = await supabase
        .from("profiles")
        .select("id, full_name, email")
        .in("id", userIds);

      const profileMap = new Map(profiles?.map((p) => [p.id, p]) || []);
      for (const sub of subs) {
        (sub as Submission).profile = profileMap.get(sub.user_id) || null;
      }
    }

    setApplications(apps);
    setSubmissions(subs as Submission[]);
    setStats({
      totalApplications: apps.length,
      pending: apps.filter((a) => a.status === "pending").length,
      accepted: apps.filter((a) => a.status === "accepted").length,
      rejected: apps.filter((a) => a.status === "rejected").length,
      totalChats: chatsRes.count ?? 0,
      totalSubmissions: subs.length,
    });
    setLoading(false);
  }

  async function updateStatus(id: string, status: string) {
    await supabase.from("applications").update({ status }).eq("id", id);
    setApplications((prev) =>
      prev.map((a) => (a.id === id ? { ...a, status } : a))
    );
    setStats((prev) => {
      const old = applications.find((a) => a.id === id);
      if (!old) return prev;
      return {
        ...prev,
        [old.status]: (prev[old.status as keyof Stats] as number) - 1,
        [status]: (prev[status as keyof Stats] as number) + 1,
      };
    });
  }

  if (authLoading) return null;
  if (!profile || profile.role !== "admin") return <Navigate to="/" replace />;

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-6 lg:px-12 pt-32 pb-20">
        <p className="text-text-muted">Loading...</p>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-6 lg:px-12 pt-32 pb-20">
      <p className="text-xs uppercase tracking-[0.2em] text-text-muted mb-3">
        Admin
      </p>
      <h1 className="text-3xl sm:text-4xl font-medium text-white tracking-[-0.04em] mb-12">
        Platform Overview
      </h1>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-px bg-white/5 mb-16">
        {[
          { label: "Applications", value: stats.totalApplications },
          { label: "Pending", value: stats.pending },
          { label: "Accepted", value: stats.accepted },
          { label: "Submissions", value: stats.totalSubmissions },
          { label: "Questions Asked", value: stats.totalChats },
        ].map((s) => (
          <div key={s.label} className="bg-black p-6 text-center">
            <p className="text-3xl font-medium text-white tracking-[-0.04em]">
              {s.value}
            </p>
            <p className="text-xs uppercase tracking-[0.15em] text-text-muted mt-2">
              {s.label}
            </p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-6 mb-8 border-b border-white/10">
        <button
          onClick={() => { setActiveTab("applications"); setExpandedId(null); }}
          className={`pb-3 text-xs uppercase tracking-[0.15em] transition-colors ${
            activeTab === "applications"
              ? "text-white border-b border-white"
              : "text-text-muted hover:text-white"
          }`}
        >
          Applications ({applications.length})
        </button>
        <button
          onClick={() => { setActiveTab("submissions"); setExpandedId(null); }}
          className={`pb-3 text-xs uppercase tracking-[0.15em] transition-colors ${
            activeTab === "submissions"
              ? "text-white border-b border-white"
              : "text-text-muted hover:text-white"
          }`}
        >
          Weekly Submissions ({submissions.length})
        </button>
        <button
          onClick={() => { setActiveTab("knowledge"); setExpandedId(null); }}
          className={`pb-3 text-xs uppercase tracking-[0.15em] transition-colors ${
            activeTab === "knowledge"
              ? "text-white border-b border-white"
              : "text-text-muted hover:text-white"
          }`}
        >
          Knowledge Base
        </button>
      </div>

      {/* Submissions tab */}
      {activeTab === "submissions" && (
        submissions.length === 0 ? (
          <p className="text-text-muted text-sm">No submissions yet.</p>
        ) : (
          <div className="space-y-4">
            {submissions.map((sub) => (
              <div key={sub.id} className="bg-dark-card p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1">
                    <p className="text-white font-medium">
                      {sub.profile?.full_name || sub.profile?.email || "Unknown user"}
                    </p>
                    <span className="text-[10px] uppercase tracking-[0.15em] px-2 py-0.5 text-accent bg-accent/10">
                      Week {sub.week_number}
                    </span>
                    <span className={`text-[10px] uppercase tracking-[0.15em] px-2 py-0.5 ${
                      sub.status === "responded"
                        ? "text-green-400 bg-green-400/10"
                        : "text-text-muted bg-white/5"
                    }`}>
                      {sub.status}
                    </span>
                  </div>
                  <p className="text-text-subtle text-xs">
                    {new Date(sub.created_at).toLocaleDateString("en-GB", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {sub.status === "submitted" && (
                    <button
                      onClick={() => retrySubmission(sub.id)}
                      disabled={retrying === sub.id}
                      className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.1em] bg-amber-500/20 text-amber-400 px-3 py-2 hover:bg-amber-500/30 transition-all disabled:opacity-50"
                    >
                      <RotateCw className={`w-3 h-3 ${retrying === sub.id ? "animate-spin" : ""}`} />
                      {retrying === sub.id ? "Retrying..." : "Retry"}
                    </button>
                  )}
                  {sub.video_url && (
                    <div className="w-full mt-3">
                      <p className="text-[10px] uppercase tracking-[0.2em] text-text-subtle mb-2">
                        Submission Video
                      </p>
                      <video
                        src={sub.video_url}
                        controls
                        preload="metadata"
                        className="w-full max-w-lg rounded border border-white/10"
                      />
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {/* Knowledge Base tab */}
      {activeTab === "knowledge" && <KnowledgeManager />}

      {/* Applications tab */}
      {activeTab === "applications" && (applications.length === 0 ? (
        <p className="text-text-muted text-sm">No applications yet.</p>
      ) : (
        <div className="space-y-4">
          {applications.map((app) => {
            const isExpanded = expandedId === app.id;

            return (
              <div key={app.id} className="bg-dark-card">
                {/* Clickable header */}
                <button
                  onClick={() => setExpandedId(isExpanded ? null : app.id)}
                  className="w-full p-6 flex items-center justify-between gap-4 text-left hover:bg-white/[0.02] transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <p className="text-white font-medium">
                        {app.first_name} {app.last_name}
                      </p>
                      <span
                        className={`text-[10px] uppercase tracking-[0.15em] px-2 py-0.5 ${
                          app.status === "accepted"
                            ? "text-green-400 bg-green-400/10"
                            : app.status === "rejected"
                            ? "text-red-400 bg-red-400/10"
                            : "text-accent bg-accent/10"
                        }`}
                      >
                        {app.status}
                      </span>
                      {app.ai_score !== null && (
                        <span
                          className={`text-[10px] font-medium px-2 py-0.5 ${
                            app.ai_score >= 70
                              ? "text-green-400 bg-green-400/10"
                              : app.ai_score >= 40
                              ? "text-amber-400 bg-amber-400/10"
                              : "text-red-400 bg-red-400/10"
                          }`}
                        >
                          AI: {app.ai_score}/100
                        </span>
                      )}
                    </div>
                    <p className="text-text-muted text-sm">
                      {app.business_name || app.email}
                      {app.stage && ` — ${stageLabels[app.stage] || app.stage}`}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-text-subtle text-xs">
                      {new Date(app.created_at).toLocaleDateString("en-GB", {
                        day: "numeric",
                        month: "short",
                      })}
                    </span>
                    {isExpanded ? (
                      <ChevronUp className="w-4 h-4 text-text-muted" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-text-muted" />
                    )}
                  </div>
                </button>

                {/* Expanded detail view */}
                {isExpanded && (
                  <div className="px-6 pb-6 border-t border-white/5">
                    <div className="grid sm:grid-cols-2 gap-8 pt-6">
                      {/* Left column — applicant details */}
                      <div className="space-y-5">
                        <div>
                          <p className="text-[10px] uppercase tracking-[0.2em] text-text-subtle mb-1">
                            Full Name
                          </p>
                          <p className="text-white text-sm">
                            {app.first_name} {app.last_name}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] uppercase tracking-[0.2em] text-text-subtle mb-1">
                            Email
                          </p>
                          <p className="text-white text-sm">{app.email}</p>
                        </div>
                        {app.business_name && (
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.2em] text-text-subtle mb-1">
                              Business Name
                            </p>
                            <p className="text-white text-sm">{app.business_name}</p>
                          </div>
                        )}
                        {app.stage && (
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.2em] text-text-subtle mb-1">
                              Stage
                            </p>
                            <p className="text-white text-sm">
                              {stageLabels[app.stage] || app.stage}
                            </p>
                          </div>
                        )}
                        <div>
                          <p className="text-[10px] uppercase tracking-[0.2em] text-text-subtle mb-1">
                            Applied
                          </p>
                          <p className="text-white text-sm">
                            {new Date(app.created_at).toLocaleDateString("en-GB", {
                              day: "numeric",
                              month: "long",
                              year: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </p>
                        </div>
                      </div>

                      {/* Right column — business idea + media */}
                      <div className="space-y-5">
                        {app.business_idea && (
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.2em] text-text-subtle mb-1">
                              Business Idea
                            </p>
                            <p className="text-text-muted text-sm leading-relaxed">
                              {app.business_idea}
                            </p>
                          </div>
                        )}

                        {app.ai_summary && (
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.2em] text-text-subtle mb-1">
                              AI Assessment
                            </p>
                            <div className="bg-white/[0.03] border border-white/5 p-3">
                              {app.ai_score !== null && (
                                <span
                                  className={`inline-block text-xs font-medium px-2 py-0.5 mb-2 ${
                                    app.ai_score >= 70
                                      ? "text-green-400 bg-green-400/10"
                                      : app.ai_score >= 40
                                      ? "text-amber-400 bg-amber-400/10"
                                      : "text-red-400 bg-red-400/10"
                                  }`}
                                >
                                  Score: {app.ai_score}/100
                                </span>
                              )}
                              <p className="text-text-muted text-sm leading-relaxed">
                                {app.ai_summary}
                              </p>
                            </div>
                          </div>
                        )}

                        {app.video_pitch_url && (
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.2em] text-text-subtle mb-2">
                              Video Pitch
                            </p>
                            <video
                              src={app.video_pitch_url}
                              controls
                              preload="metadata"
                              className="w-full max-w-lg rounded border border-white/10"
                            />
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-3 mt-8 pt-6 border-t border-white/5">
                      {app.status === "pending" ? (
                        <>
                          <button
                            onClick={() => updateStatus(app.id, "accepted")}
                            className="text-xs uppercase tracking-[0.1em] bg-green-500/20 text-green-400 px-4 py-2.5 hover:bg-green-500/30 transition-all"
                          >
                            Accept Application
                          </button>
                          <button
                            onClick={() => updateStatus(app.id, "rejected")}
                            className="text-xs uppercase tracking-[0.1em] bg-red-500/20 text-red-400 px-4 py-2.5 hover:bg-red-500/30 transition-all"
                          >
                            Reject Application
                          </button>
                        </>
                      ) : (
                        <p className="text-xs text-text-subtle">
                          This application has been{" "}
                          <span
                            className={
                              app.status === "accepted"
                                ? "text-green-400"
                                : "text-red-400"
                            }
                          >
                            {app.status}
                          </span>
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
