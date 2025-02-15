from django.contrib import admin
from dynamic_config.models import *


class ConfigEntryAdmin(admin.ModelAdmin):
    pass


admin.site.register(ConfigEntry, ConfigEntryAdmin)
