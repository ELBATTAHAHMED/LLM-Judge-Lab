"""
judge_engine.py
===============
Pure-function evaluation engine for the LLM-as-a-Judge Reliability Lab.

This module is intentionally decoupled from the database layer.  It only
knows how to:
  1. Build a G-EVAL style judge prompt (single-turn).
  2. Build a context-aware multi-turn judge prompt (injecting prior turn context).
  3. Call the OpenAI Chat Completions API.
  4. Parse the structured verdict out of the response.

All database interactions live in run_evaluation.py.

Methodology (G-EVAL — Single Turn)
-----------------------------------
The judge is instructed to:
  a) Read the question and both candidate answers carefully.
  b) Reason step-by-step about factual accuracy, coherence, helpfulness,
     and conciseness.
  c) Conclude with a single structured line: "WINNER: A", "WINNER: B",
     or "WINNER: TIE".

Methodology (Multi-Turn Consistency Extension)
-----------------------------------------------
For multi-turn evaluations, the judge receives:
  a) Turn 1's original question, both answers, and the judge's own Turn 1 verdict.
  b) Turn 2's follow-up question and both answers.
This allows post-hoc computation of a Logical Consistency Score: measuring
whether the judge preserves a coherent relative quality ordering across turns.

The explicit reasoning is stored verbatim in JudgeDecision.reasoning so that
every decision is fully auditable and reproducible for your thesis.
"""

import os
import logging
import re
import time
from dataclasses import dataclass
from typing import Literal, Any

log = logging.getLogger(__name__)

# ── Types ─────────────────────────────────────────────────────────────────────

Verdict = Literal["A", "B", "TIE", "UNKNOWN"]


@dataclass(frozen=True)
class JudgeResult:
    """Structured output from one judge call."""
    verdict: Verdict          # "A", "B", "TIE", or "UNKNOWN" on parse failure
    reasoning: str            # Full raw response text from the model
    model_name: str           # Exact model identifier used (e.g. "gpt-4o")
    input_tokens: int         # Prompt token usage
    output_tokens: int        # Completion token usage


@dataclass(frozen=True)
class CalibratedJudgeResult:
    """Structured output from a real-time Dual A/B Swap calibrated evaluation."""
    original_order_winner: str     # Candidate winner from Pass 1 ("A", "B", "TIE", "UNKNOWN")
    swapped_order_winner: str      # Candidate winner from Pass 2 mapped back to original IDs
    final_calibrated_winner: str   # Final debiased consensus winner ("A", "B", "TIE", "UNKNOWN")
    position_bias_detected: bool   # True if Pass 1 and Pass 2 verdicts diverged
    reasoning_original: str        # Raw text from Pass 1
    reasoning_swapped: str         # Raw text from Pass 2
    detailed_reasoning: str        # Combined auditable reasoning narrative
    model_name: str                # Evaluator model identifier
    total_input_tokens: int        # Aggregate prompt tokens used
    total_output_tokens: int       # Aggregate completion tokens used


# ── Prompt Template ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an expert, impartial AI evaluator participating in a rigorous academic \
research study on the reliability of LLM-as-a-Judge systems.

Your task is to evaluate two candidate answers to a given question. You must:
1. Carefully read the question and both answers.
2. Reason step-by-step about the following four criteria:
   - **Factual Accuracy**: Is the information correct and well-grounded?
   - **Coherence**: Is the answer logically structured and easy to follow?
   - **Helpfulness**: Does the answer fully address what was asked?
   - **Conciseness**: Is the answer appropriately brief without omitting key details?
3. After your analysis, conclude your response with EXACTLY one of these three \
verdict lines on its own line:
   WINNER: A
   WINNER: B
   WINNER: TIE

