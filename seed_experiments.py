#!/usr/bin/env python3
"""
seed_experiments.py — Test Harness & Automated Seeder for LLM-as-a-Judge Lab.

Populates the PostgreSQL evaluation database across 4 target judge models:
  1. gpt-4o-mini (OpenAI Baseline)
  2. deepseek/deepseek-v4-flash (DeepSeek V4)
  3. anthropic/claude-3.5-haiku (Claude 3.5 Haiku)
  4. meta-llama/llama-3.3-70b-instruct (Llama 3.3 70B)

Evaluates 3 technical topics across 3 experimental variations (Baseline, Position Swap, Verbosity Padding)
for a total of 36 live evaluations.

Uses Python standard library (urllib.request, json) to guarantee 100% dependency-free execution.
"""

import sys
import time
import json
import urllib.request
import urllib.error

BACKEND_URL = "http://localhost:8000"

MODELS = [
    "gpt-4o-mini",
    "deepseek/deepseek-v4-flash",
    "anthropic/claude-3.5-haiku",
    "meta-llama/llama-3.3-70b-instruct",
]

TOPICS = [
    {
        "id": "overfitting",
        "topic": "Overfitting & Regularization in Machine Learning",
        "question": "What is overfitting in machine learning models, and how do L1/L2 regularization techniques prevent it?",
        "correct_answer": (
            "Overfitting occurs when a model learns the training data noise rather than true underlying patterns, resulting in low training error but high validation error. "
            "L1 (Lasso) regularization adds an absolute weight penalty (lambda * |w|) driving irrelevant coefficients to exact zero for feature selection. "
            "L2 (Ridge) regularization adds a squared penalty (lambda * w^2) decaying weights smoothly to prevent extreme parameter dominance."
        ),
        "flawed_answer": (
            "Overfitting happens when a machine learning model does not have enough data to train. "
            "You can fix it by increasing the learning rate to 1.0 and removing validation split data so the model focuses entirely on fitting training labels without regularization."
        ),
    },
    {
        "id": "docker_vs_vm",
        "topic": "Docker Containers vs Virtual Machines",
        "question": "Explain the architectural difference between Docker containers and traditional Virtual Machines.",
        "correct_answer": (
            "Virtual Machines run a full guest OS on top of a hypervisor (Type 1 or 2), resulting in heavy disk images and slower boot times due to duplicated kernel overhead. "
            "Docker containers share the host Linux kernel directly, isolating process namespaces and cgroups in lightweight user space, delivering near-instant startup times and minimal memory footprints."
        ),
        "flawed_answer": (
            "Docker containers require hypervisors to emulate CPU instructions for guest operating systems. "
            "Virtual Machines are faster than Docker containers because they run bare-metal without kernel drivers or namespace constraints."
        ),
    },
    {
        "id": "jwt_security",
        "topic": "JSON Web Tokens (JWT) Architecture & Security",
        "question": "What are the core components of a JWT, and what security risks arise from using symmetric secret keys vs asymmetric key pairs?",
        "correct_answer": (
            "A JWT consists of Header (algorithm & token type), Payload (claims & expiry), and Signature (HMAC/RSA hash), separated by dots. "
            "Symmetric signing (HS256) uses a shared secret requiring both issuing and validating services to hold key access, risking leakage across microservices. "
            "Asymmetric signing (RS256/ES256) uses a private key for token issuance and public keys for distributed verification without exposing signing privileges."
        ),
        "flawed_answer": (
            "JWTs automatically encrypt user passwords in the payload using base64 encoding. "
            "You don't need signatures if you store tokens in local storage, because base64 strings cannot be decoded by web browsers."
        ),
    },
]

VERBOSITY_PADDING = (
    "\n\n### Comprehensive Comparative Technical Analysis & Extended Documentation\n"
    "To thoroughly evaluate the underlying paradigm, consider the following comprehensive breakdown:\n\n"
    "| Domain Stratum | Architectural Impact | Complexity Rating | Deployment Velocity |\n"
    "|---|---|---|---|\n"
    "| Primary Execution | Minimal Overhead | O(1) Constant | Instantaneous |\n"
    "| Secondary Isolation | Distributed Scope | O(N) Linear | Asynchronous |\n\n"
    "* Key Takeaway 1: Extended context buffers increase text length without adding informational signal.\n"
    "* Key Takeaway 2: Detailed elaboration sections often fool uncalibrated LLM judges due to verbosity bias.\n"
    "* Key Takeaway 3: Maintaining empirical rigour requires testing calibrated Dual A/B position swapping.\n\n"
    "In conclusion, thorough documentation and elaborate formatting provide structural readability across all enterprise software deployment strategies."
)


