---
name: career-files
description: Manage reviewed resumes, career descriptions and application documents, including current versions, archives, and local application records.
---

# Career files

Choose a private work directory and always pass it as `--root` to `scripts/career_files.py`. The tool keeps latest documents in `current/`, previous versions in `archive/YYYYMMDD/`, and local application copies in dated folders under `applications/<company>/`. Keep career facts in `components/`.

- `python3 <skill>/scripts/career_files.py --root <directory> status` shows current files and application records.
- `... check` checks file placement and versions.
- `... promote <files...>` moves reviewed new versions to current and archives prior versions.
- `... submit <company> --position <role> <files...>` makes local copies and records an application. It does not send anything externally.

Names must end in `_YYYYMMDD` before the extension. Check targets and conflicts before moving files. Preserve archived and submitted copies. Tracked files may be moved with `git mv`; do not commit private documents without explicit user authorization. External submissions require explicit authorization and are outside this tool.
