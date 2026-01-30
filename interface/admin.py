import random
import json
import logging

from django.contrib import admin
from django_summernote.admin import SummernoteModelAdmin
from django_summernote.utils import get_attachment_model
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
    MyAttachmentAdminForm,
    LabTaskInlineForm,
)
from .admin_descriptions import LAB_NODE_DESCRIPTION, get_lab_task_description
from django.db.models import DurationField, JSONField
from django.db import transaction
from django_apscheduler.admin import DjangoJob, DjangoJobExecution


class CustomJSONEditorWidget(JSONEditorWidget):
    class Media:
        css = {
            'all': ('admin/css/json_admin.css',)
        }


class TabularInlineWithDescription(admin.TabularInline):
    """
    Базовый класс TabularInline с поддержкой описания.
    Для добавления описания установите атрибут 'description' в дочернем классе.
    """
    description = None
    template = 'admin/edit_inline/tabular_with_description.html'

    def get_description(self):
        """Возвращает описание для отображения"""
        return self.description


class LabLevelInline(admin.TabularInline):
    model = LabLevel
    extra = 1  # Display one empty level form by default
    fields = ["level_number", "description"]


class LabTaskTypeInline(admin.TabularInline):
    """Inline для создания типов заданий в карточке лабы"""
    model = LabTaskType
    extra = 1
    fields = ['name', 'default_duration']
    verbose_name = "Тип задания"
    verbose_name_plural = "Типы заданий"

    formfield_overrides = {
        DurationField: {
            'widget': TimeDurationWidget(
                show_days=False, 
                show_hours=False, 
                show_minutes=True, 
                show_seconds=True,
                attrs={'style': 'width:5em;'}
            ),
        }
    }

class LabTaskInline(TabularInlineWithDescription):
    model = LabTask
    form = LabTaskInlineForm
    extra = 1
    fields = ['task_id', 'task_type', 'description']  

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
        base_fields = ['task_id', 'task_type', 'description']  

        # Добавляем json_config только для JSON_CONFIGURED типа
        if parent_lab:
            if parent_lab.tasks_type == 'JSON_CONFIGURED':
                base_fields.append('json_config')
            elif parent_lab.tasks_type == 'TESTING':
                base_fields.append('question')
                base_fields.append('answer')

        return base_fields

    def get_description(self):
        """Возвращает описание в зависимости от типа заданий родительской Lab"""
        parent_lab = None
        if hasattr(self, 'parent_instance'):
            parent_lab = self.parent_instance

        if parent_lab:
            tasks_type = parent_lab.tasks_type
            return get_lab_task_description(tasks_type)

        # По умолчанию возвращаем описание для CLASSIC
        return get_lab_task_description('CLASSIC')

    def get_formset(self, request, obj=None, **kwargs):
        """Сохраняет ссылку на родительский объект и устанавливает описание"""
        if obj:
            self.parent_instance = obj
        # Устанавливаем описание динамически (даже если obj=None, будет использовано значение по умолчанию)
        self.description = self.get_description()
        return super().get_formset(request, obj, **kwargs)


class LabNodeInline(TabularInlineWithDescription):
    model = LabNode
    extra = 1
    fields = ['node_name', 'login', 'password']
    description = LAB_NODE_DESCRIPTION


