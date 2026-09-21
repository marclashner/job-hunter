# JobEvaluationAgent

`JobEvaluationAgent` uses the OpenAI Agents SDK (`Agent` + `Runner` + Pydantic `output_type`) to decide whether a listing is worth the candidate's time. It does not write or submit applications.

`POST /jobs/{id}/evaluate` loads the job, primary profile, evidence, and `HardFilterResult`, runs the agent, grounds the output, and stores a `job_evaluations` row.

`POST /evaluation/batch` is an in-process pipeline (no Celery or other queue): load unevaluated jobs, discard deterministic hard-filter failures without calling the model, run `JobEvaluationAgent` on the rest, persist, and return a summary. Jobs are processed independently; one failure is logged and the batch continues. Already-evaluated jobs are skipped unless `reevaluate` is true. `dry_run` runs hard filters only and does not call the model or write rows.

## Configuration

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Required for the live agent |
| `OPENAI_MODEL` | Default `gpt-4o-mini` (structured classification, not a reasoning-max model) |
| `OPENAI_EVALUATION_TEMPERATURE` | Default `0` |
| `OPENAI_EVALUATION_SEED` | Unused by the OpenAI Responses API (kept in settings for later providers) |
| `EVALUATION_CONCURRENCY` | Default worker threads for batch (capped by `EVALUATION_CONCURRENCY_MAX`) |
| `EVALUATION_RATE_LIMIT_PER_MINUTE` | Spacing of model calls (`0` disables) |
| `EVALUATION_BATCH_LIMIT_DEFAULT` / `EVALUATION_BATCH_LIMIT_MAX` | How many jobs a batch will pick up |
| `OPENAI_INPUT_USD_PER_MILLION` / `OPENAI_OUTPUT_USD_PER_MILLION` | Used to estimate cost from token usage |

Temperature 0 and `top_p=1` are set for repeatable structured output. They do not make the model fully deterministic. `seed` is not sent because the OpenAI Responses API rejects it.

## Deterministic vs model

Always deterministic (code, not the LLM):

- Hard filters before the agent
- `overall_score` = sum of component scores
- `supporting_evidence_ids` must be in the provided `CandidateEvidence` set
- Skill tokens such as COBOL/Rust in **strengths** or **reasoning** must appear in evidence text
- Failed hard filters force `recommendation=reject`
- Empty evidence forces `evidence_strength=0` and demotes `apply` to `review`
- Hard-filter `missing_information` (including `job_salary`) is merged onto the evaluation

The model still chooses component scores, prose, and apply/review when the hard filter passed. That part can vary across runs even at temperature 0.

Batch evaluation records token usage and an estimated USD cost on `job_evaluations` when the Agents SDK exposes usage on the run result.

## Grounding

The closed world is `CandidateEvidence`. Unknown profile fields are not skills. The agent instructions and an output guardrail plus `ground_evaluation()` all reject unsupported citations.
