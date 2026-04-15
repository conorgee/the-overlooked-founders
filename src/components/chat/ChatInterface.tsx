import { useState, useRef, useEffect } from "react";
import { Loader2 } from "lucide-react";
import type { ChatMessage as ChatMessageType } from "../../lib/types";
import { sendChatMessage, submitFeedback, formatHistory } from "../../lib/api";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { supabase } from "../../lib/supabase";
import { useAuth } from "../../lib/auth";

const suggestedQuestions = [
  "How should I price my product?",
  "When is the right time to hire?",
  "How do I know if I have product-market fit?",
  "What's the biggest mistake first-time founders make?",
  "Should I raise VC funding?",
];

export function ChatInterface() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load chat history from Supabase on mount
  useEffect(() => {
    if (!user) return;
    supabase
      .from("chat_messages")
      .select("*")
      .eq("user_id", user.id)
      .order("created_at", { ascending: true })
      .then(({ data }) => {
        if (data) {
          setMessages(
            data.map((m) => ({
              id: m.id,
              role: m.role as "user" | "assistant",
              content: m.content,
              sources: m.sources_cited ?? undefined,
              timestamp: new Date(m.created_at),
            }))
          );
        }
      });
  }, [user]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function persistMessage(role: "user" | "assistant", content: string, sources?: string[]) {
    if (!user) return;
    await supabase.from("chat_messages").insert({
      user_id: user.id,
      role,
      content,
      sources_cited: sources ?? null,
    });
  }

  const handleSend = async (content: string) => {
    const userMessage: ChatMessageType = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    persistMessage("user", content);

    try {
      const history = formatHistory([...messages, userMessage]);
      const { reply, sources, message_id } = await sendChatMessage(content, history, user?.id);

      const finalSources = sources;

      const assistantMessage: ChatMessageType = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: reply,
        sources: finalSources.length > 0 ? finalSources : undefined,
        timestamp: new Date(),
        messageId: message_id ?? undefined,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      // Only persist client-side if backend didn't (no user_id = no server-side persist)
      if (!message_id) {
        persistMessage("assistant", reply, finalSources.length > 0 ? finalSources : undefined);
      }
    } catch {
      const errorMessage: ChatMessageType = {
        id: crypto.randomUUID(),
        role: "assistant",
        content:
          "Sorry, I'm having trouble connecting right now. Please try again in a moment.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFeedback = async (msgId: string, feedback: "helpful" | "not_helpful") => {
    const msg = messages.find((m) => m.id === msgId);
    if (!msg?.messageId) return;
    try {
      await submitFeedback(msg.messageId, feedback);
      setMessages((prev) =>
        prev.map((m) => (m.id === msgId ? { ...m, feedback } : m))
      );
    } catch {
      // silently fail
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-6 sm:p-8 space-y-8">
        {messages.length === 0 && (
          <div className="text-center py-20">
            <p className="text-xs uppercase tracking-[0.2em] text-text-muted mb-6">
              Ask a Mentor
            </p>
            <h3 className="text-3xl sm:text-4xl font-medium text-white tracking-[-0.04em] mb-4">
              What do you need
              <br />
              <span className="text-text-muted">guidance on?</span>
            </h3>
            <p className="text-text-muted mb-12 max-w-md mx-auto text-[15px] leading-relaxed">
              Every answer is grounded in real experience and cites its sources.
            </p>
            <div className="flex flex-wrap justify-center gap-3">
              {suggestedQuestions.map((q) => (
                <button
                  key={q}
                  onClick={() => handleSend(q)}
                  className="text-xs uppercase tracking-[0.1em] border border-white/10 px-5 py-2.5 text-text-muted hover:text-white hover:border-white/30 transition-all duration-300"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} onFeedback={handleFeedback} />
        ))}

        {isLoading && (
          <div className="flex gap-4">
            <div className="w-8 h-8 flex items-center justify-center shrink-0">
              <Loader2 className="w-4 h-4 text-text-muted animate-spin" />
            </div>
            <div className="py-3">
              <p className="text-text-subtle text-sm">Thinking...</p>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-white/10 p-6 sm:p-8">
        <ChatInput onSend={handleSend} disabled={isLoading} />
      </div>
    </div>
  );
}
