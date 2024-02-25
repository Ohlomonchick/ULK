from django.contrib import admin
from django_summernote.admin import SummernoteModelAdmin
from django.contrib.auth.admin import UserAdmin

from .models import *


class SomeModelAdmin(SummernoteModelAdmin):  # instead of ModelAdmin
    summernote_fields = '__all__'


class MyUserAdmin(UserAdmin):
    list_display = ("username", "is_staff", "platoon")
    fieldsets = UserAdmin.fieldsets
    fieldsets = ((None, {'fields': ('username', 'password', 'platoon')}), ) + fieldsets[1:]
    list_filter = ("is_staff", "platoon")

    search_fields = ("platoon",)


admin.site.register(Lab, SomeModelAdmin)
admin.site.register(Platoon, admin.ModelAdmin)
admin.site.register(User, MyUserAdmin)
