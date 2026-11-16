# Career tree schema

Use the YAML subset supported by `scripts/minimal_yaml.py`: no anchors, aliases or flow mappings. Quote strings containing `:` or `#`.

Every company, optional group and role is a directory with one `root.yaml`. Each problem is a separate YAML file in its role directory.

- Company: `type: company`, required `title`; optional `period`, `description`, `attachments`.
- Group: `type: group`, required `title`; optional `description`.
- Role: `type: role`, required `title` and `period`; optional `headcount`, `tags`, `one_liner`, `summary`, `stack`, `key_results`, `responsibilities`, `attachments`.
- Problem: `type: problem`, required `title`, `issue`, `resolution`, `result`; optional `attachments`.

Attachments are lists of entries with `label`, `type` (`image`, `file`, or `link`), and `path` for files or `url` for links. Use descriptive names for directories and problem files. See `tests/fixtures/tree/companyA` for a synthetic example. Validate with `scripts/validate_tree.py`.
