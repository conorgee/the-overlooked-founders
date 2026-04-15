# Architectural Choices for Prototype

## Context
The AI Mentorship Platform for Entrepreneurs needs a working prototype deployable to Netlify. This document captures the key architectural decisions and implementation plan.

---

## Tech Stack: Vite + React + Tailwind

### Why Vite + React (not Next.js)?
- **Netlify-native**: Vite builds to a static `dist/` folder that Netlify serves directly
- **No SSR complexity**: Next.js on Netlify requires the `@netlify/plugin-nextjs` adapter and introduces server-side rendering overhead unnecessary for a prototype
- **Fast dev experience**: Vite's HMR is near-instant
- **Serverless functions**: Netlify Functions (v2) handle the Claude API proxy — no backend server needed
- **TypeScript throughout** for type safety

### Why Tailwind CSS (no shadcn/ui)?
- shadcn/ui requires a CLI tool and copy-paste components, adding setup complexity
- For a prototype, 5-6 custom UI components (Button, Card, Input, etc.) are sufficient
- Tailwind alone gives us full control over the dark-themed branding

---

## Project Structure

```
prototype/
  package.json
  vite.config.ts
  tsconfig.json
  netlify.toml                    # Netlify build config + SPA redirects
  index.html
  tailwind.config.ts
  postcss.config.js
  .env.example                    # ANTHROPIC_API_KEY placeholder
  public/
    favicon.ico
  src/
    main.tsx                      # React entry point
    App.tsx                       # Router setup
    index.css                     # Tailwind directives + custom styles
    components/
      layout/
        Header.tsx                # Nav bar with logo + links
        Footer.tsx
        Layout.tsx                # Wraps all pages
      landing/
        Hero.tsx                  # Main hero section
        HowItWorks.tsx            # 3-step process cards
        ProgramStructure.tsx      # 8-week overview
        CTA.tsx                   # "Apply Now" call to action
      chat/
        ChatInterface.tsx         # Main chat component
        ChatMessage.tsx           # Individual message bubble
        ChatInput.tsx             # Input bar with send button
        SourceCitation.tsx        # Shows which content the answer drew from
      application/
        ApplicationForm.tsx       # Multi-step application form
      dashboard/
        WeekCard.tsx              # Individual week in the programme
        ProgressTracker.tsx       # Visual progress indicator
      ui/
        Button.tsx
        Card.tsx
        Input.tsx
        Textarea.tsx
    pages/
      LandingPage.tsx             # Route: /
      AskStephenPage.tsx          # Route: /ask
      ApplicationPage.tsx         # Route: /apply
      DashboardPage.tsx           # Route: /dashboard
    data/
      stephen-knowledge.ts        # 10-15 curated sample passages (simplified RAG)
      program-weeks.ts            # 8-week program structure
    lib/
      api.ts                      # Fetch wrapper for Netlify Functions
      types.ts                    # TypeScript interfaces
  netlify/
    functions/
      chat.ts                     # Serverless function -> Claude API
```

---

## Pages

### 1. Landing Page (`/`)
- **Hero**: Program title, subtitle, CTA button
- **How It Works**: 3-step visual flow (Apply -> Get AI Mentorship -> Ask Stephen Anything)
- **8-Week Programme**: Card grid showing each week's theme
- **CTA**: "Apply Now" driving to the application form

### 2. Ask Stephen (`/ask`)
- Chat interface with conversation bubbles (user on right, Stephen on left)
- Each AI response includes **source citations** (e.g., "From Podcast Ep 12: Pricing Strategy")
- Pre-loaded **suggested questions** to get started
- Calls `/.netlify/functions/chat` endpoint
- Conversation history maintained in React state for multi-turn context

### 3. Apply (`/apply`)
- Multi-step form: Personal Info -> Business Idea -> Video Pitch (upload placeholder) -> Submit
- Form validation with inline errors
- Success confirmation screen

