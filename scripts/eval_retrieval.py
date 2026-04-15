"""
Retrieval Evaluation Framework
Tests hybrid search (vector + keyword) with expected source matching.
Run: python scripts/eval_retrieval.py
"""

import os
import sys
import json
from pathlib import Path

import httpx

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
from lib.knowledge_retrieval import retrieve_for_chat

supabase = create_client(
    os.environ.get("SUPABASE_URL") or os.environ["VITE_SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
)

test_cases = [
    # Semantic matches (vector should find these)
    {"query": "how do I charge customers for my product", "expects": ["Podcast Ep 12: Pricing Strategy"]},
    {"query": "feeling lonely as a founder", "expects": ["Podcast Ep 8: Founder Mindset"]},
    {"query": "should I take investment or bootstrap", "expects": ["LinkedIn Post: Fundraising Reality Check"]},
    {"query": "how do I find my first employees", "expects": ["LinkedIn Post: Three Things About Hiring"]},
    {"query": "how do I know if people want my product", "expects": ["Podcast Ep 27: Product-Market Fit"]},
    {"query": "how to get customers without spending money", "expects": ["Article: Marketing on Zero Budget"]},
    {"query": "what metrics should I track", "expects": ["Article: The Only Metrics That Matter"]},
    {"query": "when should I give up on my idea", "expects": ["Tweet Thread: When to Pivot"]},
    {"query": "how to build company culture", "expects": ["Tweet Thread: Building Culture"]},
    {"query": "what type of revenue model should I use", "expects": ["Podcast Ep 19: Revenue Models"]},
    {"query": "how to talk to potential customers", "expects": ["Podcast Ep 35: Customer Discovery"]},
    {"query": "my first market is too broad", "expects": ["LinkedIn Post: Go-To-Market Mistakes"]},
    {"query": "when should I launch my MVP", "expects": ["Book: The Founder's Playbook, Chapter 3"]},
    # Keyword matches (FTS should find these even if vector misses)
    {"query": "what did Ep 12 say about pricing", "expects": ["Podcast Ep 12: Pricing Strategy"]},
    {"query": "MVP trap", "expects": ["Book: The Founder's Playbook, Chapter 3"]},
    {"query": "fundraising reality check", "expects": ["LinkedIn Post: Fundraising Reality Check"]},
    # Multi-source queries (should find at least one)
    {"query": "pricing strategy for startups", "expects": ["Podcast Ep 12: Pricing Strategy", "Podcast Ep 19: Revenue Models"]},
    {"query": "hiring and team culture", "expects": ["LinkedIn Post: Three Things About Hiring", "Tweet Thread: Building Culture"]},
]

context_cases = [
    {
        "name": "follow-up on pricing",
        "history": [
            {"role": "user", "content": "How should I price my product?"},
            {"role": "assistant", "content": "The biggest mistake founders make is underpricing. Price is a signal of value. Consider starting higher than you think — when I raised from $9 to $49/month, enterprise customers started taking us seriously."},
        ],
        "query": "Tell me more about that",
        "expects": ["Podcast Ep 12: Pricing Strategy"],
    },
    {
        "name": "pronoun reference to hiring",
        "history": [
            {"role": "user", "content": "When should I make my first hire?"},
            {"role": "assistant", "content": "Hire for attitude, train for skill. Your first hire should free up your biggest bottleneck."},
        ],
        "query": "What else should I know about it?",
        "expects": ["LinkedIn Post: Three Things About Hiring"],
    },
    {
        "name": "topic shift — no enrichment needed",
        "history": [
            {"role": "user", "content": "How should I price my product?"},
            {"role": "assistant", "content": "Consider value-based pricing..."},
        ],
        "query": "How do I find investors for my startup?",
        "expects": ["LinkedIn Post: Fundraising Reality Check"],
    },
]


def evaluate():
    print(f"\nRetrieval Evaluation — {len(test_cases)} test cases")
    print("\u2500" * 60)

    passed = 0
    total_expected = 0
    total_found = 0

    for tc in test_cases:
        results = retrieve_for_chat(supabase, tc["query"])
        result_titles = [r["source_title"] for r in results]

        found = [e for e in tc["expects"] if e in result_titles]
        found_any = len(found) > 0

        total_expected += len(tc["expects"])
        total_found += len(found)

        if found_any:
            passed += 1
            rank = result_titles.index(found[0]) + 1
            print(f'  \u2713 "{tc["query"]}"')
            print(f"    \u2192 found {found[0]} (rank {rank})")
        else:
            print(f'  \u2717 "{tc["query"]}"')
            print(f'    \u2192 expected: {" OR ".join(tc["expects"])}')
            print(f'    \u2192 got: {", ".join(result_titles[:3])}')

    print("\u2500" * 60)
    pass_rate = (passed / len(test_cases)) * 100
    recall = (total_found / total_expected) * 100
    print(f"Pass rate: {passed}/{len(test_cases)} ({pass_rate:.0f}%)")
    print(f"Recall: {total_found}/{total_expected} ({recall:.0f}%)")
    print()

    # Context-aware tests — call the /chat endpoint
    print(f"\nContext-Aware Retrieval — via /chat endpoint")
    print("\u2500" * 60)

    SERVICE_URL = "http://localhost:3001"
    API_KEY = os.environ.get("PIPELINE_API_KEY") or os.environ.get("VITE_PIPELINE_API_KEY")

    ctx_passed = 0
    for tc in context_cases:
        try:
            headers = {"Content-Type": "application/json"}
            if API_KEY:
                headers["x-api-key"] = API_KEY

            response = httpx.post(
                f"{SERVICE_URL}/chat",
                headers=headers,
                json={"message": tc["query"], "history": tc["history"]},
                timeout=30.0,
            )

            if response.status_code != 200:
                print(f'  \u2717 "{tc["name"]}" — HTTP {response.status_code}')
                continue

            data = response.json()
            sources = data.get("sources", [])
            found_source = any(
                any(s_found for s_found in sources if e.split(":")[0] in s_found)
                for e in tc["expects"]
            )

            reply_lower = data["reply"].lower()
            topic_match = any(
                any(kw in reply_lower for kw in e.lower().split() if len(kw) > 3)
                for e in tc["expects"]
            )

            if found_source or topic_match:
                ctx_passed += 1
                print(f'  \u2713 "{tc["name"]}"')
                print(f'    \u2192 sources: {", ".join(sources) or "(inline)"}')
            else:
                print(f'  \u2717 "{tc["name"]}"')
                print(f'    \u2192 expected topic: {" OR ".join(tc["expects"])}')
                print(f'    \u2192 got sources: {", ".join(sources) or "none"}')
                print(f'    \u2192 reply preview: {data["reply"][:100]}...')
        except Exception as err:
            print(f'  \u2717 "{tc["name"]}" — {err}')

    print("\u2500" * 60)
    print(f"Context-aware: {ctx_passed}/{len(context_cases)} passed")
    print()


if __name__ == "__main__":
    evaluate()
