import random
import logging

from django.contrib import admin
from django_summernote.admin import SummernoteModelAdmin
from django.contrib.auth.admin import UserAdmin
from django_json_widget.widgets import JSONEditorWidget
from .models import *
from .forms import CustomUserCreationForm, CompetitionForm, TeamCompetitionForm, KkzForm, KkzLabInlineForm, Competition2UserInlineForm
from django.db.models import JSONField
from django.db import transaction
from django_apscheduler.admin import DjangoJob, DjangoJobExecution
from django.contrib.admin.widgets import FilteredSelectMultiple



class CustomJSONEditorWidget(JSONEditorWidget):
    class Media:
        css = {
            'all': ('admin/css/json_admin.css',)
        }


class LabLevelInline(admin.TabularInline):
    model = LabLevel
    extra = 1  # Display one empty level form by default
    fields = ["level_number", "description"]


class LabTaskInline(admin.TabularInline):
    model = LabTask
    extra = 1  # Shows one empty form by default


class LabModelAdmin(SummernoteModelAdmin):  # instead of ModelAdmin
    summernote_fields = 'description'
    formfield_overrides = {
        JSONField: {
            'widget': CustomJSONEditorWidget(width="50%", height="30vh")
        },
    }
    inlines = [LabLevelInline, LabTaskInline]


class MyUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    list_display = ("username", "is_staff", "platoon")
    model = User
    fieldsets = UserAdmin.fieldsets
    fieldsets = ((None, {'fields': ('username', 'password', 'platoon')}),) + fieldsets[1:]
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
    exclude = ('pnet_login', )


class Competition2UserInline(admin.TabularInline):
    model = Competition2User
    form = Competition2UserInlineForm
    extra = 0
    fields = ('user', 'level', 'tasks')
    readonly_fields = ('user',)
    can_delete = False


def set_all_users_to_competition_level(modeladmin, request, queryset):
    for competition in queryset:
        comp_users = competition.competition_users.all()
        comp_users.update(level=competition.level)


class CompetitionAdmin(admin.ModelAdmin):
    form = CompetitionForm
    add_form = CompetitionForm
    list_display = ("start", "lab", 'all_platoons', 'all_non_platoon_users')
    search_fields = ['lab__name']
    exclude = ('participants', 'deleted', 'slug', 'issued_labs', 'kkz')
    inlines = [Competition2UserInline]
    actions = [set_all_users_to_competition_level]

    class Media:
        js = ('admin/js/load_levels.js', 'admin/js/jquery-3.7.1.min.js')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Exclude rows that actually belong to the TeamCompetition subclass
        return qs.exclude(teamcompetition__isnull=False)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if obj and obj.lab:
            formset.parent_instance = obj
        return formset

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()

    def all_platoons(self, obj):
        return ", ".join(str(tag.number) for tag in obj.platoons.all())

    def all_non_platoon_users(self, obj):
        return ", ".join(user.last_name for user in obj.non_platoon_users.all())

    all_platoons.short_description = 'Взвода'
    all_non_platoon_users.short_description = 'Отдельные пользователи'


class KkzLabInline(admin.TabularInline):
    model = KkzLab
    form = KkzLabInlineForm
    extra = 1
    fields = ['lab', 'tasks', 'num_tasks']
    filter_horizontal = ['tasks']

    class Media:
        css = {'all': ('admin/css/kkz_custom.css',)}
        js = ('admin/js/jquery-3.7.1.min.js', 'admin/js/load_levels.js')


class KkzAdmin(admin.ModelAdmin):
    form = KkzForm
    inlines = [KkzLabInline]
    list_display = ('name', 'start', 'finish')

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = form.instance

        for kkz_lab in obj.kkz_labs.all():
            competition, created = Competition.objects.get_or_create(
                defaults={'start': obj.start, 'finish': obj.finish},
                lab=kkz_lab.lab,
                kkz=obj
            )
            if not created:
                competition.start = obj.start
                competition.finish = obj.finish
                competition.save()

            competition.platoons.set(obj.platoons.all())
            competition.non_platoon_users.set(obj.non_platoon_users.all())
            users = obj.get_users()
            tasks = list(kkz_lab.tasks.all())
            num_tasks = kkz_lab.num_tasks

            if users:
                for user in users:
                    competition2user, created = Competition2User.objects.get_or_create(
                        competition=competition,
                        user=user
                    )
                    if tasks:
                        assigned_tasks = random.sample(tasks, min(num_tasks, len(tasks)))
                        if competition.kkz.unified_tasks:
                            competition.tasks.set(assigned_tasks)
                        else:
                            competition2user.tasks.set(assigned_tasks)

                        
class TeamAdmin(admin.ModelAdmin):
    exclude = ('slug', )

    def save_related(self, request, form, formsets, change):
        # First, let Django save all related m2m data
        super().save_related(request, form, formsets, change)

        # Now update the slug based on name and users
        obj = form.instance
        slug_str = obj.name
        for user in obj.users.all():
            slug_str += '-' + slugify(user.last_name)

        obj.slug = slugify(slug_str)
        obj.save()

        transaction.on_commit(lambda: Team.post_create(sender=Team, instance=obj, created=True))


class TeamCompetitionAdmin(CompetitionAdmin):
    form = TeamCompetitionForm
    add_form = TeamCompetitionForm

    def get_queryset(self, request):
        qs = admin.ModelAdmin.get_queryset(self, request)
        qs = qs.filter(pk__in=TeamCompetition.objects.values_list('pk', flat=True))
        return qs

admin.site.register(Lab, LabModelAdmin)
admin.site.register(Platoon, admin.ModelAdmin)
admin.site.register(Competition, CompetitionAdmin)
admin.site.register(User, MyUserAdmin)
admin.site.register(Answers, admin.ModelAdmin)
admin.site.register(Team, TeamAdmin)
admin.site.register(TeamCompetition, TeamCompetitionAdmin)
admin.site.register(TeamCompetition2Team, admin.ModelAdmin)
admin.site.unregister(DjangoJob)
admin.site.unregister(DjangoJobExecution)
admin.site.register(Kkz, KkzAdmin)