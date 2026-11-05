import time

from leapp.libraries.common.rhsm import skip_rhsm
from leapp.libraries.stdlib import api, CalledProcessError, run
from leapp.models import RpmToFlatpakFacts

# flatpak talks to the authenticator of the Flatpak remote (the OCI authenticator
# for the Red Hat Flatpak registry) over a D-Bus session bus. There is no session bus
# during the first boot, so the command is run in a private one created by
# dbus-run-session, otherwise flatpak fails with
# "Cannot autolaunch D-Bus without X11 $DISPLAY".
# See https://github.com/flatpak/flatpak/issues/3847
_FLATPAK_PREINSTALL_CMD = ['dbus-run-session', '--', 'flatpak', 'preinstall', '--system',
                           '--noninteractive']
_MAX_ATTEMPTS = 3
_RETRY_SLEEP = 10


def _run_flatpak_preinstall():
    """
    Run ``flatpak preinstall``, retrying on failure.

    The command downloads the applications from the Flatpak remotes, so it
    requires a working network connection. The network might not be fully
    available right after the system starts, hence the retries.
    """
    last_error = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            run(_FLATPAK_PREINSTALL_CMD)
            return True
        except (CalledProcessError, OSError) as e:
            last_error = e
            api.current_logger().warning(
                'Attempt {} of {} to run flatpak preinstall failed: {}'.format(
                    attempt, _MAX_ATTEMPTS, e
                )
            )
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_RETRY_SLEEP)
    api.current_logger().error(
        'Failed to run flatpak preinstall: {}. The applications were not migrated to Flatpak,'
        ' install them as Flatpaks manually.'.format(last_error)
    )
    return False


def process():
    facts = next(api.consume(RpmToFlatpakFacts), None)
    if not facts or not facts.packages:
        return

    if skip_rhsm():
        api.current_logger().debug(
            'Skipping the RPM-to-Flatpak migration: RHSM is not in use, so the migration'
            ' was not enabled and the required packages are not installed.'
        )
        return

    rpm_names = sorted(p.rpm_name for p in facts.packages)
    api.current_logger().info(
        'Migrating packages from RPM to Flatpak: {}'.format(', '.join(rpm_names))
    )

    _run_flatpak_preinstall()
