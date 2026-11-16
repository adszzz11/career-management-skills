# Career onboarding

Use a private working directory chosen by the user. For the commands below, `SKILL` is the absolute path to `skills/career-tree` and `WORK` is the user's private career directory. Never place real data in the skill repository.

1. Ask whether the user has an existing resume or career description. If so, read the provided file, extract company, role and problem information into the tree described in `schema.md`, and ask the user to confirm dates, role boundaries and any missing or uncertain details. Preserve the original. If there is no source, interview one company and role at a time: what they did, challenges, actions, outcomes and measured results. Ask targeted follow-ups; save each confirmed role as you go. Do not invent facts or metrics.
2. Ask for information needed for the desired output, such as name, contact details, education, skills, activities and design preferences. Save only the necessary personal profile in `$WORK/profile.yaml`, using `design/profile.yaml.example` as a guide. Do not request or expose personal data beyond the task.
3. Validate and extract the tree:

   ```sh
   python3 "$SKILL/scripts/validate_tree.py" "$WORK/components"
   python3 "$SKILL/scripts/extract.py" --tree-dir "$WORK/components" --out "$WORK/career-data.json"
   python3 "$SKILL/dashboard/build.py" --data "$WORK/career-data.json" --profile "$WORK/profile.yaml" --out "$WORK/dashboard.html"
   ```

   If extraction reports warnings or returns 2, present them to the user rather than resolving ambiguous facts by guessing. Show the dashboard locally when possible and incorporate corrections.
4. For a job-specific package, read the job description provided by the user or verify its public source, then run:

   ```sh
   python3 "$SKILL/scripts/generate_application.py" --data "$WORK/career-data.json" --profile "$WORK/profile.yaml" --company "Example Company" --role "Example Role" --jd-file "$WORK/jd.txt" --out-dir "$WORK/application"
   ```

   Omit `--jd-file` if no job description is supplied. The output includes HTML documents, a selection rationale, and JD text when supplied. Review the results and fill any motivation TODO with the user's input. PDF generation uses the same command with `--confirm-pdf` after review and requires Chrome. Do not treat a generated package as submitted.
5. Manage reviewed versions with `career-files`, using an explicit `--root` pointing to the private career directory. Review generated facts, document completeness, formatting, and confidentiality before any sharing.
