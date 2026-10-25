"""Compatibility alias for :mod:`hermes_platform.constants`."""

import sys

from hermes_platform import constants as _impl
from hermes_platform.constants import (
    FIRST_PARTY_MODULE_ROOTS,
    _get_platform_default_hermes_home, apply_subprocess_home_env, assert_named_profile_home_live,
    display_hermes_home, find_node_executable, get_default_hermes_root, get_hermes_home,
    get_hermes_home_override, get_process_hermes_home, get_real_home, get_subprocess_home,
    hermes_home_key, hermes_managed_node_tree_present, is_container, is_wsl, iter_hermes_node_dirs,
    profile_name_for_home, project_venv_dir, reset_hermes_home_override, set_hermes_home_override,
    sudo_invoker_default_home, venv_bin_dir, venv_python_path,
    with_hermes_node_path,
)

sys.modules[__name__] = _impl
