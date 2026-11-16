---
name: career-tree
description: Organize a user's career history through interviews or existing resumes, maintain a company-role-problem tree, and generate a resume, career description, dashboard, or job-specific application package.
---

# Career tree

When asked to organize a career or create a resume, read [ONBOARDING.md](ONBOARDING.md), follow the relevant route, and respond in the user's language. Ask for an existing resume or career document; if none is available, interview the user one role at a time. Preserve original evidence, ask about missing or uncertain facts, and never invent metrics, accomplishments, employment dates, or motivation.

Keep personal source documents, profile, tree, generated files and application records in a private user workspace, outside this repository. Confirm the location with the user when unclear. Never upload, publish, or apply on the user's behalf without explicit authorization. Existing submitted documents should remain unchanged.

For the tree structure see [schema.md](schema.md). Use the scripts relative to this skill directory, passing absolute input/output paths. The extractor returns exit code 2 when it detects ambiguities: show the warnings and ask the user before deciding. Validate the tree before generating documents. Use explicit `--profile` for the dashboard and application generator so personal data stays outside the skill installation.

Before first document generation, ask about page count, layout and palette. Available palettes are blue, mono and modern; see [design/templates.md](design/templates.md). Generate HTML first, review its factual and visual content with the user, then generate PDF if requested. Cover-letter motivation is left as TODO. The renderer only covers career data; incorporate education, activities, and other user-provided profile sections as needed, and verify the final document.

Use the companion `career-files` skill to manage current and archived documents and local submission records. Those operations do not submit applications externally.