The verdict line MUST appear at the very end of your response. Do not add any \
text after it. Do not use markdown formatting for the verdict line itself.
"""


def build_judge_prompt(
    question: str,
    answer_a: str,
    answer_b: str,
) -> list[dict[str, str]]:
    """
    Build the OpenAI messages list for a single judge evaluation.

    Parameters
    ----------
    question:  The original prompt/question text.
    answer_a:  Text of the answer assigned to Position A.
    answer_b:  Text of the answer assigned to Position B.

    Returns
    -------
    messages : list[dict]  Ready to pass to client.chat.completions.create().
    """
    user_content = (
        f"## Question\n{question}\n\n"
        f"## Answer A\n{answer_a}\n\n"
        f"## Answer B\n{answer_b}\n\n"
        "Please evaluate both answers according to the four criteria and provide "
        "your step-by-step reasoning, then state your verdict."
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user",   "content": user_content},
    ]


# ── Response Parser ───────────────────────────────────────────────────────────

# Matches "WINNER: A", "WINNER: B", or "WINNER: TIE" (case-insensitive,
# optional surrounding whitespace).
_VERDICT_PATTERN = re.compile(
    r"WINNER\s*:\s*(A|B|TIE)\b",
    re.IGNORECASE,
)


def parse_winner(response_text: str) -> Verdict:
    """
    Extract the structured verdict from the model's raw response text.

    Searches for the LAST occurrence of the verdict pattern so that if the
    model mentions "WINNER: A" in its reasoning body, only the final
    conclusion line is used.

    Returns "UNKNOWN" if no parseable verdict is found.
    """
    matches = _VERDICT_PATTERN.findall(response_text)
    if not matches:
        log.warning("No WINNER verdict found in response. Marking as UNKNOWN.")
        return "UNKNOWN"
    return matches[-1].upper()  # last match, normalised to uppercase


# ── Multi-Turn Context-Aware Prompt ──────────────────────────────────────────

_MULTITURN_SYSTEM_PROMPT = """\
You are an expert, impartial AI evaluator participating in a rigorous academic \
research study on the reliability of LLM-as-a-Judge systems.

You are evaluating a TWO-TURN conversation. You have already evaluated Turn 1 \
and reached a verdict. Now you must evaluate Turn 2 while staying LOGICALLY \
CONSISTENT with your Turn 1 judgment.

Your task:
1. Review the Turn 1 context and your prior verdict shown to you.
2. Carefully read the Turn 2 follow-up question and both candidate answers.
3. Reason step-by-step about:
   - **Factual Accuracy**: Is the Turn 2 answer correct and grounded?
   - **Coherence**: Does Turn 2 logically build on Turn 1?
   - **Helpfulness**: Does Turn 2 fully address the follow-up question?
   - **Conciseness**: Is the answer appropriately concise?
   - **Consistency**: Does your verdict align with the relative quality \
difference you observed in Turn 1?
4. After your analysis, conclude with EXACTLY one verdict line:
   WINNER: A
   WINNER: B
   WINNER: TIE

