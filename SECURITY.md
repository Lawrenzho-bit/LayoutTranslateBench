# Security Policy

## Reporting a vulnerability

LayoutTranslateBench is a benchmark project — there is no production service to attack. The most likely concerns are:

- A malicious annotation file or submission JSONL that triggers parser bugs or denial-of-service in the scoring pipeline
- A supply-chain risk in a runner adapter that calls third-party APIs
- A dataset-level concern (e.g. a document contains content that should be redacted, or a license issue)

If you find a security issue, please open a **private** report:

1. Go to the **Security** tab on the GitHub repository.
2. Click **"Report a vulnerability"**.
3. Provide a clear description, steps to reproduce, and (if applicable) a suggested mitigation.

We commit to acknowledging reports within 5 business days and to publishing a fix (or a public advisory if a fix isn't feasible) within 30 days for high-severity issues.

For non-security bugs, use [regular GitHub Issues](https://github.com/Lawrenzho-bit/LayoutTranslateBench/issues).

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅         |
| < 0.1   | n/a (pre-release) |

## Out of scope

- Issues with third-party translation systems we benchmark — report those to the respective vendors.
- Issues with GitHub Pages, GitHub Actions, or other GitHub-operated infrastructure — report to GitHub directly.
