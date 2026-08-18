# Pre-controlled-execution contract

This contract is planning metadata, not controlled evidence. Real execution is
prohibited unless the source snapshot, pricing verification, and external model
routing checks are completed and recorded.

- Dataset checksum: `b2fff1524b199fb2d302b7c4ebd752a9a47d32bab68a232ab06b7b1e07fa1510`
- DatasetVersion: `2f8c7bba-08b1-4d8b-8b0e-b564e8a61886`
- Canonicalization: `unordered-pair-consensus-v1`
- Prompt: `controlled-judge-pairwise-v1`; its SHA-256 is calculated by
  `controlled_prompt.prompt_hash()` and persisted in planned manifests.
- Protocol: `phase3-controlled-v1`
- Analysis: `phase4-analysis-v1`
- Retry policy: `controlled-retry-v2`
- Failure policy: `controlled-failure-v2`
- Planned units/calls: 13,400 / 16,600

## Frozen execution settings

- Judge routes: `gpt-4o-mini` via OpenAI; `anthropic/claude-3-haiku`,
  `deepseek/deepseek-chat`, and `meta-llama/llama-3.3-70b-instruct` via
  OpenRouter.  No aliasing or silent model substitution is permitted.
- Required request settings: structured JSON, `temperature`, `top_p`, an
  explicit seed only where the registry says it is supported, and a 350-token
  maximum output budget. Unsupported settings fail locally before transport.
- Pricing: `pre-execution-pricing-v1` remains
  `PRICING_VERIFICATION_REQUIRED`. On 2026-08-18 the local environment could
  not reach the official OpenAI pricing page (proxy/certificate-revocation
  failure); no price has been inferred or guessed. This blocks a REAL profile.
- Ambiguity: a crash after the outbound boundary records `AMBIGUOUS`; only an
  operator-recorded `RECOVERED_SUCCESS`, `FAILED_FINAL`, or
  `AUTHORIZED_RERUN` resolution may move it forward. Automatic resend is
  forbidden.
- OpenRouter routing: `controlled-openrouter-routing-v1` is fail-closed and
  now frozen as `controlled-routing-v1`: Claude Haiku → `amazon-bedrock`,
  DeepSeek Chat → `streamlake`, and Llama 3.3 70B → `deepinfra/turbo`.
  Controlled requests use `provider.order`/`provider.only`, `allow_fallbacks=false`,
  `require_parameters=true`, and `X-OpenRouter-Metadata: enabled`. Changing
  this configuration changes the routing fingerprint and requires manifest
  regeneration before execution.

## Routing, transport, and pricing

- OpenAI `gpt-4o-mini`: direct OpenAI; native structured JSON enabled.
- OpenRouter judges: prompt-enforced strict JSON plus parser; native transport
  JSON mode is not required for scientific validity.
- Capability policy: temperature/top-p supported for all judges; seed supported
  only for GPT-4o-mini and recorded as NOT_SUPPORTED elsewhere; max output 350.
- Pricing config: `pricing-config-v1`, externally verified 2026-08-18, USD.

## Final routing manifests

- RQ1 `e8f1c2a754fc703326aeef55a6f38a8eeb935a298f78507a8c23b42deb769080`
- RQ2 `185a928a5a4546bf823cd5e84e977f1df8e75de801f74bc2bddcfe99e4e4fdd1`
- RQ3 `7da12bed902b5fdb81fa509ea65f4d601372cafc72a6cbac790fea396cb51b07`
- RQ4 `8832891654525fc823a679a2245c2f9220467abbab58580b0523dbbe018a0f0a`
- RQ5 `9e2652cc612fd19eea541065657aa63f5e9ff34ff7b9a74488c7745476eba0c8`
- RQ6 `06c5c1ad1a78e47f69b7285635771be47e437b3a6246e68fc0866dcfa56281ef`
- RQ7 `4049fe075f81704238f2e4f31be3afe09b11a76f57f7287264f51e83826901c4`

Material changes to canonicalization, prompt, model routing, parameters,
variant generation, pass mapping, retry/failure policy, or metrics require a
new source commit, version review, and manifest regeneration before execution.
