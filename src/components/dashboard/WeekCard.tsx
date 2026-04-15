import { useState, useRef } from "react";
import { Upload, Check, Loader2, MessageSquare } from "lucide-react";
import ReactMarkdown from "react-markdown";
import type { ProgramWeek, Submission } from "../../lib/types";
import { SERVICE_URL, apiHeaders } from "../../lib/api";
import { Button } from "../ui/Button";
import { supabase } from "../../lib/supabase";
import { useAuth } from "../../lib/auth";

interface WeekCardProps {
  week: ProgramWeek;
  submission?: Submission | null;
  onSubmitted?: () => void;
}

const statusLabels = {
  completed: "Completed",
  current: "In Progress",
  locked: "Locked",
};

function getVideoDuration(file: File): Promise<number> {
  return new Promise((resolve) => {
    const video = document.createElement("video");
    video.preload = "metadata";
    video.onloadedmetadata = () => {
      URL.revokeObjectURL(video.src);
      resolve(video.duration);
    };
    video.onerror = () => resolve(0);
    video.src = URL.createObjectURL(file);
  });
}

export function WeekCard({ week, submission, onSubmitted }: WeekCardProps) {
  const { user } = useAuth();
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [showFeedback, setShowFeedback] = useState(false);

  async function handleUpload(file: File) {
    if (!user) return;
    setUploading(true);
    setError("");

    // Validate file type
    if (file.type !== "video/mp4") {
      setError("Only MP4 files are accepted");
      setUploading(false);
      return;
    }

    // Validate duration (max 2 minutes)
    const duration = await getVideoDuration(file);
    if (duration > 120) {
      setError("Video must be 2 minutes or less");
      setUploading(false);
      return;
    }

    try {
      const ext = file.name.split(".").pop();
      const path = `weekly/${user.id}/week-${week.week}-${Date.now()}.${ext}`;

      const { error: uploadErr } = await supabase.storage
        .from("video-pitches")
        .upload(path, file);

      if (uploadErr) throw new Error(uploadErr.message);

      const { data: urlData } = supabase.storage
        .from("video-pitches")
        .getPublicUrl(path);

      const { data: insertData, error: insertErr } = await supabase
        .from("weekly_submissions")
        .insert({
          user_id: user.id,
          week_number: week.week,
          video_url: urlData.publicUrl,
          status: "submitted",
        })
        .select("id")
        .single();

      if (insertErr) throw new Error(insertErr.message);

      // Fire-and-forget: trigger the feedback pipeline microservice
      if (insertData?.id) {
        fetch(`${SERVICE_URL}/process`, {
          method: "POST",
          headers: apiHeaders(),
          body: JSON.stringify({ submissionId: insertData.id }),
        }).catch(() => {}); // Don't block UI on pipeline errors
      }

      onSubmitted?.();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  const hasSubmission = !!submission;
  const hasFeedback = !!submission?.ai_response;

  return (
    <div
      className={`border-t border-white/10 py-8 ${
        week.status === "locked" ? "opacity-40" : ""
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <span className="text-xs uppercase tracking-[0.15em] text-text-subtle">
            Week {week.week}
          </span>
          <h3 className="text-xl font-medium text-white tracking-[-0.02em] mt-1">
            {week.title}
          </h3>
        </div>
        <span
          className={`text-xs uppercase tracking-[0.15em] ${
            week.status === "completed"
              ? "text-white"
              : week.status === "current"
              ? "text-white"
              : "text-text-subtle"
          }`}
        >
          {statusLabels[week.status]}
        </span>
      </div>

      <p className="text-text-muted text-[15px] leading-relaxed mb-4 max-w-2xl">
        {week.description}
      </p>

      <div className="flex flex-wrap gap-x-4 gap-y-1 mb-4">
        {week.topics.map((topic) => (
          <span key={topic} className="text-xs text-text-subtle">
            {topic}
          </span>
        ))}
      </div>

      {/* Submission area for current/completed weeks */}
      {week.status !== "locked" && (
        <>
          {hasSubmission ? (
            <div className="mt-6 border border-white/10 p-6">
              <div className="flex items-center gap-2 mb-3">
                <Check className="w-4 h-4 text-green-400" />
                <p className="text-sm text-white">Video submitted</p>
                <span className="text-xs text-text-subtle ml-auto">
                  {new Date(submission.created_at).toLocaleDateString("en-GB", {
                    day: "numeric",
                    month: "short",
                  })}
                </span>
              </div>

              {submission.video_url && (
                <video
                  src={submission.video_url}
                  controls
                  preload="metadata"
                  className="w-full rounded border border-white/10 mt-2"
                />
              )}

              {hasFeedback && (
                <div className="mt-4">
                  <button
                    onClick={() => setShowFeedback(!showFeedback)}
                    className="flex items-center gap-2 text-xs uppercase tracking-[0.1em] text-accent hover:text-accent-hover transition-colors"
                  >
                    <MessageSquare className="w-3 h-3" />
                    {showFeedback ? "Hide Feedback" : "View AI Feedback"}
                  </button>

                  {showFeedback && (
                    <div className="mt-4 p-5 bg-white/[0.03] border border-white/5">
                      <div className="prose-feedback text-text-muted text-sm leading-relaxed">
                        <ReactMarkdown
                          components={{
                            h1: ({ children }) => (
                              <h3 className="text-white text-base font-medium mt-5 mb-2 first:mt-0">{children}</h3>
                            ),
                            h2: ({ children }) => (
                              <h3 className="text-white text-base font-medium mt-5 mb-2 first:mt-0">{children}</h3>
                            ),
                            h3: ({ children }) => (
                              <h4 className="text-white text-sm font-medium mt-4 mb-1.5">{children}</h4>
                            ),
                            p: ({ children }) => (
                              <p className="text-text-muted text-sm leading-relaxed mb-3">{children}</p>
                            ),
                            strong: ({ children }) => (
                              <strong className="text-white font-medium">{children}</strong>
                            ),
                            ul: ({ children }) => (
                              <ul className="list-disc list-outside ml-4 mb-3 space-y-1.5">{children}</ul>
                            ),
                            ol: ({ children }) => (
                              <ol className="list-decimal list-outside ml-4 mb-3 space-y-1.5">{children}</ol>
                            ),
                            li: ({ children }) => (
                              <li className="text-text-muted text-sm leading-relaxed">{children}</li>
                            ),
                          }}
                        >
                          {submission.ai_response!.response_text}
                        </ReactMarkdown>
                      </div>
                      {submission.ai_response!.sources_cited &&
                        submission.ai_response!.sources_cited.length > 0 && (
                          <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-white/5">
                            {submission.ai_response!.sources_cited.map((s) => (
                              <span
                                key={s}
                                className="text-[10px] text-text-subtle border border-white/10 px-2 py-0.5"
                              >
                                {s}
                              </span>
                            ))}
                          </div>
                        )}
                    </div>
                  )}
                </div>
              )}

              {!hasFeedback && (submission.status === "submitted" || submission.status === "processing") && (
                <p className="text-xs text-text-subtle mt-3">
                  {submission.status === "processing"
                    ? "AI is analyzing your video..."
                    : "AI feedback will be generated shortly..."}
                </p>
              )}
            </div>
          ) : week.status === "current" ? (
            <div className="mt-6 border border-dashed border-white/10 p-8 flex flex-col items-center">
              <Upload className="w-6 h-6 text-text-subtle mb-3" />
              <p className="text-text-muted text-sm mb-4">
                Upload your weekly video update (MP4, max 2 min)
              </p>

              {error && (
                <p className="text-red-400 text-xs mb-3">{error}</p>
              )}

              <input
                ref={fileRef}
                type="file"
                accept="video/mp4,.mp4"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleUpload(file);
                }}
              />

              <Button
                size="sm"
                onClick={() => fileRef.current?.click()}
                disabled={uploading}
              >
                {uploading ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  "Upload Video"
                )}
              </Button>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
