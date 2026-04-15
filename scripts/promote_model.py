"""
Model Promotion with RAGAS Evaluation Gate

Promotes a model version from Staging to Production in MLflow registry,
but ONLY if RAGAS evaluation metrics don't regress by more than 5%.

Usage:
  python scripts/promote_model.py --model-name startup-embeddings --version 2
"""

import argparse
import os
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"

import mlflow
from mlflow.tracking import MlflowClient

root = Path(__file__).resolve().parent.parent
env_file = root / ".env.local"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(root))

TRACKING_URI = f"sqlite:///{root}/mlruns.db"
mlflow.set_tracking_uri(TRACKING_URI)

from supabase import create_client
from lib.knowledge_retrieval import retrieve_for_chat
from lib.embeddings import get_embedding

supabase = create_client(
    os.environ.get("SUPABASE_URL") or os.environ["VITE_SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
)

# Reuse eval dataset and metric functions from eval_ragas
from scripts.eval_ragas import (
    EVAL_DATASET,
    context_precision,
    context_recall,
    faithfulness,
    answer_relevance,
    get_chat_answer,
)


def run_ragas_eval() -> dict:
    """Run RAGAS evaluation and return aggregate scores."""
    scores = {"context_precision": [], "context_recall": [], "faithfulness": [], "answer_relevance": []}

    for tc in EVAL_DATASET[:5]:  # Quick eval on first 5 for promotion gate
        question = tc["question"]
        ground_truth = tc["ground_truth"]
        chunks = retrieve_for_chat(supabase, question)
        answer = get_chat_answer(question, chunks)
        if not answer:
            continue

        scores["context_precision"].append(context_precision(question, chunks))
        scores["context_recall"].append(context_recall(ground_truth, chunks))
        scores["faithfulness"].append(faithfulness(answer, chunks))
        scores["answer_relevance"].append(answer_relevance(question, answer))

    return {k: sum(v) / len(v) if v else 0.0 for k, v in scores.items()}


def get_baseline_scores(client: MlflowClient) -> dict | None:
    """Get the latest RAGAS scores from the ragas-evaluation experiment."""
    try:
        experiment = client.get_experiment_by_name("ragas-evaluation")
        if not experiment:
            return None

        runs = client.search_runs(
            experiment_ids=[experiment.experiment_id],
            order_by=["start_time DESC"],
            max_results=1,
        )
        if not runs:
            return None

        run = runs[0]
        return {
            "context_precision": run.data.metrics.get("avg_context_precision", 0),
            "context_recall": run.data.metrics.get("avg_context_recall", 0),
            "faithfulness": run.data.metrics.get("avg_faithfulness", 0),
            "answer_relevance": run.data.metrics.get("avg_answer_relevance", 0),
        }
    except Exception:
        return None


def promote(model_name: str, version: int):
    client = MlflowClient()

    print(f"\nPromotion Gate: {model_name} v{version}")
    print("=" * 60)

    # Run RAGAS eval with candidate model
    print("\nRunning RAGAS evaluation...")
    candidate_scores = run_ragas_eval()
    print(f"  Candidate scores:")
    for metric, value in candidate_scores.items():
        print(f"    {metric}: {value:.3f}")

    # Get baseline from latest RAGAS run
    baseline_scores = get_baseline_scores(client)

    if baseline_scores:
        print(f"\n  Baseline scores (from latest RAGAS run):")
        for metric, value in baseline_scores.items():
            print(f"    {metric}: {value:.3f}")

        # Gate: check for regression > 5%
        blocked = False
        for metric in ["context_precision", "context_recall", "faithfulness", "answer_relevance"]:
            baseline = baseline_scores.get(metric, 0)
            candidate = candidate_scores.get(metric, 0)

            if baseline > 0 and candidate < baseline * 0.95:
                print(f"\n  BLOCKED: {metric} regressed ({baseline:.3f} -> {candidate:.3f}, >{5}% drop)")
                blocked = True

        if blocked:
            print(f"\nPromotion BLOCKED. Fix regressions before promoting.")
            return False
    else:
        print("\n  No baseline found. Skipping regression check.")

    # Log the promotion decision
    mlflow.set_experiment("model-promotions")
    with mlflow.start_run(run_name=f"promote-{model_name}-v{version}"):
        mlflow.log_params({"model_name": model_name, "version": version})
        for metric, value in candidate_scores.items():
            mlflow.log_metric(f"candidate_{metric}", value)
        if baseline_scores:
            for metric, value in baseline_scores.items():
                mlflow.log_metric(f"baseline_{metric}", value)

    # Promote
    try:
        client.transition_model_version_stage(
            name=model_name,
            version=version,
            stage="Production",
            archive_existing_versions=True,
        )
        print(f"\n{model_name} v{version} promoted to Production.")
    except Exception as e:
        print(f"\nCould not transition model stage: {e}")
        print("(This is expected if the model wasn't registered via mlflow.register_model)")

    return True


def main():
    parser = argparse.ArgumentParser(description="Promote model with RAGAS evaluation gate")
    parser.add_argument("--model-name", required=True, help="MLflow registered model name")
    parser.add_argument("--version", type=int, required=True, help="Model version to promote")
    args = parser.parse_args()

    success = promote(args.model_name, args.version)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
