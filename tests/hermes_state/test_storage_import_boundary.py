"""The canonical store must not import gateway/ to compute its own identities (latent cycle)."""
import subprocess
import sys


def test_runtime_storage_modules_import_without_loading_gateway():
    probe = ("import sys, hermes_state, hermes_store.runtime.transactions, hermes_store.sessions.local, hermes_store.repair.local_lineage, "
             "hermes_store.mutations.binding, hermes_store.mutations.branch, hermes_store.mutations.chat_pick, "
             "hermes_store.mutations.compress, hermes_store.mutations.guards, hermes_store.mutations.prepared, "
             "hermes_store.mutations.reset, hermes_store.mutations.retirement, hermes_store.mutations.transcript, "
             "hermes_store.mutations.actions, hermes_store.compression.session, hermes_store.compression.rewind, "
             "hermes_store.compression.prune_rewrite, hermes_store.compression.worker_compression, hermes_store.search.messages, "
             "hermes_store.search.index, hermes_store.repair.repair, hermes_store.repair.reconcile, hermes_store.repair.coverage, "
             "hermes_store.repair.profile_repair, hermes_store.repair.maintenance, hermes_store.repair.portability, "
             "hermes_store.repair.local_lineage, hermes_store.repair.local_migration, hermes_store.runtime.transactions, "
             "hermes_store.runtime.workers, hermes_store.runtime.worker_context, hermes_store.runtime.worker_lifecycle, "
             "hermes_store.runtime.readpool, hermes_store.runtime.lockowners, hermes_store.media.retirement, hermes_store.adapters.terminal, "
             "hermes_store.adapters.todo, hermes_store.adapters.gateway; "
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
