# Security Policy

## Scope

CyberHost APE is a toolkit that **orchestrates** third-party security tools; it
downloads and launches them. Report issues in **CyberHost's own code** here
(e.g. the resolver/updater download & extraction path, command handling,
path/traversal handling). Vulnerabilities in bundled third-party tools should be
reported to those projects upstream.

## Reporting a vulnerability

Please **do not** open a public issue for a security vulnerability.

- Use GitHub's **private vulnerability reporting** (Security → Report a
  vulnerability) on this repository, or
- email the maintainers at the address listed on the project page.

Include: affected version/commit, a clear description, reproduction steps, and
impact. We aim to acknowledge within 7 days and to provide a remediation
timeline after triage.

## Supported versions

The latest released version receives security fixes. Because the kit is
self-updating (`update --self`), please confirm the issue on the latest release
before reporting.

## Hardening notes (by design)

- Archive extraction rejects path-traversal ("zip-slip") entries and uses the
  tar `data` filter where available.
- Checksums are verified when upstream publishes them.
- Downloads come only from each tool's official source as declared in
  `tools.yaml`; `update --self` refreshes that mapping.
