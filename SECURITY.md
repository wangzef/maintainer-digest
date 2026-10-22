# Security policy

This is an early-stage tool. The latest source on `main` is the supported version; there is no security-response SLA.

For suspected vulnerabilities, use GitHub's private vulnerability reporting if it is enabled on this repository. If it is unavailable, open an issue requesting a private contact channel **without disclosing exploit details or sensitive data**.

The client reads only `https://api.github.com` and refuses redirects. Tokens come from `GH_TOKEN` or `GITHUB_TOKEN`; use read-only permissions and repository restrictions. The tool does not post issues, merge code, or change settings. It escapes Markdown table content and only renders GitHub HTTPS source links.

Saved snapshots contain raw API records, which can include issue/PR bodies and private metadata. JSON metrics include selected records and may also contain private information. Store them with appropriate filesystem permissions; do not publish private-repository reports as public Actions artifacts.

No guarantee is made that output derived from an untrusted snapshot is safe for every downstream renderer. Review it before embedding in a site or another automation system.
