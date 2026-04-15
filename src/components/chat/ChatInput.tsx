import { useState } from "react";
import { ArrowRight } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setInput("");
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-3">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Ask a mentor anything..."
        disabled={disabled}
        className="flex-1 bg-transparent border-b border-white/20 px-0 py-3 text-white placeholder:text-text-subtle focus:outline-none focus:border-white transition-colors duration-300 disabled:opacity-40"
      />
      <button
        type="submit"
        disabled={disabled || !input.trim()}
        className="bg-accent text-black px-5 py-3 transition-all duration-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-accent-hover"
      >
        <ArrowRight className="w-4 h-4" />
      </button>
    </form>
  );
}
