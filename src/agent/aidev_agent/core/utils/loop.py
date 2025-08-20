# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import asyncio
import atexit

# Global variable to store the event loop reference
_loop = None


def get_event_loop():
    """
    Get the current event loop, create one if it doesn't exist, and activate it.

    Returns:
        asyncio.AbstractEventLoop: The current event loop.
    """
    global _loop

    # Return the cached loop if we have one
    if _loop is not None and not _loop.is_closed():
        return _loop

    try:
        # Try to get the current event loop
        _loop = asyncio.get_running_loop() or asyncio.get_event_loop()
    except RuntimeError:
        # No event loop exists, create a new one
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        # Register cleanup function
        atexit.register(_cleanup_loop)

    return _loop


def _cleanup_loop():
    """Cleanup function to properly close the event loop on exit."""
    global _loop
    if _loop is not None and not _loop.is_closed():
        try:
            # Cancel all pending tasks
            pending = asyncio.all_tasks(_loop)
            for task in pending:
                task.cancel()

            # Run until all tasks are cancelled
            if pending:
                _loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

            # Close the loop
            _loop.close()
        except Exception:
            # Ignore exceptions during cleanup
            pass
        finally:
            _loop = None
