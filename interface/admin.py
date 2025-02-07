import random
from django.contrib import admin
from django_summernote.admin import SummernoteModelAdmin
from django.contrib.auth.admin import UserAdmin
from django_json_widget.widgets import JSONEditorWidget
from .models import *
from .forms import CustomUserCreationForm, CompetitionForm, KkzForm
from django.db.models import JSONField
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
    extra = 0
    fields = ('user', 'level', 'tasks')
    readonly_fields = ('user', )
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


    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if obj and obj.lab:
            formset.form.base_fields['level'].queryset = LabLevel.objects.filter(lab=obj.lab)

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
    extra = 1
    fields = ['lab', 'tasks', 'num_tasks']
    filter_horizontal = ['tasks']

    class Media:
        js = (
            'admin/js/load_levels.js', 'admin/js/jquery-3.7.1.min.js',
        )

    # def formfield_for_manytomany(self, db_field, request, **kwargs):
    #     if db_field.name == "tasks":
    #         if request.method == "POST" and "lab" in request.POST:
    #             try:
    #                 lab_id = int(request.POST.get("lab"))
    #                 kwargs["queryset"] = LabTask.objects.filter(lab_id=lab_id)
    #             except (ValueError, TypeError):
    #                 kwargs["queryset"] = LabTask.objects.none()
    #         elif 'object_id' in request.resolver_match.kwargs:
    #             try:
    #                 kkz_lab_id = request.resolver_match.kwargs['object_id']
    #                 kkz_lab = KkzLab.objects.get(id=kkz_lab_id)
    #                 kwargs["queryset"] = LabTask.objects.filter(lab=kkz_lab.lab)
    #             except KkzLab.DoesNotExist:
    #                 kwargs["queryset"] = LabTask.objects.none()
    #         else:
    #             kwargs["queryset"] = LabTask.objects.none()
    #     return super().formfield_for_manytomany(db_field, request, **kwargs)


class KkzAdmin(admin.ModelAdmin):
    inlines = [KkzLabInline]
    list_display = ('name', 'start', 'finish')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        for kkz_lab in obj.kkz_labs.all():
            competition = Competition.objects.create(
                start=obj.start,
                finish=obj.finish,
                lab=kkz_lab.lab,
                kkz=obj,
            )

            competition.platoons.set(obj.platoons.all())
            competition.non_platoon_users.set(obj.non_platoon_users.all())

            users = obj.get_users()
            tasks = list(kkz_lab.tasks.all())
            num_tasks = kkz_lab.num_tasks

            if tasks and users:
                for user in users:
                    assigned_tasks = random.sample(tasks, min(num_tasks, len(tasks)))
                    competition2user, created = Competition2User.objects.get_or_create(
                        competition=competition,
                        user=user)
                    if competition.kkz.unified_tasks:
                        competition.tasks.set(assigned_tasks)
                    else:
                        competition2user.tasks.set(assigned_tasks)


admin.site.register(Lab, LabModelAdmin)
admin.site.register(Platoon, admin.ModelAdmin)
admin.site.register(Competition, CompetitionAdmin)
admin.site.register(User, MyUserAdmin)
admin.site.register(Answers, admin.ModelAdmin)
admin.site.unregister(DjangoJob)
admin.site.unregister(DjangoJobExecution)
admin.site.register(Kkz, KkzAdmin)