"""Import-graph ratchet: layer edges, package cycles, and late imports."""

from __future__ import annotations

from tests.scripts.test_code_health import _commit, _repo, _verdict


def test_layer_violation_blocks_only_new_edges(tmp_path, capsys):
    repo, base = _repo(tmp_path)
    base = _commit(repo, {
        "agent/a.py": "from hermes_cli.config import load\n",
        "gateway/g.py": "VALUE = 1\n",
        "hermes_cli/c.py": "VALUE = 1\n",
    })
    code, out = _verdict(repo, base, {"agent/a.py": "VALUE = 1\n"}, capsys)
    assert code == 0, out
    code, out = _verdict(repo, base, {"agent/a.py": "from hermes_cli.auth import login\n"}, capsys)
    assert code == 1 and "LAYER_VIOLATION" in out, out


def test_new_package_cycle_blocks(tmp_path, capsys):
    repo, base = _repo(tmp_path)
    base = _commit(repo, {
        "agent/a.py": "import gateway.g\n",
        "gateway/g.py": "VALUE = 1\n",
    })
    code, out = _verdict(repo, base, {"gateway/g.py": "import agent.a\n\nVALUE = 1\n"}, capsys)
    assert code == 1 and "IMPORT_CYCLE" in out, out


def test_new_late_cross_package_import_blocks(tmp_path, capsys):
    repo, base = _repo(tmp_path)
    base = _commit(repo, {
        "agent/b.py": "VALUE = 1\n",
        "gateway/g.py": "import agent.b\n\n\ndef f():\n    return 1\n",
    })
    code, out = _verdict(
        repo,
        base,
        {"gateway/g.py": "import agent.b\n\n\ndef f():\n    import agent.b\n    return 1\n"},
        capsys,
    )
    assert code == 1 and "LATE_IMPORT" in out, out


def test_moved_module_is_not_a_new_late_import(tmp_path, capsys):
    repo, base = _repo(tmp_path)
    base = _commit(repo, {
        "agent/a.py": "def f():\n    from hermes_cli.config_defaults import DEFAULT_CONFIG\n    return DEFAULT_CONFIG\n",
    })
    code, out = _verdict(
        repo,
        base,
        {"agent/a.py": "def f():\n    from hermes_config.defaults import DEFAULT_CONFIG\n    return DEFAULT_CONFIG\n"},
        capsys,
    )
    assert code == 0, out


def test_module_level_import_does_not_trigger_late_import(tmp_path, capsys):
    repo, base = _repo(tmp_path)
    base = _commit(repo, {
        "agent/b.py": "VALUE = 1\n",
        "agent/c.py": "VALUE = 1\n",
        "gateway/g.py": "import agent.b\n\n\ndef f():\n    return 1\n",
    })
    code, out = _verdict(
        repo,
        base,
        {"gateway/g.py": "import agent.b\nimport agent.c\n\n\ndef f():\n    return 1\n"},
        capsys,
    )
    assert code == 0, out
