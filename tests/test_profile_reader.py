"""Profile reader tests."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from backyard.server.profile_reader import (
    ProfileInvalidError,
    ProfileNotFoundError,
    load_profile,
)


def _write_me_yaml(tmp_path: Path, content: str) -> Path:
    d = tmp_path / ".backyard-mcp"
    d.mkdir()
    f = d / "me.yaml"
    f.write_text(textwrap.dedent(content))
    return tmp_path


def test_load_valid_profile(tmp_path):
    _write_me_yaml(tmp_path, """
        project:
          name: Payments Service
          id: payments-service
          team:
            - name: Alice Chen
              email: alice@acme.com
              role: backend
    """)
    profile = load_profile(tmp_path)
    assert profile.id == "payments-service"
    assert profile.name == "Payments Service"
    assert profile.engineer.name == "Alice Chen"
    assert profile.engineer.email == "alice@acme.com"
    assert profile.engineer.role == "backend"
    assert profile.engineer.owns == []


def test_load_profile_with_owns(tmp_path):
    _write_me_yaml(tmp_path, """
        project:
          name: Payments Service
          id: payments-service
          team:
            - name: Bob Smith
              email: bob@acme.com
              role: frontend
              owns: ["ui/**", "components/**"]
    """)
    profile = load_profile(tmp_path)
    assert profile.engineer.role == "frontend"
    assert "ui/**" in profile.engineer.owns


def test_missing_file_raises(tmp_path):
    with pytest.raises(ProfileNotFoundError):
        load_profile(tmp_path)


def test_missing_project_id_raises(tmp_path):
    _write_me_yaml(tmp_path, """
        project:
          name: Payments Service
          team:
            - name: Alice Chen
              email: alice@acme.com
              role: backend
    """)
    with pytest.raises(ProfileInvalidError, match="project.id"):
        load_profile(tmp_path)


def test_missing_name_raises(tmp_path):
    _write_me_yaml(tmp_path, """
        project:
          name: Payments Service
          id: payments-service
          team:
            - email: alice@acme.com
              role: backend
    """)
    with pytest.raises(ProfileInvalidError, match="name"):
        load_profile(tmp_path)


def test_missing_email_raises(tmp_path):
    _write_me_yaml(tmp_path, """
        project:
          name: Payments Service
          id: payments-service
          team:
            - name: Alice Chen
              role: backend
    """)
    with pytest.raises(ProfileInvalidError, match="email"):
        load_profile(tmp_path)


def test_invalid_role_raises(tmp_path):
    _write_me_yaml(tmp_path, """
        project:
          name: Payments Service
          id: payments-service
          team:
            - name: Alice Chen
              email: alice@acme.com
              role: wizard
    """)
    with pytest.raises(ProfileInvalidError, match="wizard"):
        load_profile(tmp_path)


def test_project_id_links_teammates(tmp_path_factory):
    """Two engineers with the same project.id belong to the same project."""
    alice_ws = tmp_path_factory.mktemp("alice")
    bob_ws = tmp_path_factory.mktemp("bob")

    _write_me_yaml(alice_ws, """
        project:
          name: Payments Service
          id: payments-service
          team:
            - name: Alice Chen
              email: alice@acme.com
              role: backend
    """)
    _write_me_yaml(bob_ws, """
        project:
          name: Payments Service
          id: payments-service
          team:
            - name: Bob Smith
              email: bob@acme.com
              role: frontend
    """)

    alice = load_profile(alice_ws)
    bob = load_profile(bob_ws)
    assert alice.id == bob.id  # same project
    assert alice.engineer.email != bob.engineer.email  # different engineers
