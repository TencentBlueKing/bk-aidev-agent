import os

from blueapps.patch.settings_paas_services import INSTALLED_APPS, STATICFILES_DIRS

CUR_DIR = os.path.dirname(__file__)

STATICFILES_DIRS += [os.path.join(CUR_DIR, "dist/static")]

INSTALLED_APPS += ("agent",)
