<p align="center">
  <img src="src/assets/logo-white.png" alt="The Overlooked Founders" width="400" />
</p>

<p align="center">
  <strong>AI-Powered Mentorship Platform for Entrepreneurs</strong>
</p>

---

A prototype platform for The Overlooked Founders — an initiative backing high-potential founders from lower socioeconomic backgrounds through an 8-week AI-powered mentorship programme.

**What it does:**

- RAG-powered "Ask a Mentor" chat — hybrid vector + keyword search with context-aware retrieval and feedback-boosted re-ranking
- AI feedback pipeline — video transcription (Whisper) + knowledge-grounded mentorship feedback
- Application scoring — hybrid Random Forest classifier + LLM summary with optional video pitch analysis
- Transcript analytics — NLP scoring (confidence, topic alignment, specificity, sentiment) with early warning flags
- User feedback loop — thumbs up/down drives retrieval quality via Wilson score re-ranking
- MLflow experiment tracking — model registry with RAGAS evaluation gate for production promotion
- Admin dashboard — knowledge base CRUD with auto-chunking + embedded video playback
- Participant dashboard — weekly video submissions, progress tracking, AI feedback

**Stack:**

- **Frontend:** React, TypeScript, Vite, Tailwind CSS v4
- **Backend:** Python, FastAPI, sentence-transformers (all-MiniLM-L6-v2), scikit-learn, MLflow
- **ML/NLP:** distilbert (sentiment), embedding fine-tuning (TripletLoss), RAGAS evaluation
- **Infrastructure:** Supabase (Postgres + pgvector + Auth + Storage), Groq (Llama 3.3 70B + Whisper)
