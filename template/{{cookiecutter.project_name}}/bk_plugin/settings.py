import os

from blueapps.patch.settings_paas_services import INSTALLED_APPS, STATICFILES_DIRS

CUR_DIR = os.path.dirname(__file__)

STATIC_TEMPLATE_ROOT = os.path.join(CUR_DIR, "{{cookiecutter.static_template_root}}")

STATICFILES_DIRS += [os.path.join(STATIC_TEMPLATE_ROOT, "static")]

INSTALLED_APPS += ("agent",)
