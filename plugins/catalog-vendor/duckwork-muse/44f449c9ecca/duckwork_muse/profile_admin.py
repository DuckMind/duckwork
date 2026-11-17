"""Dashboard-only read-only profile listing and selection; lifecycle stays with Duckwork."""
from .content_io import DomainError, revision
from .views import Views, canonical

PLUGIN = 'duckwork-muse'


def resolve(name):
    from duckwork_cli.profiles import get_profile_dir, list_profile_names, normalize_profile_name
    from duckwork_constants import get_default_duckwork_root, get_duckwork_home
    if not isinstance(name, str) or normalize_profile_name(name) != name or name not in list_profile_names():
        raise DomainError('not_found', 'Select a registered profile on this Duckwork host')
    root = get_default_duckwork_root(home=get_duckwork_home()).resolve()
    home = get_profile_dir(name).resolve()
    if name == 'default' and home != root:
        raise DomainError('profile_mismatch', 'Default root resolution changed')
    return home


def state(name):
    from pm.plugins_state import read_home_selection
    from duckwork_cli.plugins import parse_manifest_file
    home = resolve(name)
    # PM's public selection reader does not seed SOUL/config backups or mutate
    # process globals; generic load_config_readonly is not side-effect-free.
    selection = (read_home_selection(home) or {}).get('plugins', {})
    enabled = PLUGIN in selection.get('enabled', []) and PLUGIN not in selection.get('disabled', [])
    path = home/'plugins'/PLUGIN
    manifest = parse_manifest_file(path/'plugin.yaml', path, 'user', '') if (path/'plugin.yaml').is_file() else None
    try:
        raw = Views(home).files.read('install.json')
    except FileNotFoundError:
        raw = b''
    row = {'name': name, 'installed': manifest is not None, 'enabled': bool(manifest and enabled),
           'version': manifest.version if manifest else None, 'managed_by': 'Duckwork',
           'read_only': True, 'initialized': bool(raw)}
    row['revision'] = revision(canonical([row, revision(raw)]))
    return row


def profiles():
    from duckwork_cli.profiles import list_profile_names
    return {'profiles': [state(name) for name in list_profile_names()],
            'host_scope': 'This Duckwork instance only; select a profile before viewing its content'}


def selected_view(name):
    row = state(name)
    if not row['installed'] or not row['enabled']:
        raise DomainError('not_installed', 'Muse is not installed and enabled in this profile')
    return Views(resolve(name))

