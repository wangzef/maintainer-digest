# Contributing

Thanks for helping maintainers spend less time assembling reports. English and Chinese issues and pull requests are welcome.

## Run locally

Python 3.10+ is required; runtime and unit tests use the standard library.

```bash
python3 -m unittest discover -s tests -v
python3 -m maintainer_digest --input examples/demo-snapshot.json --lang en
```

Before a PR, explain the user-visible problem and include a focused regression test when changing collection or counting logic. Keep documentation in both languages consistent. Do not add a runtime dependency without explaining why it is needed.

Useful contributions include reproducible pagination errors, counting-boundary cases, clearer bilingual wording, accessibility of generated Markdown, and real maintainer workflows. Start by discussing larger changes in an issue. Avoid unsolicited automated PRs to unrelated projects.

## Data and honesty

Use synthetic, clearly labeled snapshots in tests. Never upload tokens, private repository data, or another person's private contact details. Real usage examples require permission from the relevant project. Do not invent users, stars, testimonials, maintenance history, or program acceptance claims.

## Review

The maintainer reviews the behavior, test evidence, compatibility with Python 3.10+, and counting semantics. There is no guaranteed response time. Security reports belong in the private channel described in [SECURITY.md](SECURITY.md).

## Conduct

Be considerate, stay technical, and respect maintainers' time. Harassment, personal attacks, spam, and fabricated activity are not welcome. The maintainer may moderate disruptive participation.

By contributing code, you agree to license your contribution under this project's MIT license.
