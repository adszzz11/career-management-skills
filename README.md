# Career management skills

Reusable agent skills for organizing career history, interviewing for missing details, preparing resumes and application documents, and managing document versions. Supports Claude Code plugin discovery; a Codex agent can read `skills/career-tree/SKILL.md` and `skills/career-files/SKILL.md` directly.

## Start

Open this repository in your agent and say:

> Use the career management skills in this repository to organize my career and create my resume. Ask whether I have an existing resume first, and ask about anything you need to know.

The agent should follow `skills/career-tree/SKILL.md` and `ONBOARDING.md`. It will ask for an existing resume or interview you, build a company/role/problem tree, check uncertain facts, and prepare documents for review. Use `skills/career-files/SKILL.md` to manage reviewed versions and local submission records. The scripts do not submit applications.

Keep your own documents and personal data in a private workspace, separate from this skill repository. `career-data/` is ignored as an additional safeguard, not a substitute for checking files before sharing. Do not commit real profiles or generated documents.

Python 3.10+ is required; the scripts use the standard library. PDF export requires a compatible browser. This is an early-stage package; review generated facts, formatting, and privacy before sharing.

Run tests with `bash skills/career-tree/tests/run_tests.sh` and `python3 skills/career-files/tests/test_career_files.py`.
