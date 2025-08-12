import random
import logging

from django.contrib import admin
from django_summernote.admin import SummernoteModelAdmin
from django.contrib.auth.admin import UserAdmin
from django_json_widget.widgets import JSONEditorWidget
from durationwidget.widgets import TimeDurationWidget
from .models import *
from .forms import (
    CustomUserCreationForm,
    CompetitionForm,
    TeamCompetitionForm,
    KkzForm,
    KkzLabInlineForm,
    Competition2UserInlineForm,
    LabForm,
)
from django.db.models import DurationField, JSONField
from django.db import transaction
from django_apscheduler.admin import DjangoJob, DjangoJobExecution



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
    extra = 1
    fields = ['task_id', 'description']  # Базовые поля по умолчанию
    
    formfield_overrides = {
        JSONField: {
            'widget': CustomJSONEditorWidget(width="100%", height="300px")
        }
    }
    
    def _get_parent_lab(self, request, obj=None):
        """Получает родительский объект Lab различными способами"""
        # Из сохраненной ссылки
        if hasattr(self, 'parent_instance'):
            return self.parent_instance
        
        # Из объекта LabTask
        if obj and hasattr(obj, 'lab'):
            return obj.lab
            
        # Из URL (для новых объектов)
        if request and 'change' in request.path:
            import re
            match = re.search(r'/lab/(\d+)/change/', request.path)
            if match:
                try:
                    from .models import Lab
                    return Lab.objects.get(pk=int(match.group(1)))
                except Lab.DoesNotExist:
                    pass
        
        return None
    
    def get_fields(self, request, obj=None):
        """Динамически определяет поля в зависимости от типа заданий Lab"""
        parent_lab = self._get_parent_lab(request, obj)
        base_fields = ['task_id', 'description']
        
        # Добавляем json_config только для JSON_CONFIGURED типа
        if parent_lab and parent_lab.tasks_type == 'JSON_CONFIGURED':
            base_fields.append('json_config')
        
        return base_fields
    
    def get_formset(self, request, obj=None, **kwargs):
        """Сохраняет ссылку на родительский объект"""
        if obj:
            self.parent_instance = obj
        return super().get_formset(request, obj, **kwargs)


class LabModelAdmin(SummernoteModelAdmin):  # instead of ModelAdmin
    form = LabForm
    summernote_fields = 'description'
    list_display = ('name', 'lab_type', 'program', 'get_learning_years')
    formfield_overrides = {
        JSONField: {
            'widget': CustomJSONEditorWidget(width="50%", height="30vh")
        },
        DurationField: {
            'widget': TimeDurationWidget(show_days=True, show_hours=True, show_minutes=True, show_seconds=False)
        }
    }
    inlines = [LabLevelInline, LabTaskInline]

    def get_learning_years(self, obj):
        return ", ".join(str(year) for year in obj.learning_years)
    get_learning_years.short_description = 'Годы обучения'

    def get_fieldsets(self, request, obj=None):
        base_fields = ('name', 'slug', 'description', 'platform', 'program', 'lab_type', 'learning_years', 'default_duration', 'tasks_type', 'cover', 'answer_flag')
        pnet_fields = ('NodesData', 'ConnectorsData', 'Connectors2CloudData', 'NetworksData')

        if obj and obj.platform == "PN":
            return (
                (None, {'fields': base_fields}),
                ('PNETLab Конфигурация', {
                    'fields': pnet_fields,
                    'classes': ('collapse',)
                })
            )
        else:
            return (
                (None, {'fields': base_fields}),
            )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        return form
    
    def get_formsets_with_inlines(self, request, obj=None):
        # Передаем информацию о родительском объекте в inline-формы
        for inline, formset in super().get_formsets_with_inlines(request, obj):
            if obj and hasattr(inline, 'parent_instance'):
                inline.parent_instance = obj
            yield inline, formset


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


class KkzLabInline(admin.StackedInline):
    model = KkzLab
    form = KkzLabInlineForm
    extra = 1
    fields = ['lab', 'tasks', 'num_tasks']
    filter_horizontal = ['tasks']
    can_delete = False

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
            tasks = list(kkz_lab.tasks.all() or kkz_lab.lab.options.all())
            num_tasks = kkz_lab.num_tasks

            if users:
                if obj.unified_tasks:
                    all_tasks = kkz_lab.tasks.all() or kkz_lab.lab.options.all()
                    num_tasks = kkz_lab.num_tasks

                    selected_tasks = random.sample(
                        list(all_tasks),
                        min(num_tasks, all_tasks.count())
                    )
                    kkz_lab.tasks.set(selected_tasks)  # Исправлено
                    kkz_lab.save()

                    competition.tasks.set(selected_tasks)  # Исправлено

                    users = obj.get_users()
                    for user in users:
                        comp2user, _ = Competition2User.objects.update_or_create(
                            competition=competition,
                            user=user
                        )
                        comp2user.tasks.set(selected_tasks)  # Исправлено
                else:
                    users = obj.get_users()
                    tasks = list(kkz_lab.tasks.all() or kkz_lab.lab.options.all())
                    num_tasks = kkz_lab.num_tasks

                    for user in users:
                        comp2user, created = Competition2User.objects.get_or_create(
                            competition=competition,
                            user=user
                        )
                        if tasks:
                            assigned_tasks = random.sample(
                                tasks,
                                min(num_tasks, len(tasks))
                            )
                            comp2user.tasks.set(assigned_tasks)


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


class PlatoonAdmin(admin.ModelAdmin):
    model = Platoon
    list_display = ('number', 'learning_year')


admin.site.register(Lab, LabModelAdmin)
admin.site.register(Platoon, PlatoonAdmin)
admin.site.register(Competition, CompetitionAdmin)
admin.site.register(User, MyUserAdmin)
admin.site.register(Answers, admin.ModelAdmin)
admin.site.register(Team, TeamAdmin)
admin.site.register(TeamCompetition, TeamCompetitionAdmin)
# admin.site.register(TeamCompetition2Team, admin.ModelAdmin)
admin.site.unregister(DjangoJob)
admin.site.unregister(DjangoJobExecution)
admin.site.register(Kkz, KkzAdmin)