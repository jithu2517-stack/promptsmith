# Security policy

## Supported versions

Security fixes are applied to the latest version on the default branch.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or accidentally exposed
credential. Use GitHub's private vulnerability reporting for this repository, or
contact the maintainer through the email shown on the GitHub profile. Include
reproduction steps, impact, and any relevant version information.

PromptSmith reads provider API keys from environment variables. Never commit keys,
vaults containing secrets, or `.env` files. Review prompts before sending them to a
remote provider because prompts and variables may contain sensitive data.
