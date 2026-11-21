import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import fcntl
except ImportError:
    fcntl = None

logger = logging.getLogger(__name__)


def try_start_local_producer(payload: dict) -> bool:
    try:
        limit = int(os.environ.get("BKAI_CHAT_LOCAL_PRODUCER_LIMIT", "0"))
    except ValueError:
        logger.warning("Invalid BKAI_CHAT_LOCAL_PRODUCER_LIMIT, using Celery")
        return False
    if limit <= 0 or fcntl is None:
        return False

    app_key = hashlib.sha256(payload["spec"]["app_code"].encode()).hexdigest()
    directory = Path(tempfile.gettempdir()) / f"bkai-producer-{os.getuid()}-{app_key}"
    try:
        directory.mkdir(mode=0o700, exist_ok=True)
        info = directory.lstat()
        if info.st_uid != os.getuid() or directory.is_symlink() or info.st_mode & 0o077:
            logger.warning("Unsafe local producer lock directory, using Celery")
            return False
        for index in range(limit):
            with (directory / str(index)).open("ab") as slot:
                try:
                    fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                with tempfile.TemporaryFile(mode="w+b") as request:
                    request.write(json.dumps(payload).encode())
                    request.seek(0)
                    subprocess.Popen(
                        [sys.executable, "-m", "django", "run_chat_local_producer"],
                        stdin=request,
                        pass_fds=(slot.fileno(),),
                        start_new_session=True,
                    )
                return True
    except OSError:
        logger.exception("Unable to launch local producer, using Celery")
    return False
