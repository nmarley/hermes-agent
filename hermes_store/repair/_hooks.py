"""Late access to the repair hooks without importing the store facade at module load."""


def hooks():
    from hermes_store.api import repair_hooks
    return repair_hooks()
