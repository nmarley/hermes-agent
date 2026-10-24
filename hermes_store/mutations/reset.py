"""Prepare and publish a local reset inside the mutation receipt transaction."""
import json
import uuid
import time

from hermes_state_local import POLICY_PREFIX
from hermes_state_local_lineage import advance_local_target, validate_local_lineage
from hermes_store.mutations.guards import require_target_advanceable
from hermes_state_runtime import RuntimeStoreError
from hermes_state_runtime_workers import discard_orphan_workers_on_reset, runtime_lineage


def reset_in_transaction(db, conn, session_id, payload):
    saved = conn.execute('SELECT value FROM state_meta WHERE key=?',
                         (POLICY_PREFIX + session_id,)).fetchone()
    if saved is None:
        raise RuntimeStoreError('runtime_coordination_required')
    receipt = json.loads(saved[0])
    target = validate_local_lineage(conn, receipt)
    discard_orphan_workers_on_reset(conn, runtime_lineage(conn, session_id))
    require_target_advanceable(db, conn, list({session_id, target}))
    parent = conn.execute('SELECT * FROM sessions WHERE id=?', (target,)).fetchone()
    policy = receipt['policy']
    from hermes_store.api import mutation_hooks
    child_id = uuid.uuid4().hex
    entry, _now = mutation_hooks().reset_entry(receipt['entry'], child_id)
    db._publish_child_session_row(conn, parent, parent_session_id=target,
        child_session_id=child_id, source=policy['source'], model=policy['model'],
        model_config={'_reset_from': target}, system_prompt=None,
        cwd=policy['cwd'], profile_name=parent['profile_name'])
    conn.execute("UPDATE sessions SET ended_at=?,end_reason='session_reset' WHERE id=?", (time.time(), target))
    db._bump_conversation_generation(conn, target, 'session_reset')
    advance_local_target(conn, target, child_id, entry=entry.to_dict())
    conn.execute('UPDATE sessions SET runtime_generation=runtime_generation+1 WHERE id=?', (session_id,))
    generation = conn.execute('SELECT runtime_generation FROM sessions WHERE id=?', (session_id,)).fetchone()[0]
    # advance_local_target already advances the logical owner's revision.
    return set(), {'target_session_id': child_id, 'previous_target_session_id': target,
                   'execution_generation': generation}
