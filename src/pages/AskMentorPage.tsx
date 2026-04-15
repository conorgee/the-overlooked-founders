import { ChatInterface } from "../components/chat/ChatInterface";

export function AskMentorPage() {
  return (
    <div className="max-w-3xl mx-auto w-full h-[calc(100dvh-5rem)] flex flex-col pt-20">
      <ChatInterface />
    </div>
  );
}
