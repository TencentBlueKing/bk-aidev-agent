# -*- coding: utf-8 -*-

from functools import wraps

from aidev_bkplugin.utils import is_local_dev


def login_exempt(view_func):
    """Mark a view function as being exempt from login view protection"""

    def wrapped_view(*args, **kwargs):
        return view_func(*args, **kwargs)

    wrapped_view.login_exempt = is_local_dev()
    return wraps(view_func)(wrapped_view)