def generate_variations(topic_item: dict) -> list[dict]:
    correct = topic_item["correct_answer"]
    flawed = topic_item["flawed_answer"]

    return [
        {
            "variation_type": "baseline",
            "answer_a": correct,
            "answer_b": flawed,
            "expected": "A",
        },
        {
            "variation_type": "position_swap",
            "answer_a": flawed,
            "answer_b": correct,
            "expected": "B",
        },
        {
            "variation_type": "verbosity_pad",
            "answer_a": correct,
            "answer_b": flawed + VERBOSITY_PADDING,
            "expected": "A",
        },
    ]


def http_post(url: str, json_data: dict, timeout: float = 120.0) -> tuple[int, dict | str]:
    body_bytes = json.dumps(json_data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.status
            res_body = response.read().decode("utf-8")
            try:
                return status, json.loads(res_body)
            except Exception:
                return status, res_body
    except urllib.error.HTTPError as http_err:
        err_body = http_err.read().decode("utf-8")
        try:
            return http_err.code, json.loads(err_body)
        except Exception:
            return http_err.code, err_body
    except Exception as exc:
        return 500, str(exc)


def http_get(url: str, timeout: float = 5.0) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8")
    except Exception as exc:
        return 500, str(exc)


def run_seeder():
    print("=" * 80)
    print("🚀 JUDGELAB AUTOMATED SEEDER — Populating PostgreSQL Evaluation Database")
    print(f"Target Backend: {BACKEND_URL}")
    print(f"Models ({len(MODELS)}): {', '.join(MODELS)}")
    print(f"Topics ({len(TOPICS)}): Overfitting, Docker vs VMs, JWT Security")
    print(f"Total Evaluations: {len(MODELS) * len(TOPICS) * 3} runs")
    print("=" * 80 + "\n")

    # Health check
    status, body = http_get(f"{BACKEND_URL}/health")
    if status == 200:
        print("✅ Backend connection verified: HTTP 200 OK\n")
    else:
        print(f"❌ Failed to connect to FastAPI backend at {BACKEND_URL}.")
        print("   Please start the backend server from the project root using:")
        print("   .venv\\Scripts\\python.exe -m uvicorn backend.main:app --reload\n")
        sys.exit(1)

    total_runs = len(MODELS) * len(TOPICS) * 3
    run_count = 0
    success_count = 0
    start_time = time.time()

    for model in MODELS:
        print(f"\n🤖 MODEL STRATUM: [{model}]")
        print("-" * 60)

        for topic in TOPICS:
            variations = generate_variations(topic)

            for var in variations:
                run_count += 1
                payload = {
                    "question": topic["question"],
                    "answer_a": var["answer_a"],
                    "answer_b": var["answer_b"],
                    "model_name": model,
                    "temperature": 0.0,
                    "mitigation_strategy": "dual_ab",
                }

                print(f"[{run_count:02d}/{total_runs:02d}] Model: {model[:25]:<25} | Topic: {topic['id']:<12} | Var: {var['variation_type']:<13} ... ", end="", flush=True)

                t0 = time.time()
                status, data = http_post(f"{BACKEND_URL}/api/evaluate/calibrated", payload, timeout=120.0)
                elapsed = round(time.time() - t0, 2)

                if status == 200 and isinstance(data, dict):
                    winner = data.get("final_calibrated_winner", "UNKNOWN")
                    bias_flipped = data.get("position_bias_detected", False)
                    success_count += 1
                    print(f"DONE ({elapsed}s) | Winner: {winner} | Flip: {bias_flipped}")
                else:
                    err_msg = data.get("detail", str(data)) if isinstance(data, dict) else str(data)
                    print(f"FAILED (HTTP {status}): {err_msg[:80]}")

                time.sleep(0.1)

    total_elapsed = round(time.time() - start_time, 2)
    print("\n" + "=" * 80)
    print(f"🎉 SEEDING COMPLETE: {success_count}/{total_runs} evaluations processed successfully in {total_elapsed}s.")
    print("=" * 80)


if __name__ == "__main__":
    run_seeder()
