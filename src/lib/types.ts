export interface KnowledgePassage {
  id: string;
  source: string;
  sourceType: "podcast" | "article" | "tweet" | "linkedin" | "book";
  topic: string;
  content: string;
}

export interface ProgramWeek {
  week: number;
  title: string;
  description: string;
  topics: string[];
  status: "completed" | "current" | "locked";
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  timestamp: Date;
  messageId?: string;
  feedback?: "helpful" | "not_helpful";
}

export interface ApplicationFormData {
  firstName: string;
  lastName: string;
  email: string;
  businessName: string;
  businessIdea: string;
  stage: string;
  videoFile: File | null;
}

export interface Application {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  business_name: string | null;
  business_idea: string | null;
  stage: string | null;
  status: string;
  video_pitch_url: string | null;
  ai_score: number | null;
  ai_summary: string | null;
  created_at: string;
  user_id: string | null;
}

export interface Submission {
  id: string;
  user_id: string;
  week_number: number;
  video_url: string | null;
  status: string;
  created_at: string;
  profile?: { full_name: string | null; email: string } | null;
  ai_response?: { response_text: string; sources_cited: string[] | null } | null;
}
