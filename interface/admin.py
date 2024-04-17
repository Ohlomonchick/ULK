from django.contrib import admin
from django_summernote.admin import SummernoteModelAdmin
from django.contrib.auth.admin import UserAdmin

from .models import *
from .forms import CustomUserCreationForm, CompetitionForm


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
    add_form = CustomUserCreationForm
    list_display = ("username", "is_staff", "platoon")
    model = User
    fieldsets = UserAdmin.fieldsets
    fieldsets = ((None, {'fields': ('username', 'password', 'platoon')}), ) + fieldsets[1:]

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "first_name", "last_name", "password1", "password2", "platoon"
            )}
        ),
    )
    list_filter = ("is_staff", "platoon")

    search_fields = ("first_name", "last_name")


class CompetitionAdmin(admin.ModelAdmin):
    form = CompetitionForm
    add_form = CompetitionForm
    exclude = ('slug', 'participants')
    list_display = ("start", "lab")
    search_fields = ['lab__name']


admin.site.register(IssuedLabs, IssuedLabsModel)
admin.site.register(Lab, SomeModelAdmin)
admin.site.register(Platoon, admin.ModelAdmin)
admin.site.register(Competition, CompetitionAdmin)
admin.site.register(User, MyUserAdmin)
admin.site.register(Answers, admin.ModelAdmin)
