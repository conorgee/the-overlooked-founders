import type { ChatMessage as ChatMessageType } from "../../lib/types";
import { SourceCitation } from "./SourceCitation";

interface ChatMessageProps {
  message: ChatMessageType;
  onFeedback?: (messageId: string, feedback: "helpful" | "not_helpful") => void;
}

export function ChatMessage({ message, onFeedback }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-4 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`w-8 h-8 flex items-center justify-center shrink-0 text-xs uppercase tracking-wider font-medium ${
          isUser ? "text-white" : "text-text-muted"
        }`}
      >
        {isUser ? "You" : "SB"}
      </div>

      <div className={`max-w-[80%] ${isUser ? "text-right" : ""}`}>
        <div
          className={`px-5 py-4 text-[15px] leading-relaxed ${
            isUser
              ? "bg-accent text-black"
              : "bg-dark-card text-white"
          }`}
        >
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>

        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {message.sources.map((source, i) => (
              <SourceCitation key={i} source={source} />
            ))}
          </div>
        )}

        {!isUser && message.messageId && (
          <div className="mt-2 flex gap-2 opacity-60 hover:opacity-100 transition-opacity">
            <button
              onClick={() => onFeedback?.(message.id, "helpful")}
              disabled={!!message.feedback}
              className={`text-xs px-3 py-1 border transition-all ${
                message.feedback === "helpful"
                  ? "border-green-500/50 text-green-400"
                  : "border-white/10 text-text-muted hover:border-white/30 hover:text-white"
              }`}
            >
              Helpful
            </button>
            <button
              onClick={() => onFeedback?.(message.id, "not_helpful")}
              disabled={!!message.feedback}
              className={`text-xs px-3 py-1 border transition-all ${
                message.feedback === "not_helpful"
                  ? "border-red-500/50 text-red-400"
                  : "border-white/10 text-text-muted hover:border-white/30 hover:text-white"
              }`}
            >
              Not helpful
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
