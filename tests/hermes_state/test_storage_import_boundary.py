"""The canonical store must not import gateway/ to compute its own identities (latent cycle)."""
import subprocess
import sys


def test_runtime_storage_modules_import_without_loading_gateway():
    probe = ("import sys, hermes_state, hermes_state_runtime, hermes_state_local, hermes_state_local_lineage, "
             "hermes_state_mutation_binding, hermes_state_mutation_branch, hermes_state_mutation_chat_pick, "
             "hermes_state_mutation_compress, hermes_state_mutation_guards, hermes_state_mutation_prepared, "
             "hermes_state_mutation_reset, hermes_state_mutation_retirement, hermes_state_mutation_transcript, "
             "hermes_state_mutations, hermes_state_compression, hermes_state_rewind, "
             "hermes_state_prune_rewrite, hermes_state_worker_compression, hermes_state_search, "
             "hermes_state_fts, hermes_state_repair, hermes_state_reconcile, hermes_state_coverage, "
             "hermes_state_profile_repair, hermes_state_maintenance, hermes_state_portability, "
             "hermes_state_local_lineage, hermes_state_local_migration, hermes_state_runtime, "
             "hermes_state_runtime_workers, hermes_state_worker_context, hermes_state_worker_lifecycle, "
             "hermes_state_readpool, hermes_state_lockowners, hermes_state_media, hermes_state_terminal, "
             "hermes_state_todo, hermes_state_gateway; "
             "print(sorted(m for m in sys.modules if m == 'gateway' or m.startswith('gateway.')))")
    out = subprocess.run([sys.executable, '-c', probe], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == '[]', out.stdout


def test_gateway_names_are_the_storage_definitions():
    from hermes_store import keys
    from gateway.session import SessionStore, profile_from_session_key_namespace
    from gateway.session_admission import admission_fingerprint
    from gateway.session_local_recovery import local_identity
    assert admission_fingerprint is keys.admission_fingerprint
    assert local_identity is keys.local_identity
    assert profile_from_session_key_namespace is keys.profile_from_session_key_namespace
    for key, profile in (('agent:main:local:dm:x', 'default'), ('agent:main~:local:dm:x', 'main'),
                         ('agent:work:local:dm:x', 'work'), ('agent::x', 'default'), ('cli:x', None), (None, None)):
        assert SessionStore._profile_from_session_key(key) == keys.profile_from_session_key(key) == profile
