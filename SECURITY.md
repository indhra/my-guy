# Security policy

My Guy is an alpha recommendation-only CLI. Do not send vulnerability details through public issues. Use [GitHub's private security advisory form](https://github.com/indhra/my-guy/security/advisories/new) so the maintainer can investigate privately. Include the affected release tag, host, operating system, a minimal reproduction, and impact; remove tokens, private prompts, and unrelated personal data.

The first planned supported release is `v0.1.0`. Until it is published, there is no tagged release to patch. After publication, fixes will target the latest supported `v0.1.x` release; older alpha releases may require upgrading. The maintainer will coordinate disclosure and document affected versions in an advisory or release note.

My Guy reads third-party skill metadata as untrusted data, and does not execute providers. Approval bindings are not authentication against malicious code already running in the same Python process. Review a root before trusting it and avoid sharing private prompts in public reports.
