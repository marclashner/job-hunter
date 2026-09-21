# JobEvaluationAgent

`JobEvaluationAgent` uses the OpenAI Agents SDK (`Agent` + `Runner` + Pydantic `output_type`) to decide whether a listing is worth the candidate's time. It does not write or submit applications.

`POST /jobs/{id}/evaluate` loads the job, primary profile, evidence, and `HardFilterResult`, runs the agent, grounds the output, and stores a `job_evaluations` row.

## Configuration

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Required for the live agent |
| `OPENAI_MODEL` | Default `gpt-4o-mini` (structured classification, not a reasoning-max model) |
| `OPENAI_EVALUATION_TEMPERATURE` | Default `0` |
| `OPENAI_EVALUATION_SEED` | Unused by the OpenAI Responses API (kept in settings for later providers) |

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

## Grounding

The closed world is `CandidateEvidence`. Unknown profile fields are not skills. The agent instructions and an output guardrail plus `ground_evaluation()` all reject unsupported citations.
