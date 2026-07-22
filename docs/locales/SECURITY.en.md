<p align="right">
  <strong>English</strong> ·
  <a href="../../SECURITY.md">简体中文</a>
</p>

# Security Policy

## Supported Versions

Only the latest stable release receives security fixes. Get the latest version from [GitHub Releases](https://github.com/liushafeiniao/SheetToConfig/releases).

| Version | Status |
|---|---|
| Latest 1.x | ✅ Receives security fixes |
| Older versions | ❌ No longer maintained |

## Reporting a Vulnerability

**Please report security issues through [GitHub Private Vulnerability Reporting](https://github.com/liushafeiniao/SheetToConfig/security/advisories/new).** Reports are visible only to project maintainers, and you can discuss details privately within the advisory.

If the private form is temporarily unavailable, open a public issue stating only that the private reporting form is unavailable. **Do not include vulnerability details, a PoC, or personal contact information in that issue.** A maintainer will check and restore the reporting channel; submit the report through the private form once it is available.

### What to Include

- Affected version and operating system
- Reproduction steps or a proof of concept (PoC)
- Potential impact
- Suggested fixes, if you have any

## Response Targets

- We aim to acknowledge reports with an initial assessment **within 7 days**; complex cases or holidays may take longer
- Confirmed vulnerabilities are prioritized by severity, with timing and disclosure coordinated with the reporter
- With the reporter's consent, a fix may include credit in `CHANGELOG.md`; anonymity is always available
- Please do not disclose vulnerability details before a coordinated fix or security advisory is ready

## Scope

SheetToConfig is a local desktop application that processes user-supplied Excel configuration sheets. We are particularly interested in:

- Code execution or application crashes triggered by maliciously crafted Excel files
- Path traversal in the export pipeline (writing outside the intended directory)
- Unauthorized reads or writes of local configuration files or project data
- Supply-chain risks in third-party dependencies (`requirements*.txt`)

The following are generally **not considered** security issues in this project:

- Attacks that require the attacker to already have local user privileges
- Generic issues in the PyQt / Python runtime itself (please report those upstream)
- Social engineering or physical access attacks

## Code of Conduct

All interactions during security research are also governed by the [Code of Conduct](../../CODE_OF_CONDUCT.md).
