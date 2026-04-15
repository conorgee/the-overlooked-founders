import json
import logging
import os
import re
from pathlib import Path

import joblib
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config import LLM_MODEL, MAX_TOKENS_SCORE
from deps import supabase, groq_client, authenticate
from helpers.transcription import transcribe_video
from lib.feature_extraction import extract_features, FEATURE_NAMES

logger = logging.getLogger(__name__)
router = APIRouter()

MODEL_PATH = Path(__file__).resolve().parent.parent.parent.parent / "models" / "application-scorer-v1.joblib"
_scorer = None


def _get_scorer():
    global _scorer
    if _scorer is None and MODEL_PATH.exists():
        _scorer = joblib.load(str(MODEL_PATH))
        logger.info("Loaded classifier from %s", MODEL_PATH)
    return _scorer


class ScoreBody(BaseModel):
    applicationId: str


async def _generate_summary(app: dict, score: int, top_factors: list[tuple[str, float]]) -> str:
    stage = app.get("stage", "Not specified")
    factor_lines = "\n".join(f"  - {name}: {imp:.3f}" for name, imp in top_factors)

    prompt = f"""You are an application reviewer for The Overlooked Founders, an 8-week AI-powered mentorship programme for young entrepreneurs from underrepresented backgrounds.

A trained classifier scored this application {score}/100. The top contributing features were:
{factor_lines}

Score bands: 80-100 Exceptional, 60-79 Promising, 40-59 Potential, 1-39 Early.

Write a 2-3 sentence assessment that explains the score in human-readable terms. Reference the specific strengths or weaknesses the features highlight. Do NOT output JSON — just the summary text."""

    user_content = f"""Application:
Business Name: {app.get('business_name') or 'Not provided'}
Stage: {stage}
Business Idea: {app.get('business_idea') or 'Not provided'}"""

    completion = groq_client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=MAX_TOKENS_SCORE,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return (completion.choices[0].message.content or "").strip()


@router.post("/score-application", dependencies=[Depends(authenticate)])
async def score_application(body: ScoreBody):
    logger.info("Starting scoring for application %s", body.applicationId)

    app_res = (
        supabase.table("applications")
        .select("id, business_name, business_idea, stage, first_name, last_name, ai_score, video_pitch_url")
        .eq("id", body.applicationId)
        .single()
        .execute()
    )

    app = app_res.data
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if app.get("ai_score") is not None:
        logger.info("Already scored (%s). Skipping.", app["ai_score"])
        return {"message": "Already scored", "score": app["ai_score"]}

    try:
        pitch_transcript = None
        if app.get("video_pitch_url"):
            logger.info("Transcribing video pitch...")
            try:
                pitch_transcript = transcribe_video(groq_client, app["video_pitch_url"])
                logger.info("Pitch transcript: %s...", pitch_transcript[:100])
            except Exception as err:
                logger.warning("Pitch transcription failed entirely, scoring without video: %s", err)

        scorer = _get_scorer()

        if scorer is not None:
            # Hybrid mode: classifier score + LLM summary
            logger.info("Using trained classifier (hybrid mode)")
            features = extract_features(app)
            feature_row = [features.get(name, 0) for name in FEATURE_NAMES]
            score = int(scorer.predict([feature_row])[0])
            score = max(1, min(100, score))

            if hasattr(scorer, "feature_importances_"):
                importances = scorer.feature_importances_
            elif hasattr(scorer, "named_steps") and hasattr(getattr(scorer.named_steps.get("model"), "coef_", None), "__len__"):
                importances = np.abs(scorer.named_steps["model"].coef_)
            else:
                importances = np.zeros(len(FEATURE_NAMES))

            top_factors = sorted(
                zip(FEATURE_NAMES, importances),
                key=lambda x: -x[1],
            )[:5]

            summary = await _generate_summary(app, score, top_factors)
        else:
            # Fallback: pure LLM scoring (no classifier available)
            logger.info("No classifier found, using LLM-only scoring")
            has_pitch = bool(pitch_transcript)
            stage = app.get("stage", "Not specified")

            criteria_base = f"""1. **Problem Clarity** (High weight): Can the founder articulate the problem they're solving? Is it specific and real?
2. **Market Understanding** (High weight): Do they know who their customer is? Have they shown any validation or research?
3. **Founder Commitment** (Medium weight): Does the application show effort, ambition, and skin in the game?
4. **Stage-Appropriate Progress** (Medium weight): For their declared stage ({stage}), are they where they should be?"""

            if has_pitch:
                criteria = criteria_base + "\n5. **Pitch Quality** (Medium weight): How well does the founder communicate their vision in the video? Do they show clarity, passion, and conviction?"
                num_criteria = "five"
            else:
                criteria = criteria_base
                num_criteria = "four"

            scoring_prompt = f"""You are an application reviewer for The Overlooked Founders, an 8-week AI-powered mentorship programme for young entrepreneurs from underrepresented backgrounds.

Evaluate this application across {num_criteria} criteria:
{criteria}

Score scale: 1-100
- 80-100: Exceptional — strong candidate
- 60-79: Promising — worth a closer look
- 40-59: Potential — needs more development
- 1-39: Early — may benefit from resources before reapplying

You MUST respond with ONLY valid JSON, no other text:
{{"score": <number>, "summary": "<2-3 sentence assessment>"}}"""

            pitch_section = ""
            if pitch_transcript:
                pitch_section = f"\n\nVideo Pitch Transcript:\n---\n{pitch_transcript}\n---"

            user_content = f"""Application from {app.get('first_name', '')} {app.get('last_name', '')}:

Business Name: {app.get('business_name') or 'Not provided'}
Stage: {stage}
Business Idea: {app.get('business_idea') or 'Not provided'}{pitch_section}

Please score this application."""

            completion = groq_client.chat.completions.create(
                model=LLM_MODEL,
                max_tokens=MAX_TOKENS_SCORE,
                messages=[
                    {"role": "system", "content": scoring_prompt},
                    {"role": "user", "content": user_content},
                ],
            )

            raw = completion.choices[0].message.content or ""
            logger.info("Raw response: %s", raw)

            json_match = re.search(r"\{[\s\S]*\}", raw)
            if not json_match:
                raise ValueError("Failed to parse JSON from LLM response")

            parsed = json.loads(json_match.group())
            score = min(100, max(1, round(parsed["score"])))
            summary = parsed.get("summary", "")
            top_factors = None

        supabase.table("applications").update({
            "ai_score": score,
            "ai_summary": summary,
        }).eq("id", body.applicationId).execute()

        result = {"success": True, "score": score, "summary": summary}
        if top_factors is not None:
            result["top_factors"] = [{"feature": name, "importance": round(float(imp), 3)} for name, imp in top_factors]

        logger.info("Application %s scored: %d — %s...", body.applicationId, score, summary[:80])
        return result
    except Exception as err:
        logger.error("Scoring error: %s", err)
        raise HTTPException(status_code=500, detail=str(err))
