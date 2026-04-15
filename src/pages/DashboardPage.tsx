import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { useEffect, useState, useCallback } from "react";
import { programWeeks } from "../data/program-weeks";
import { ProgressTracker } from "../components/dashboard/ProgressTracker";
import { WeekCard } from "../components/dashboard/WeekCard";
import { useAuth } from "../lib/auth";
import { supabase } from "../lib/supabase";
import type { Application, Submission } from "../lib/types";

type DashboardApplication = Pick<Application, "business_name" | "business_idea" | "status">;

export function DashboardPage() {
  const { user, profile } = useAuth();
  const [application, setApplication] = useState<DashboardApplication | null>(null);
  const [submissions, setSubmissions] = useState<Map<number, Submission>>(new Map());
  const [chatCount, setChatCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    if (!user) return;

    const [appRes, subRes, chatRes] = await Promise.all([
      supabase
        .from("applications")
        .select("business_name, business_idea, status")
        .eq("user_id", user.id)
        .order("created_at", { ascending: false })
        .limit(1)
        .maybeSingle(),
      supabase
        .from("weekly_submissions")
        .select("id, user_id, week_number, video_url, status, created_at")
        .eq("user_id", user.id)
        .order("created_at", { ascending: false }),
      supabase
        .from("chat_messages")
        .select("id", { count: "exact", head: true })
        .eq("user_id", user.id)
        .eq("role", "user"),
    ]);

    setApplication(appRes.data);
    setChatCount(chatRes.count ?? 0);

    // Build submissions map (latest per week)
    const subMap = new Map<number, Submission>();
    if (subRes.data) {
      // Fetch AI responses for all submissions
      const subIds = subRes.data.map((s) => s.id);
      let aiResponses: Record<string, { response_text: string; sources_cited: string[] | null }> = {};

      if (subIds.length > 0) {
        const { data: aiData } = await supabase
          .from("ai_responses")
          .select("submission_id, response_text, sources_cited")
          .in("submission_id", subIds);

        if (aiData) {
          for (const r of aiData) {
            aiResponses[r.submission_id] = {
              response_text: r.response_text,
              sources_cited: r.sources_cited,
            };
          }
        }
      }

      for (const s of subRes.data) {
        if (!subMap.has(s.week_number)) {
          subMap.set(s.week_number, {
            ...s,
            ai_response: aiResponses[s.id] || null,
          });
        }
      }
    }
    setSubmissions(subMap);
    setLoading(false);
  }, [user]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Poll every 10s while any submission is pending/processing
  useEffect(() => {
    const hasPending = Array.from(submissions.values()).some(
      (s) => s.status === "submitted" || s.status === "processing"
    );
    if (!hasPending) return;

    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [submissions, fetchData]);

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-6 lg:px-12 pt-32 pb-20">
        <p className="text-text-muted">Loading...</p>
      </div>
    );
  }

  const displayName = profile?.full_name || user?.email || "Founder";
  const businessLine = application?.business_name
    ? `${application.business_name}${application.business_idea ? ` — ${application.business_idea.slice(0, 60)}${application.business_idea.length > 60 ? "..." : ""}` : ""}`
    : null;

  const weeksCompleted = programWeeks.filter((w) => w.status === "completed").length;
  const submissionCount = submissions.size;

  return (
    <div className="max-w-4xl mx-auto px-6 lg:px-12 pt-32 pb-20">
      {/* Profile header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 mb-16">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-text-muted mb-3">
            Welcome back
          </p>
          <h1 className="text-3xl sm:text-4xl font-medium text-white tracking-[-0.04em]">
            {displayName}
          </h1>
          {businessLine && (
            <p className="text-text-muted text-[15px] mt-2">{businessLine}</p>
          )}
          {application && (
            <p className="text-xs uppercase tracking-[0.15em] text-accent mt-3">
              Application: {application.status.replace("_", " ")}
            </p>
          )}
        </div>
        <Link
          to="/ask"
          className="inline-flex items-center gap-2 border border-white/20 text-white px-5 py-2.5 text-xs uppercase tracking-[0.15em] font-medium hover:border-white/50 transition-all duration-300"
        >
          Ask a Mentor
          <ArrowRight className="w-3 h-3" />
        </Link>
      </div>

      <ProgressTracker />

      {/* Quick stats */}
      <div className="grid grid-cols-3 gap-px bg-white/5 mb-16">
        <div className="bg-black p-8 text-center">
          <p className="text-3xl font-medium text-white tracking-[-0.04em]">{weeksCompleted}</p>
          <p className="text-xs uppercase tracking-[0.15em] text-text-muted mt-2">Weeks Done</p>
        </div>
        <div className="bg-black p-8 text-center">
          <p className="text-3xl font-medium text-white tracking-[-0.04em]">{submissionCount}</p>
          <p className="text-xs uppercase tracking-[0.15em] text-text-muted mt-2">Videos Submitted</p>
        </div>
        <div className="bg-black p-8 text-center">
          <p className="text-3xl font-medium text-white tracking-[-0.04em]">{chatCount}</p>
          <p className="text-xs uppercase tracking-[0.15em] text-text-muted mt-2">Questions Asked</p>
        </div>
      </div>

      {/* Week cards */}
      <p className="text-xs uppercase tracking-[0.2em] text-text-muted mb-8">
        Your Programme
      </p>
      <div>
        {programWeeks.map((week) => (
          <WeekCard
            key={week.week}
            week={week}
            submission={submissions.get(week.week)}
            onSubmitted={fetchData}
          />
        ))}
      </div>
    </div>
  );
}