class LabModelAdmin(SummernoteModelAdmin):  # instead of ModelAdmin
    form = LabForm
    summernote_fields = 'description'
    list_display = ('name', 'lab_type', 'program', 'get_learning_years')
    ordering = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    formfield_overrides = {
        JSONField: {
            'widget': CustomJSONEditorWidget(width="50%", height="30vh")
        },
        DurationField: {
            'widget': TimeDurationWidget(show_days=True, show_hours=True, show_minutes=True, show_seconds=False, attrs={'style': 'width:5em;'})
        }
    }
    inlines = [LabLevelInline, LabTaskTypeInline, LabTaskInline, LabNodeInline]

    class Media:
        js = ('admin/js/jquery-3.7.1.min.js', "admin/js/load_lab_type.js", "admin/js/task_type_selector.js")

    def get_learning_years(self, obj):
        return ", ".join(str(year) for year in obj.learning_years)
    get_learning_years.short_description = 'Годы обучения'

    def get_fieldsets(self, request, obj=None):
        base_fields = [
            'name',
            'slug',
            'pnet_slug',
            'description',
            'platform',
            'program',
            'lab_type',
            'learning_years',
            'default_duration',
            'tasks_type',
            'cover',
            'background_image',
            'lab_elements_color',
            'answer_flag',
            'need_kibana',
            'task_checking',
        ]
        pnet_fields = ('NodesData', 'ConnectorsData', 'Connectors2CloudData', 'NetworksData')
        ssh_fields = ('PnetSSHNodeName',)

        if obj.platform != "NO" and obj.lab_type == "PZ":
            base_fields.append('need_iframe_for_admin')

        base_fields = tuple(base_fields)

        if obj and obj.platform == "PN":
            return (
                (None, {'fields': base_fields}),
                ('PNETLab Конфигурация', {
                    'fields': pnet_fields,
                    'classes': ('collapse',)
                })
            )
        elif obj and obj.platform == "CMD":
            return (
                (None, {'fields': base_fields}),
                ('PNETLab Конфигурация', {
                    'fields': pnet_fields,
                    'classes': ('collapse',)
                }),
                ('Конфигурация консоли', {
                    'fields': ssh_fields,
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
                # Устанавливаем описание для inline с описанием
                if isinstance(inline, TabularInlineWithDescription):
                    inline.description = inline.get_description()
            yield inline, formset

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        if formset.model == LabTaskType:
            for obj in instances:
                obj.save()
            for obj in formset.deleted_objects:
                obj.delete()
            return

        if formset.model == LabTask:
            for subform in formset.forms:
                if subform.instance.pk and subform.cleaned_data.get('DELETE'):
                    subform.instance.delete()
                    continue
                
                if subform.cleaned_data and not subform.cleaned_data.get('DELETE'):
                    instance = subform.instance
                    raw_value = subform.cleaned_data.get('task_type') 
                    
                    if raw_value:
                        if raw_value.startswith('name:'):
                            type_name = raw_value.split('name:', 1)[1]
                            try:
                                task_type = LabTaskType.objects.get(lab=form.instance, name=type_name)
                                instance.task_type = task_type
                            except LabTaskType.DoesNotExist:
                                instance.task_type = None
                        else:
                            try:
                                instance.task_type_id = int(raw_value)
                            except (ValueError, TypeError):
                                instance.task_type = None
                    else:
                        instance.task_type = None
                    
                    instance.save()
            return

        formset.save()


class MyUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    list_display = ("username", "is_staff", "platoon", "pnet_login", "pnet_password")
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
    exclude = ('participants', 'deleted', 'slug', 'issued_labs', 'kkz', 'created_at')
    inlines = [Competition2UserInline]
    actions = [set_all_users_to_competition_level]

    class Media:
        js = ('admin/js/jquery-3.7.1.min.js', 'admin/js/load_levels.js', 'admin/js/update_num_tasks.js')

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
    fields = ['lab', 'tasks', 'num_tasks', 'assignments']
    filter_horizontal = ['tasks']
    can_delete = False

    class Media:
        css = {'all': ('admin/css/kkz_custom.css',)}
        js = ('admin/js/jquery-3.7.1.min.js', 'admin/js/load_levels.js')


class KkzPreviewInline(admin.StackedInline):
    model = KkzPreview
    fields = ('lab', 'user', 'tasks')
    filter_horizontal = ['tasks']
    extra = 0
    can_delete = False

    class Media:
        js = ('admin/js/kkz_random_preview.js', 'admin/js/load_levels.js', 'admin/js/jquery-3.7.1.min.js')


class KkzAdmin(admin.ModelAdmin):
    form = KkzForm
    inlines = [KkzLabInline, KkzPreviewInline]
    list_display = ('name', 'platoons_display', 'start', 'duration')

    def platoons_display(self, obj):
        platoons = obj.platoons.all()
        return ' '.join(str(platoon) for platoon in platoons)
    platoons_display.short_description = 'Взводы'

    def duration(self, obj):
        if obj.finish and obj.start:
            delta = obj.finish - obj.start
            total_seconds = int(delta.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return '-'
    duration.short_description = 'Продолжительность'

    def save_related(self, request, form, formsets, change):
        """
        Обрабатывает сохранение связанных объектов.
        Использует общую логику из _create_kkz_competitions.
        """
        super().save_related(request, form, formsets, change)

        from .forms import _create_kkz_competitions

        obj = form.instance

        kkz_lab_formset = next((fs for fs in formsets if fs.model == KkzLab), None)
        if not kkz_lab_formset:
            return

        labs_info = []
        preview_assignments = {}

        for kkz_lab_index, kkz_lab_form in enumerate(kkz_lab_formset.forms):
            if kkz_lab_form.cleaned_data.get('DELETE', False):
                continue

            if not kkz_lab_form.cleaned_data.get('lab'):
                continue

            lab = kkz_lab_form.cleaned_data['lab']
            tasks = list(kkz_lab_form.cleaned_data.get('tasks', [])) or list(LabTask.objects.filter(lab=lab))
            num_tasks = kkz_lab_form.cleaned_data.get('num_tasks') or len(tasks)

            labs_info.append({
                'lab': lab,
                'lab_id': lab.id,
                'tasks': tasks,
                'task_ids': [t.id for t in tasks],
                'num_to_assign': num_tasks
            })

            # Получаем assignments из inline-формы
            assignments_str = kkz_lab_form.cleaned_data.get('assignments', '{}')
            try:
                assignments_from_form = json.loads(assignments_str) if assignments_str else {}
                if assignments_from_form:
                    preview_assignments[lab.id] = assignments_from_form
            except json.JSONDecodeError:
                pass

        if labs_info:
            _create_kkz_competitions(obj, labs_info, preview_assignments if preview_assignments else None)


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


class MyAttachmentAdmin(admin.ModelAdmin):
    form = MyAttachmentAdminForm
    list_display = ('name', 'file', 'uploaded')
    readonly_fields = ('uploaded',)


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
# Отменяем автоматическую регистрацию django-summernote и регистрируем с нашей формой
try:
    admin.site.unregister(get_attachment_model())
except admin.sites.NotRegistered:
    pass
admin.site.register(MyAttachment, MyAttachmentAdmin)