The verdict line MUST appear at the very end of your response.
"""


def build_multiturn_judge_prompt(
    turn1_question: str,
    turn1_verdict: str,
    turn2_question: str,
    answer_a: str,
    answer_b: str,
) -> list[dict[str, str]]:
    """
    Build a context-aware multi-turn judge prompt.

    Injects the Turn 1 question and the judge's own prior Turn 1 verdict into
    the Turn 2 evaluation, enabling measurement of logical consistency.

    Parameters
    ----------
    turn1_question : The original Turn 1 prompt text.
    turn1_verdict  : The judge's verdict from Turn 1 ("A", "B", or "TIE").
    turn2_question : The follow-up Turn 2 prompt text.
    answer_a       : Text of the answer assigned to Position A.
    answer_b       : Text of the answer assigned to Position B.

    Returns
    -------
    messages : list[dict]  Ready to pass to client.chat.completions.create().
    """
    user_content = (
        f"## TURN 1 CONTEXT (Prior Evaluation)\n"
        f"**Turn 1 Question:** {turn1_question}\n"
        f"**Your Turn 1 Verdict:** WINNER: {turn1_verdict}\n\n"
        f"---\n"
        f"## TURN 2 EVALUATION (Current Task)\n"
        f"**Turn 2 Follow-up Question:** {turn2_question}\n\n"
        f"## Answer A\n{answer_a}\n\n"
        f"## Answer B\n{answer_b}\n\n"
        "Please evaluate Turn 2 using step-by-step reasoning across all criteria, "
        "then state your final verdict."
    )
    return [
        {"role": "system", "content": _MULTITURN_SYSTEM_PROMPT},
        {"role": "user",   "content": user_content},
    ]


def call_judge_multiturn(
    client,
    turn1_question: str,
    turn1_verdict: str,
    turn2_question: str,
    answer_a: str,
    answer_b: str,
    model_name: str = "gpt-4o",
    temperature: float = 0.0,
    max_retries: int = 5,
    initial_backoff: float = 2.0,
) -> "JudgeResult":
    """
    Call the OpenAI API for a context-aware multi-turn evaluation.

    Parameters
    ----------
    client          : openai.OpenAI instance.
    turn1_question  : Original Turn 1 prompt text.
    turn1_verdict   : The judge's prior verdict from Turn 1.
    turn2_question  : Turn 2 follow-up prompt text.
    answer_a        : Text of the answer shown in Position A.
    answer_b        : Text of the answer shown in Position B.
    model_name      : OpenAI model identifier.
    temperature     : Sampling temperature (0 = deterministic).
    max_retries     : Maximum retry attempts on retriable errors.
    initial_backoff : Initial wait time in seconds before first retry.

    Returns
    -------
    JudgeResult with verdict, full reasoning, model name, and token usage.
    """
    messages = build_multiturn_judge_prompt(
        turn1_question, turn1_verdict, turn2_question, answer_a, answer_b
    )
    backoff = initial_backoff

    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
            )
            raw_text: str = response.choices[0].message.content or ""
            verdict = parse_winner(raw_text)

            return JudgeResult(
                verdict=verdict,
                reasoning=raw_text,
                model_name=model_name,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )

        except Exception as exc:
            exc_str = str(exc)
            is_rate_limit   = "429" in exc_str or "rate_limit" in exc_str.lower()
            is_server_error = any(
                code in exc_str for code in ("500", "502", "503", "504")
            )
            if (is_rate_limit or is_server_error) and attempt < max_retries:
                wait = backoff * (2 ** (attempt - 1))
                log.warning(
                    "Retriable API error (attempt %d/%d): %s. Retrying in %.1fs ...",
                    attempt, max_retries, exc_str[:120], wait,
                )
                time.sleep(wait)
                continue
            raise


# ── Client & Local Model Resolver ──────────────────────────────────────────────

def is_local_model(model_name: str) -> bool:
    """
    Detect whether model_name indicates a local Ollama model instance.
    """
    if not model_name:
        return False
    m = model_name.lower().strip()
    return any(k in m for k in ("llama", "ollama", "vicuna", "mistral-local", "local"))


def get_evaluator_client(model_name: str, client=None) -> tuple[Any, str]:
    """
    Resolve and return an appropriate OpenAI-compatible client instance and target model name.

    If model_name is a local model (Ollama):
      - Configures OpenAI client with base_url="http://localhost:11434/v1", api_key="ollama".
      - Sanitizes model identifier to "llama3" (or matching local tag).

    If model_name is a cloud OpenAI model:
      - Uses provided client or instantiates OpenAI(api_key=os.getenv("OPENAI_API_KEY")).
    """
    import openai

    if is_local_model(model_name):
        target_model = "llama3" if ("llama" in model_name.lower() or "ollama" in model_name.lower()) else model_name
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        local_client = openai.OpenAI(
            base_url=base_url,
            api_key="ollama",
            timeout=240.0,  # 4 minutes timeout for local Ollama model inference
        )
        return local_client, target_model

    if client is not None:
        return client, model_name

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("your_"):
        raise ValueError("OPENAI_API_KEY environment variable is not properly configured in .env.")

    return openai.OpenAI(api_key=api_key, timeout=120.0), model_name


# ── API Caller ────────────────────────────────────────────────────────────────

def call_judge(
    client=None,       # openai.OpenAI instance or None (auto-resolved if None)
    question: str = "",
    answer_a: str = "",
    answer_b: str = "",
    model_name: str = "gpt-4o-mini",
    temperature: float = 0.0,
    max_retries: int = 5,
    initial_backoff: float = 2.0,
) -> JudgeResult:
    """
    Call the OpenAI or local Ollama API and return a structured JudgeResult.
    """
    if is_local_model(model_name):
        # Cap retries and backoff for local Ollama models to prevent hanging wait cascades
        max_retries = min(max_retries, 2)
        initial_backoff = min(initial_backoff, 0.5)

    resolved_client, effective_model = get_evaluator_client(model_name, client)
    messages = build_judge_prompt(question, answer_a, answer_b)
    backoff = initial_backoff

    for attempt in range(1, max_retries + 1):
        try:
            response = resolved_client.chat.completions.create(
                model=effective_model,
                messages=messages,
                temperature=temperature,
            )
            raw_text: str = response.choices[0].message.content or ""
            verdict = parse_winner(raw_text)

            input_toks = response.usage.prompt_tokens if response.usage else 0
            output_toks = response.usage.completion_tokens if response.usage else 0

            return JudgeResult(
                verdict=verdict,
                reasoning=raw_text,
                model_name=model_name,
                input_tokens=input_toks,
                output_tokens=output_toks,
            )

        except Exception as exc:
            exc_str = str(exc)
            if is_local_model(model_name) and any(err in exc_str.lower() for err in ("connection", "connect", "11434", "refused", "unreachable")):
                raise RuntimeError(
                    "Local Ollama server is offline or unreachable at http://localhost:11434. "
                    "Please run 'ollama serve' and ensure the model 'llama3' is pulled."
                ) from exc

            is_rate_limit   = "429" in exc_str or "rate_limit" in exc_str.lower()
            is_server_error = any(
                code in exc_str for code in ("500", "502", "503", "504")
            )

            if (is_rate_limit or is_server_error) and attempt < max_retries:
                wait = backoff * (2 ** (attempt - 1))
                log.warning(
                    "Retriable API error (attempt %d/%d): %s. Retrying in %.1fs …",
                    attempt, max_retries, exc_str[:120], wait,
                )
                time.sleep(wait)
                continue

            raise


# ── Active Calibrated API Caller (Dual A/B Swap) ──────────────────────────────

def call_calibrated_judge(
    client=None,
    question: str = "",
    answer_a: str = "",
    answer_b: str = "",
    model_name: str = "gpt-4o-mini",
    temperature: float = 0.0,
    max_retries: int = 5,
    initial_backoff: float = 2.0,
) -> CalibratedJudgeResult:
    """
    Execute real-time in-flight bias mitigation via Dual A/B Position Swapping.
    Supports both OpenAI Cloud and Local Ollama models natively.
    """
    resolved_client, effective_model = get_evaluator_client(model_name, client)

    import concurrent.futures

    def _eval_pass_1():
        return call_judge(
            client=resolved_client,
            question=question,
            answer_a=answer_a,
            answer_b=answer_b,
            model_name=effective_model,
            temperature=temperature,
            max_retries=max_retries,
            initial_backoff=initial_backoff,
        )

    def _eval_pass_2():
        return call_judge(
            client=resolved_client,
            question=question,
            answer_a=answer_b,
            answer_b=answer_a,
            model_name=effective_model,
            temperature=temperature,
            max_retries=max_retries,
            initial_backoff=initial_backoff,
        )

    # Dispatch Pass 1 and Pass 2 concurrently in parallel threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(_eval_pass_1)
        f2 = executor.submit(_eval_pass_2)
        res1 = f1.result()
        res2 = f2.result()

    cand_winner_1 = res1.verdict  # "A", "B", "TIE", "UNKNOWN"
    verdict2 = res2.verdict

    # Map Pass 2 verdict back to original Candidate A/B IDs
    if verdict2 == "A":
        cand_winner_2 = "B"
    elif verdict2 == "B":
        cand_winner_2 = "A"
    elif verdict2 == "TIE":
        cand_winner_2 = "TIE"
    else:
        cand_winner_2 = "UNKNOWN"

    # Consensus & Mitigation Logic
    if cand_winner_1 == cand_winner_2:
        position_bias_detected = False
        final_calibrated_winner = cand_winner_1
    else:
        position_bias_detected = True
        final_calibrated_winner = "TIE"

    log.info(
        "Dual A/B Swap Evaluation completed: Pass 1 Winner=%s | Pass 2 Mapped Winner=%s | Bias Detected=%s | Final Winner=%s",
        cand_winner_1, cand_winner_2, position_bias_detected, final_calibrated_winner
    )

    detailed_reasoning = (
        f"=== PASS 1 EVALUATION (Original Order: A vs B) ===\n"
        f"Position A: Candidate A | Position B: Candidate B\n"
        f"Raw Verdict: WINNER: {res1.verdict}\n"
        f"Step-by-Step Reasoning:\n{res1.reasoning}\n\n"
        f"=== PASS 2 EVALUATION (Swapped Order: B vs A) ===\n"
        f"Position A: Candidate B | Position B: Candidate A\n"
        f"Raw Verdict: WINNER: {res2.verdict} (Mapped Candidate ID: {cand_winner_2})\n"
        f"Step-by-Step Reasoning:\n{res2.reasoning}\n\n"
        f"=== ACTIVE BIAS MITIGATION SYNTHESIS ===\n"
        f"Position Order Bias Detected: {position_bias_detected}\n"
        f"Pass 1 Choice: Candidate {cand_winner_1}\n"
        f"Pass 2 Choice: Candidate {cand_winner_2}\n"
        f"Final Calibrated Verdict: WINNER: {final_calibrated_winner}"
    )

    return CalibratedJudgeResult(
        original_order_winner=cand_winner_1,
        swapped_order_winner=cand_winner_2,
        final_calibrated_winner=final_calibrated_winner,
        position_bias_detected=position_bias_detected,
        reasoning_original=res1.reasoning,
        reasoning_swapped=res2.reasoning,
        detailed_reasoning=detailed_reasoning,
        model_name=model_name,
        total_input_tokens=res1.input_tokens + res2.input_tokens,
        total_output_tokens=res1.output_tokens + res2.output_tokens,
    )


# ── Ollama Local Model Caller ──────────────────────────────────────────────────

def call_ollama_judge(
    question: str,
    answer_a: str,
    answer_b: str,
    model_name: str = "llama3",
    ollama_url: str = "http://localhost:11434/api/generate",
    temperature: float = 0.0,
) -> JudgeResult:
    """
    Call a local Ollama model instance (e.g. Llama-3) for pairwise evaluation.
    """
    import json
    import urllib.request

    messages = build_judge_prompt(question, answer_a, answer_b)
    system_prompt = messages[0]["content"]
    user_prompt = messages[1]["content"]

    payload = {
        "model": model_name,
        "prompt": f"{system_prompt}\n\n{user_prompt}",
        "stream": False,
        "options": {
            "temperature": temperature,
        }
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ollama_url,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        response_json = json.loads(resp.read().decode("utf-8"))
        raw_text = response_json.get("response", "")
        verdict = parse_winner(raw_text)

        return JudgeResult(
            verdict=verdict,
            reasoning=raw_text,
            model_name=f"ollama/{model_name}",
            input_tokens=response_json.get("prompt_eval_count", 0),
            output_tokens=response_json.get("eval_count", 0),
        )

