"""Run only while this app is stopped, with its data mounted at /state."""
from pathlib import Path
import sys

sys.path.insert(0, '/helper')
from configure import backup_state, restore_state, tree_hashes

state = Path('/state')
before = tree_hashes(state / 'openviking')
old = set((state / 'backups').iterdir()) if (state / 'backups').exists() else set()
backup_state(state)
created = set((state / 'backups').iterdir()) - old
assert len(created) == 1
snapshot = created.pop()
restore_state(state, snapshot.name)
assert tree_hashes(state / 'openviking') == before
print('DEVICE_SNAPSHOT_RESTORE_PASSED', snapshot.name, len(before))
