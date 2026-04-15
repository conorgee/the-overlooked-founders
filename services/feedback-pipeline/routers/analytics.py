import logging

from fastapi import APIRouter, Depends

from deps import supabase, authenticate
from lib.transcript_analytics import analyse_transcript

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/founder/{user_id}", dependencies=[Depends(authenticate)])
async def founder_analytics(user_id: str):
    """Per-week NLP scores + trends for a single founder."""
    submissions = (
        supabase.table("weekly_submissions")
        .select("id, week_number, transcript")
        .eq("user_id", user_id)
        .order("week_number")
        .execute()
    )

    weeks = []
    for sub in (submissions.data or []):
        transcript = sub.get("transcript")
        if not transcript:
            continue

        analysis = analyse_transcript(transcript, sub["week_number"])
        weeks.append({
            "week": sub["week_number"],
            "confidence": analysis["confidence"]["score"],
            "topic_alignment": analysis["topic_alignment"]["score"],
            "is_on_topic": analysis["topic_alignment"]["is_on_topic"],
            "specificity": analysis["specificity"]["score"],
            "sentiment": analysis["sentiment"]["score"],
            "word_count": analysis["word_count"],
            "warnings": analysis["warnings"],
        })

    # Compute trends (compare last 2 data points)
    trends = {}
    if len(weeks) >= 2:
        latest = weeks[-1]
        previous = weeks[-2]
        for metric in ["confidence", "topic_alignment", "specificity"]:
            delta = latest[metric] - previous[metric]
            if delta > 0.1:
                trends[metric] = "improving"
            elif delta < -0.1:
                trends[metric] = "declining"
            else:
                trends[metric] = "stable"

    return {"weeks": weeks, "trends": trends}


@router.get("/cohort", dependencies=[Depends(authenticate)])
async def cohort_analytics():
    """Aggregate NLP stats across all founders in the current cohort."""
    # Get all submissions with transcripts
    submissions = (
        supabase.table("weekly_submissions")
        .select("user_id, week_number, transcript, profiles(full_name)")
        .not_.is_("transcript", "null")
        .order("week_number")
        .execute()
    )

    # Group by founder
    founders: dict[str, list] = {}
    for sub in (submissions.data or []):
        uid = sub["user_id"]
        if uid not in founders:
            name = (sub.get("profiles") or {}).get("full_name", "Unknown")
            founders[uid] = {"name": name, "weeks": []}

        analysis = analyse_transcript(sub["transcript"], sub["week_number"])
        founders[uid]["weeks"].append({
            "week": sub["week_number"],
            "confidence": analysis["confidence"]["score"],
            "specificity": analysis["specificity"]["score"],
            "topic_alignment": analysis["topic_alignment"]["score"],
        })

    # Build summary per founder
    cohort = []
    all_confidence = []
    all_specificity = []

    for uid, data in founders.items():
        if not data["weeks"]:
            continue
        latest = data["weeks"][-1]
        cohort.append({
            "user_id": uid,
            "name": data["name"],
            "weeks_completed": len(data["weeks"]),
            "latest_confidence": latest["confidence"],
            "latest_specificity": latest["specificity"],
            "latest_topic_alignment": latest["topic_alignment"],
        })
        all_confidence.append(latest["confidence"])
        all_specificity.append(latest["specificity"])

    averages = {}
    if all_confidence:
        averages["confidence"] = round(sum(all_confidence) / len(all_confidence), 3)
        averages["specificity"] = round(sum(all_specificity) / len(all_specificity), 3)

    return {"founders": cohort, "averages": averages}


@router.get("/warnings", dependencies=[Depends(authenticate)])
async def warnings():
    """Early warning flags for founders who may need intervention."""
    submissions = (
        supabase.table("weekly_submissions")
        .select("user_id, week_number, transcript, profiles(full_name)")
        .not_.is_("transcript", "null")
        .order("week_number")
        .execute()
    )

    # Group by founder
    founders: dict[str, dict] = {}
    for sub in (submissions.data or []):
        uid = sub["user_id"]
        if uid not in founders:
            name = (sub.get("profiles") or {}).get("full_name", "Unknown")
            founders[uid] = {"name": name, "analyses": []}

        analysis = analyse_transcript(sub["transcript"], sub["week_number"])
        founders[uid]["analyses"].append({
            "week": sub["week_number"],
            **analysis,
        })

    warning_list = []

    for uid, data in founders.items():
        analyses = sorted(data["analyses"], key=lambda x: x["week"])
        if len(analyses) < 2:
            continue

        latest = analyses[-1]
        previous = analyses[-2]

        # Warning: confidence drop > 0.15
        conf_latest = latest["confidence"]["score"]
        conf_prev = previous["confidence"]["score"]
        if conf_latest < conf_prev - 0.15:
            warning_list.append({
                "user_id": uid,
                "founder": data["name"],
                "type": "confidence_drop",
                "severity": "high",
                "detail": f"Confidence dropped from {conf_prev:.2f} to {conf_latest:.2f}",
                "week": latest["week"],
            })

        # Warning: off-topic for 2+ weeks
        if not latest["topic_alignment"]["is_on_topic"] and not previous["topic_alignment"]["is_on_topic"]:
            warning_list.append({
                "user_id": uid,
                "founder": data["name"],
                "type": "off_topic",
                "severity": "medium",
                "detail": f"Off-topic for weeks {previous['week']} and {latest['week']}",
                "week": latest["week"],
            })

        # Warning: declining specificity
        spec_latest = latest["specificity"]["score"]
        spec_prev = previous["specificity"]["score"]
        if spec_latest < spec_prev - 0.1:
            warning_list.append({
                "user_id": uid,
                "founder": data["name"],
                "type": "declining_specificity",
                "severity": "medium",
                "detail": f"Specificity dropped from {spec_prev:.2f} to {spec_latest:.2f}",
                "week": latest["week"],
            })

    # Sort by severity
    severity_order = {"high": 0, "medium": 1, "low": 2}
    warning_list.sort(key=lambda w: severity_order.get(w["severity"], 2))

    return {"warnings": warning_list}
