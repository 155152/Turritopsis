# Security policy

## Supported versions

Security fixes are applied to the latest release on `main`. The current supported
release line is `0.2.x`.

## Reporting a vulnerability

Please do not publish credentials, private project knowledge, or exploit details in
a public issue. Use GitHub's **Security** tab and **Report a vulnerability** when that
option is available. If private reporting is unavailable, open a minimal issue asking
the maintainer for a private contact channel without including sensitive details.

Include the affected version, operating system, reproduction steps, impact, and any
suggested mitigation. You should receive an acknowledgement within seven days.

## Deployment boundary

Turritopsis is local-first and listens on loopback by default. It has no built-in HTTP
authentication. If you deliberately bind it to a non-loopback address, place it behind
an authentication and TLS layer. Anyone who can reach an unprotected server may be able
to read or modify project knowledge.

Repository scanning and LLM-backed maintenance use conservative credential heuristics,
not a complete secret scanner. Review generated evidence before sending it to an external
model, keep sensitive files outside the scan boundary, and use environment variables for
provider credentials.
