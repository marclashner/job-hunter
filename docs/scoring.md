# Job scoring: hard filters vs later LLM judgment

Hard filters are the first, deterministic gate. They decide whether a listing is *eligible* for the candidate. They do not score fit, write applications, or interpret prose beyond small keyword tables.

`POST /jobs/{id}/hard-filter` loads the job and the primary `CandidateProfile`, then returns a `HardFilterResult`.

## Result contract

| Field | Meaning |
| --- | --- |
| `passed` | `true` when `failed_rules` is empty |
| `failed_rules` | Knock-out rule ids that fired |
| `warnings` | Non-fatal issues (contradictory fields, currency mismatch, unclassified title) |
| `missing_information` | Job or candidate fields the engine needed but did not have |
| `salary_unknown` | `true` when the job has neither `salary_min` nor `salary_max` |

**Missing information does not fail the job.** An unlisted salary sets `salary_unknown: true` and records `job_salary` in `missing_information`. The same pattern applies to remote policy, location, seniority, employment type, and industry.

## Deterministic (this engine)

These rules use structured fields and closed keyword lists only:

- **Unacceptable onsite requirement** — candidate `remote_preference=remote` and job `remote_policy` is `onsite` or `hybrid`. Unknown policy does not fail.
- **Unacceptable location** — job is onsite/hybrid and its `location` does not match `preferred_locations`. Remote jobs skip this rule. Blank location does not fail.
- **Minimum seniority** — job seniority rank is below the candidate's stored seniority. Unknown job seniority does not fail.
- **Unacceptable employment type** — job type is set and is not in `employment_preferences`. Empty preferences disable the rule.
- **Minimum compensation** — only when a salary number exists. Fail if `salary_max` is present and below the annualized minimum. If only `salary_min` is present and it is below the floor, emit `salary_ceiling_unknown` and do not fail. Currency mismatch is a warning, not a failure. Unlisted salary never fails.
- **Target role/title mismatch** — role *family* (software IC vs management vs design vs recruiting vs science) plus software specializations (frontend/backend/ai/…) when the candidate's targets are specialized and do not include a generic SWE title. Unclassified titles warn and pass.
- **Excluded industry** — if `excluded_industries` is configured on the candidate snapshot, fail when title/company/department/description contains a known alias. No detected industry does not fail.

Contradictory `location` text vs `remote_policy` (for example policy `onsite` and location `Remote — US`) adds `contradictory_location_information` and still applies the structured `remote_policy` to the onsite rule.

## Delegated to the LLM later

Do **not** put these in hard filters:

- Overall fit, ranking, or a numeric score
- Whether a long description *really* means remote, hybrid, or onsite when `remote_policy` is missing
- Parsing compensation, visas, or clearance out of prose (`$120k` in the title is ignored unless `salary_*` is set)
- Industry when it is only implied (culture, customer stories, “fintech-like”)
- Whether “Staff Engineer — Payments” is a good next role versus “Senior Backend Engineer”
- Skill-by-skill evidence matching, stack depth, or healthcare/AI claim strength
- Cover letters, outreach, or any generated experience language
- Resolving contradictory listings beyond the warning above (which signal is true)

Agents must still obey candidate provenance: `unknown` profile fields are not facts; missing evidence is not a no.
