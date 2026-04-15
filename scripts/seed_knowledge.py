"""
Seeds the knowledge base with 14 sample passages.
Clears existing data, chunks content, generates embeddings, and inserts.
Run: python scripts/seed_knowledge.py
"""

import os
import sys
from pathlib import Path

# Load .env.local from prototype root
root = Path(__file__).resolve().parent.parent
env_file = root / ".env.local"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(root))

from supabase import create_client
from lib.embeddings import get_embedding
from lib.chunker import chunk_text

supabase = create_client(
    os.environ.get("SUPABASE_URL") or os.environ["VITE_SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
)

passages = [
    {
        "source": "Podcast Ep 12: Pricing Strategy",
        "sourceType": "podcast",
        "tags": ["pricing", "business model", "revenue", "unit economics"],
        "content": "The biggest mistake I see first-time founders make is underpricing their product. They think low prices will attract more customers, but what it actually does is signal low value. When I launched my first SaaS product, I started at $9/month and nobody took it seriously. The moment I raised it to $49/month, we started getting enterprise customers who actually stuck around. Price is a signal — make sure yours says the right thing.",
    },
    {
        "source": "LinkedIn Post: Three Things About Hiring",
        "sourceType": "linkedin",
        "tags": ["hiring", "team", "first hires", "team & operations"],
        "content": "Three things I wish I knew before my first hire: 1) Hire for attitude, train for skill. The best early employees are the ones who figure things out, not the ones with the perfect CV. 2) Your first hire should free up your biggest bottleneck, not fill a role you think you should have. 3) Cultural fit isn't about liking the same things — it's about caring about the same outcomes.",
    },
    {
        "source": "Article: Scaling From 0 to 1",
        "sourceType": "article",
        "tags": ["scaling", "customers", "onboarding", "idea validation"],
        "content": "The first ten customers are everything. Don't try to scale before you've manually onboarded at least ten paying customers. Each one will teach you something your product roadmap never could. I personally called every one of our first 50 customers. Those conversations shaped our entire product direction. Automation comes later — understanding comes first.",
    },
    {
        "source": "Podcast Ep 27: Product-Market Fit",
        "sourceType": "podcast",
        "tags": ["product-market fit", "validation", "retention", "idea validation"],
        "content": "You know you've hit product-market fit when customers start pulling the product out of your hands. Before that moment, you're pushing. The difference is night and day. My test: if 40% of your users would be 'very disappointed' if your product disappeared tomorrow, you're there. If not, keep iterating. Don't scale a leaky bucket.",
    },
    {
        "source": "Tweet Thread: When to Pivot",
        "sourceType": "tweet",
        "tags": ["pivoting", "idea validation", "iteration", "persistence"],
        "content": "Hot take: most startups don't pivot too late — they pivot too early. Give your idea at least 6 months of genuine effort before deciding it won't work. That means actually talking to customers, not just building in a vacuum. The founders I mentor who succeed are the ones who are stubborn on vision but flexible on approach.",
    },
    {
        "source": "Podcast Ep 8: Founder Mindset",
        "sourceType": "podcast",
        "tags": ["mindset", "founder wellbeing", "support", "leadership"],
        "content": "The hardest part of being a founder isn't the strategy or the fundraising — it's the loneliness. You're making decisions every day with incomplete information, and most of the time nobody tells you if you got it right. Build a support system early. Find two or three people who understand the journey and check in with them regularly. Entrepreneurship is a team sport, even when it feels like a solo one.",
    },
    {
        "source": "Article: Marketing on Zero Budget",
        "sourceType": "article",
        "tags": ["marketing", "go-to-market", "growth", "customer acquisition"],
        "content": "You don't need a marketing budget to get your first 100 customers. Here's what actually works: 1) Be genuinely helpful in communities where your customers hang out. 2) Write content that answers the exact questions your customers are Googling. 3) Ask every happy customer for one introduction. Word of mouth at the early stage beats any paid channel. I built my first business to $500K ARR with zero ad spend.",
    },
    {
        "source": "LinkedIn Post: Fundraising Reality Check",
        "sourceType": "linkedin",
        "tags": ["fundraising", "pitch", "investment", "bootstrapping", "pitch & next steps"],
        "content": "Fundraising advice nobody gives you: most great businesses never raise venture capital, and that's perfectly fine. VC is a tool, not a trophy. Before you pitch investors, ask yourself: does my business actually need outside capital to grow, or am I just chasing validation? If you can bootstrap to revenue, you keep control and you prove the model. That's leverage no pitch deck can match.",
    },
    {
        "source": "Podcast Ep 35: Customer Discovery",
        "sourceType": "podcast",
        "tags": ["customer discovery", "user interviews", "research"],
        "content": "The number one rule of customer discovery: never ask people if they'd buy your product. They'll say yes to be polite, and you'll build something nobody actually wants. Instead, ask about their current behaviour. What do they do today? What frustrates them? What have they already tried? Past behaviour predicts future behaviour — hypothetical questions predict nothing.",
    },
    {
        "source": "Book: The Founder's Playbook, Chapter 3",
        "sourceType": "book",
        "tags": ["mvp", "mvp strategy", "product", "iteration", "launch"],
        "content": "Your MVP should embarrass you a little. If you're proud of v1, you launched too late. The point of an MVP isn't to impress people — it's to learn as fast as possible. Ship something small, measure what happens, and iterate. The founders who win aren't the ones with the best first version. They're the ones who learn fastest.",
    },
    {
        "source": "Tweet Thread: Building Culture",
        "sourceType": "tweet",
        "tags": ["team culture", "culture", "hiring", "team & operations"],
        "content": "Culture isn't ping pong tables and free snacks. Culture is what happens when things go wrong. Do people hide mistakes or share them? Do they wait for permission or take initiative? The culture of your startup is set in the first 10 hires. Every person you bring on either reinforces or dilutes the standards you've set. Choose carefully.",
    },
    {
        "source": "Podcast Ep 19: Revenue Models",
        "sourceType": "podcast",
        "tags": ["business model", "revenue models", "monetisation", "pricing"],
        "content": "There are really only a handful of revenue models that work for early-stage startups: subscription, transaction fees, marketplace commissions, and direct sales. Pick one and focus. The biggest trap I see is founders trying to monetise three ways at once before they've nailed one. Get one revenue stream working reliably before adding complexity.",
    },
    {
        "source": "Article: The Only Metrics That Matter",
        "sourceType": "article",
        "tags": ["metrics", "growth & metrics", "retention", "analytics", "unit economics"],
        "content": "Early-stage founders track too many metrics. Here are the only three that matter before product-market fit: 1) Retention — are people coming back? 2) Referral — are people telling others? 3) Revenue per customer — is the unit economics viable? Everything else is vanity. If those three are trending up, you're on the right track.",
    },
    {
        "source": "LinkedIn Post: Go-To-Market Mistakes",
        "sourceType": "linkedin",
        "tags": ["go-to-market", "niche", "market", "launch", "growth"],
        "content": "The most common go-to-market mistake: building for everyone. Your first market should be tiny and specific. I'm talking 'left-handed dentists in Dublin' specific. When you own a niche, you can expand. When you target everyone, you reach no one. Every successful company I've built or mentored started by dominating a small, well-defined segment first.",
    },
]


def seed():
    # Clear existing data
    count_res = supabase.table("knowledge_chunks").select("id", count="exact").execute()
    count = count_res.count or 0

    if count > 0:
        print(f"Clearing {count} existing chunks to re-seed with embeddings...")
        supabase.table("source_documents").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

    print("Loading embedding model (first run downloads ~80MB)...")
    get_embedding("test")
    print("Model loaded. Seeding knowledge base with embeddings...\n")

    total_chunks = 0

    for p in passages:
        # Insert source document
        doc_res = (
            supabase.table("source_documents")
            .insert({"title": p["source"], "source_type": p["sourceType"]})
            .execute()
        )
        doc_id = doc_res.data[0]["id"]

        # Chunk the content
        chunks = chunk_text(p["content"])

        # Embed and insert each chunk
        rows = []
        for i, chunk in enumerate(chunks):
            embedding = get_embedding(chunk)
            rows.append({
                "source_document_id": doc_id,
                "chunk_text": chunk,
                "topic_tags": p["tags"],
                "content_type": p["sourceType"],
                "chunk_index": i,
                "embedding": embedding,
            })

        supabase.table("knowledge_chunks").insert(rows).execute()

        total_chunks += len(chunks)
        tags_str = ", ".join(p["tags"])
        print(f'  \u2713 {p["source"]} \u2192 {len(chunks)} chunk(s) ({tags_str})')

    print(f"\nDone. Seeded {len(passages)} sources \u2192 {total_chunks} chunks with vector embeddings.")


if __name__ == "__main__":
    seed()
