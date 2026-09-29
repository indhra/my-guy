"""Fail-closed identity checks for the manual tagged-install gate."""

import pytest

from scripts.verify_tagged_install import (
    ValidationError, validate_gate, validate_provenance,
)


SHA = "a" * 40


def valid(**overrides):
    values = dict(
        ref="refs/heads/main", event_sha=SHA, expected_sha=SHA,
        tag_type="tag", peeled_sha=SHA, checkout_sha=SHA,
    )
    values.update(overrides)
    validate_gate(**values)


def test_exact_annotated_tag_on_main_is_accepted():
    valid()


@pytest.mark.parametrize("overrides", [
    {"ref": "refs/tags/v0.1.0"},
    {"ref": "refs/heads/feat/tagged-install-validation"},
    {"event_sha": "b" * 40},
    {"expected_sha": "a" * 39},
    {"expected_sha": "A" * 40},
    {"expected_sha": "$(echo injected)"},
    {"tag_type": "commit"},
    {"peeled_sha": "b" * 40},
    {"checkout_sha": "b" * 40},
])
def test_mismatches_fail_closed(overrides):
    with pytest.raises(ValidationError):
        valid(**overrides)


def test_exact_tagged_git_provenance_is_accepted():
    validate_provenance({
        "version": "0.1.0",
        "direct_url": {
            "url": "https://github.com/indhra/my-guy.git",
            "vcs_info": {"vcs": "git", "requested_revision": "v0.1.0", "commit_id": SHA},
        },
    }, SHA)


@pytest.mark.parametrize("wrong", [
    {"version": "0.1.1"},
    {"direct_url": {"url": "https://github.com/indhra/my-guy.git", "vcs_info": {
        "vcs": "git", "requested_revision": "main", "commit_id": SHA,
    }}},
    {"direct_url": {"url": "https://github.com/indhra/my-guy.git", "vcs_info": {
        "vcs": "git", "requested_revision": "v0.1.0", "commit_id": "b" * 40,
    }}},
    {"direct_url": {"url": "https://github.com/other/my-guy.git", "vcs_info": {
        "vcs": "git", "requested_revision": "v0.1.0", "commit_id": SHA,
    }}},
])
def test_wrong_install_provenance_is_rejected(wrong):
    payload = {
        "version": "0.1.0",
        "direct_url": {
            "url": "https://github.com/indhra/my-guy.git",
            "vcs_info": {"vcs": "git", "requested_revision": "v0.1.0", "commit_id": SHA},
        },
    }
    payload.update(wrong)
    with pytest.raises(ValidationError):
        validate_provenance(payload, SHA)