### 4. Dashboard (`/dashboard`)
- Mockup of the logged-in entrepreneur experience
- 8 week cards with status indicators (completed / current / locked)
- Progress tracker bar
- Current week expanded to show "Upload your video update" area

---

## AI Chat Architecture

### How it works
```
Browser (React)                    Netlify Function               Claude API
     |                                  |                            |
     |-- POST /chat {message, history} -->                           |
     |                                  |-- messages.create() ------>|
     |                                  |<-- response text ----------|
     |<-- {reply, sources} -------------|                            |
     |                                                               |
```

### Simplified RAG Approach
Instead of a full vector database, the prototype embeds **10-15 curated knowledge passages** directly in the system prompt. Claude's large context window handles this easily.

**Knowledge passage topics:**
1. Pricing strategy
2. First hires
3. Fundraising basics
4. Product-market fit
5. Customer discovery
6. Scaling a business
7. Founder mindset & resilience
8. Marketing on a budget
9. When to pivot
10. Building team culture

Each passage includes metadata: source type (podcast/article/tweet/LinkedIn), source name, and content excerpt. The system prompt instructs Claude to cite sources in responses.

### Security
- `ANTHROPIC_API_KEY` is **never exposed to the browser** — only accessed server-side in the Netlify Function
- API calls are proxied through the serverless function

---

## Design Theme

Matching the executive summary branding:

| Token | Value | Usage |
|-------|-------|-------|
| `dark` | `#0A0A0A` | Page background |
| `dark-card` | `#1A1A1A` | Card backgrounds |
| `dark-border` | `#333333` | Borders, dividers |
| `accent` | `#C8A455` | Gold accent (buttons, highlights) |
| `text-primary` | `#F0F0F0` | Primary text |
| `text-muted` | `#AAAAAA` | Secondary text |

**Font**: Inter (Google Fonts) — web equivalent of the Helvetica Neue used in the exec summary.

---

## Netlify Configuration

```toml
[build]
  command = "npm run build"
  publish = "dist"
  functions = "netlify/functions"

[build.environment]
  NODE_VERSION = "20"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200

[functions]
  node_bundler = "esbuild"
```

The `[[redirects]]` rule is essential for SPA routing — all routes fall through to `index.html` where React Router handles them.

---

## Dependencies

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.26.0",
    "lucide-react": "^0.400.0"
  },
  "devDependencies": {
    "@anthropic-ai/sdk": "^0.30.0",
    "@netlify/functions": "^2.8.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0"
  }
}
```

`@anthropic-ai/sdk` is in devDependencies because it's only used by the Netlify Function (bundled separately by esbuild), not client-side code.

---

## Deployment Options

### Option A: Netlify CLI (recommended)
```bash
cd prototype
npm install
npm run build
npx netlify-cli login
npx netlify-cli init
npx netlify-cli env:set ANTHROPIC_API_KEY sk-ant-...
npx netlify-cli deploy --prod
```

### Option B: Git-based (CI/CD)
1. Push to GitHub
2. Connect repo in Netlify dashboard
3. Set base directory to `prototype/`
4. Set build command: `npm run build`, publish: `dist`
5. Add `ANTHROPIC_API_KEY` in Netlify > Site settings > Environment variables

### Option C: Drag & Drop (static preview only)
1. `npm run build`
2. Drag `dist/` folder to Netlify dashboard
3. Note: Chat will NOT work without Functions — UI preview only

---

## Implementation Order

1. **Scaffold** — Vite project, Tailwind config, netlify.toml, router, Layout
2. **Landing page** — Hero, HowItWorks, ProgramStructure, CTA
3. **Ask Stephen chat** — Chat UI + Netlify Function + knowledge data
4. **Application form** — Multi-step form with validation
5. **Dashboard** — Week cards, progress mockup
6. **Polish** — Responsive design, loading states, meta tags, deploy
