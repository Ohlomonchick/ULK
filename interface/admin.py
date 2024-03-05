from django.contrib import admin
from django_summernote.admin import SummernoteModelAdmin
from django.contrib.auth.admin import UserAdmin

from .models import *


class SomeModelAdmin(SummernoteModelAdmin):  # instead of ModelAdmin
    summernote_fields = '__all__'
    exclude = ('slug',)

class IssuedLabsModel(admin.ModelAdmin):
    list_display = ("lab", "user", "end_date", "done")
    list_filter = ("user", "lab")
    exclude = ('done', )
    # search_fields = ("user",)

    fieldsets = admin.ModelAdmin.fieldsets

class MyUserAdmin(UserAdmin):
    list_display = ("username", "is_staff", "platoon")
    fieldsets = UserAdmin.fieldsets
    fieldsets = ((None, {'fields': ('username', 'password', 'platoon')}), ) + fieldsets[1:]
    list_filter = ("is_staff", "platoon")

    search_fields = ("platoon",)

class CompetitionAdmin(admin.ModelAdmin):
    exclude = ('slug', )
    list_display = ("start", "lab")


admin.site.register(IssuedLabs, IssuedLabsModel)
admin.site.register(Lab, SomeModelAdmin)
admin.site.register(Platoon, admin.ModelAdmin)
admin.site.register(Competition, CompetitionAdmin)
admin.site.register(User, MyUserAdmin)
