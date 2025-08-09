from hashlib import md5
import logging

from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save, post_delete
from django.utils.text import slugify
from django_summernote.models import AbstractAttachment
from django.contrib.auth.models import AbstractUser

from slugify import slugify
from rest_framework import serializers
from django.core.exceptions import ValidationError
from django.utils import timezone
from interface.eveFunctions import pf_login, create_lab, logout, create_all_lab_nodes_and_connectors, \
    delete_lab_with_session_destroy, change_user_workspace, create_directory, get_user_workspace_relative_path
from .validators import validate_top_level_array
from .config import *
logger = logging.getLogger(__name__)


def default_json():
    return [{}]


def get_platform_choices():
    return [
        ("PN", "PNETLab"),
        ("NO", "Без платформы"),
        ("CMD", "Командная строка")
    ]


class LabProgram(models.TextChoices):
    INFOBOR = "INFOBOR", "Информационное противоборство"
    COMPETITION = "COMPETITION", "Соревнования"

class LabType(models.TextChoices):
    HW = "HW", "Домашнее задание"
    EXAM = "EXAM", "Экзамен"
    PZ = "PZ", "Практическое занятие"
    COMPETITION = "COMPETITION", "Соревнование"


class LearningYear(models.IntegerChoices):
    FIRST = 1, "Первый"
    SECOND = 2, "Второй"
    THIRD = 3, "Третий"


class Lab(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField('Имя', max_length=255)
    description = models.TextField('Описание')
    answer_flag = models.CharField('Ответный флаг', max_length=1024, blank=True, null=True)
    slug = models.SlugField('Название в адресной строке', max_length=255)
    platform = models.CharField('Платформа', max_length=3, choices=get_platform_choices, default="NO")
    program = models.CharField('Образовательная программа', max_length=32, choices=LabProgram.choices, default=LabProgram.INFOBOR)
    lab_type = models.CharField('Тип работы', max_length=32, choices=LabType.choices, default=LabType.HW)
    learning_years = models.JSONField('Годы обучения', default=list, null=True, blank=True)
    
    # Хранение изображения в БД
    cover = models.ImageField('Обложка', upload_to='interface/labs/covers/', blank=True, null=True)
    
    NodesData = models.JSONField('Ноды', default=default_json, validators=[validate_top_level_array])
    ConnectorsData = models.JSONField('Коннекторы', default=default_json, validators=[validate_top_level_array])
    Connectors2CloudData = models.JSONField(
        'Облачные коннекторы', default=default_json, validators=[validate_top_level_array]
    )
    NetworksData = models.JSONField('Сети', default=default_json, validators=[validate_top_level_array])

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name = 'Лабораторная работа'
        verbose_name_plural = 'Лабораторные работы'
        constraints = [
            models.UniqueConstraint(fields=['slug', 'lab_type'], name='unique_slug_labtype')
        ]

    def save(self, *args, **kwargs):
        # Генерируем slug на основе имени
        base_slug = slugify(self.name)
        
        # Проверяем уникальность slug
        counter = 1
        original_slug = base_slug
        while Lab.objects.filter(slug=base_slug).exclude(pk=self.pk).exists():
            base_slug = f"{original_slug}-{counter}"
            counter += 1
        
        self.slug = base_slug
        
        super(Lab, self).save(*args, **kwargs)

    def get_platform(self):
        return self.platform


class LabSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lab
        fields = ("name", "description")


class LabLevel(models.Model):
    lab = models.ForeignKey(Lab, related_name="levels", on_delete=models.CASCADE, verbose_name="Лабораторная работа")
    level_number = models.PositiveIntegerField("Вариант")
    description = models.TextField("Описание варианта")

    class Meta:
        verbose_name = "Вариант"
        verbose_name_plural = "Варианты"
        ordering = ["lab", "level_number"]

    def __str__(self):
        return f"Вариант {self.level_number} - {self.description}"


class LabTask(models.Model):
    lab = models.ForeignKey(Lab, related_name="options", on_delete=models.CASCADE, verbose_name="Лабораторная работа")
    task_id = models.CharField("Идентификатор задания", max_length=255, null=True)
    description = models.TextField("Описание задания", blank=True, null=True)

    class Meta:
        verbose_name = "Задание"
        verbose_name_plural = "Задания"

    def __str__(self):
        return self.description


class Platoon(models.Model):
    number = models.fields.IntegerField('Номер взвода', unique=True)
    learning_year = models.IntegerField('Год обучения', choices=LearningYear.choices, default=LearningYear.FIRST)

    def __str__(self):
        return str(self.number)

    @classmethod
    def get_default_platoon(cls):
        return Platoon.objects.get_or_create(number=0)[0].id

    class Meta:
        verbose_name = 'Взвод'
        verbose_name_plural = 'Взвода'


class MyAttachment(AbstractAttachment):
    class Meta:
        verbose_name = 'Прикрепленный файл'
        verbose_name_plural = 'Прикрепленные файлы'


class User(AbstractUser):
    platoon = models.ForeignKey(Platoon,
                                related_name="students",
                                on_delete=models.CASCADE,
                                verbose_name="взвод",
                                null=True)
    pnet_login = models.CharField('Имя в Pnet', max_length=255, primary_key=False, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            if not self.platoon_id:
                default_platoon, created = Platoon.objects.get_or_create(number=0)
                self.platoon = default_platoon
        if not self.username:
            self.username = self.last_name + "_" + self.first_name
        self.pnet_login = slugify(self.username)

        super(User, self).save(*args, **kwargs)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'


class Team(models.Model):
    name = models.CharField('Имя', max_length=255)
    slug = models.SlugField('Название в адресной строке', unique=True, max_length=255)
    users = models.ManyToManyField(User, verbose_name="Участники", blank=True)

    class Meta:
        verbose_name = 'Команда'
        verbose_name_plural = 'Команды'

    def __str__(self):
        return self.name

    @classmethod
    def post_create(cls, sender, instance, created, *args, **kwargs):
        if not created:
            return

        url = get_pnet_url()
        Login = 'pnet_scripts'
        Pass = 'eve'
        cookie, xsrf = pf_login(url, Login, Pass)
        logging.debug(f'create dir with name {instance.slug}')
        create_directory(url, get_pnet_base_dir(), instance.slug, cookie)
        logout(url)


class Answers(models.Model):
    lab = models.ForeignKey(Lab, related_name="lab", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True)
    datetime = models.DateTimeField(null=True)
    lab_task = models.ForeignKey(LabTask, related_name="lab_task", on_delete=models.CASCADE, null=True)

    def __str__(self):
        if self.user:
            return str(self.lab.name + " " + self.user.username)
        else:
            return str(self.lab.name + " " + self.team.slug)

    class Meta:
        verbose_name = 'Ответ'
        verbose_name_plural = 'Ответы'
        constraints = [
            models.CheckConstraint(
                check=(
                        Q(user__isnull=False, team__isnull=True) |
                        Q(user__isnull=True, team__isnull=False)
                ),
                name="%(app_label)s_%(class)s_exclusive_user_team"
            )
        ]

class Kkz(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название ККЗ", null=True, blank=False)
    start = models.DateTimeField(verbose_name="Начало")
    finish = models.DateTimeField(verbose_name="Окончание")
    platoons = models.ManyToManyField(Platoon, verbose_name="Взвода", blank=True)
    non_platoon_users = models.ManyToManyField(User, verbose_name="Студенты", blank=True)
    unified_tasks = models.BooleanField("Единые задания для всех", default=False)
    def get_users(self):
        users = User.objects.filter(platoon__in=self.platoons.all())
        users = users.union(User.objects.filter(id__in=self.non_platoon_users.values('id')))
        return users
    def __str__(self):
        return self.name
    class Meta:
        verbose_name = "ККЗ"
        verbose_name_plural = "ККЗ"


class KkzLab(models.Model):
    kkz = models.ForeignKey('Kkz', on_delete=models.CASCADE, related_name='kkz_labs')
    lab = models.ForeignKey('Lab', on_delete=models.CASCADE, verbose_name="Лабораторная работа")
    tasks = models.ManyToManyField('LabTask', verbose_name="Задания", blank=True)
    num_tasks = models.PositiveIntegerField("Количество заданий для распределения", default=1)

    def __str__(self):
        return f"{self.kkz.name} - {self.lab.name}"

    class Meta:
        verbose_name = 'Лабораторная работа в ККЗ'
        verbose_name_plural = 'Лабораторные работы в ККЗ'


class Competition(models.Model):
    slug = models.SlugField('Название в адресной строке', unique=True, max_length=255)
    start = models.DateTimeField("Начало")
    finish = models.DateTimeField("Конец")
    lab = models.ForeignKey(Lab,
                            related_name="competitions",
                            on_delete=models.CASCADE,
                            verbose_name="Лабораторная работа",
                            null=True)

    platoons = models.ManyToManyField(Platoon, verbose_name="Взвода", blank=True)
    participants = models.IntegerField("Количество участников", null=True, default=0)
    level = models.ForeignKey(LabLevel, related_name="competitions", on_delete=models.CASCADE,
                              verbose_name="Вариант", null=True, blank=True)
    tasks = models.ManyToManyField(LabTask, blank=True, verbose_name="Задания")
    deleted = models.BooleanField(default=False)

    kkz = models.ForeignKey(Kkz, related_name="competitions", on_delete=models.CASCADE, verbose_name="ККЗ",
                            null=True, blank=True)
    num_tasks = models.PositiveIntegerField("Количество заданий для распределения", default=1, blank=True)
    non_platoon_users = models.ManyToManyField(User, verbose_name="Студенты", blank=True)
    # issued_labs = models.ManyToManyField(IssuedLabs, blank=True)

    def clean(self):
        if not self.start or not self.finish:
            raise ValidationError("Нет даты!")
        if self.start >= self.finish:
            raise ValidationError("Начало должно быть позже конца!")
        if self.finish <= timezone.now():
            raise ValidationError("Экзамен уже закончился!")

    def delete(self, *args, **kwargs):
        for issue in self.competition_users.all():
            issue.delete()

        super(Competition, self).delete(*args, **kwargs)

    class Meta:
        verbose_name = 'Экзамен'
        verbose_name_plural = 'Экзамены'

    def save(self, *args, **kwargs):
        # Generate slug only once on creation; preserve on updates
        if self._state.adding and not self.slug:
            base_slug = slugify(f"{self.lab.name}-{self.start:%Y%m%d%H%M%S}-{self.lab.lab_type}")
            unique_slug = base_slug + timezone.now().strftime("%Y%m%d%H%M%S%f")
            self.slug = md5(unique_slug.encode('utf-8')).hexdigest()
        super(Competition, self).save(*args, **kwargs)


class Competition2User(models.Model):
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name='competition_users',
        null=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_competitions'
    )
    level = models.ForeignKey(
        LabLevel,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Вариант"
    )
    tasks = models.ManyToManyField(
        LabTask,
        related_name='assigned_tasks',
        blank=True,
        verbose_name="Задания"
    )
    done = models.BooleanField('Завершено', default=False)

    deleted = models.BooleanField(default=False)

    def delete_from_platform(self, final=False):
        if self.deleted:
            return
        if self.competition.lab.get_platform() == "PN":
            url = get_pnet_url()
            Login = 'pnet_scripts'
            Pass = 'eve'
            cookie, xsrf = pf_login(url, Login, Pass)
            delete_lab_with_session_destroy(url, self.competition.lab.slug, get_pnet_base_dir(), cookie, xsrf,
                                            self.user.username)
            delete_lab_with_session_destroy(url, self.competition.lab.name, get_pnet_base_dir(), cookie, xsrf,
                                            self.user.username)
            logout(url)

        self.deleted = True
        if not final:
            self.save()

    class Meta:
        verbose_name = 'Задание участника'
        verbose_name_plural = 'Задания участников'

    def delete(self, *args, **kwargs):
        self.delete_from_platform(final=True)
        super(Competition2User, self).delete(*args, **kwargs)

    @classmethod
    def post_create(cls, sender, instance, created, *args, **kwargs):
        if not created:
            return
        lab = instance.competition.lab
        if lab.get_platform() == "PN":
            Login = 'pnet_scripts'
            Pass = 'eve'
            cookie, xsrf = pf_login(get_pnet_url(), Login, Pass)
            create_lab(get_pnet_url(), lab.slug, "", get_pnet_base_dir(), cookie, xsrf,
                       instance.user.username)
            create_all_lab_nodes_and_connectors(get_pnet_url(), lab, get_pnet_base_dir(), cookie, xsrf,
                                                instance.user.username)
            logout(get_pnet_url())


class TeamCompetition(Competition):
    teams = models.ManyToManyField(
        Team,
        through='TeamCompetition2Team',
        verbose_name='Команды',
        blank=True
    )

    class Meta:
        verbose_name = 'Соревнование'
        verbose_name_plural = 'Соревнования'


class TeamCompetition2Team(models.Model):
    competition = models.ForeignKey(
        TeamCompetition,
        on_delete=models.CASCADE,
        related_name='competition_teams'
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='team_competitions'
    )
    tasks = models.ManyToManyField(
        LabTask,
        blank=True,
        verbose_name="Задания"
    )
    deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.competition} — {self.team}"

    @classmethod
    def post_create(cls, sender, instance, created, *args, **kwargs):
        if not created:
            return
        lab = instance.competition.lab
        if lab.get_platform() == "PN":
            Login = 'pnet_scripts'
            Pass = 'eve'
            cookie, xsrf = pf_login(get_pnet_url(), Login, Pass)
            create_lab(get_pnet_url(), lab.slug, "", get_pnet_base_dir(), cookie, xsrf,
                       instance.team.slug)
            create_all_lab_nodes_and_connectors(get_pnet_url(), lab, get_pnet_base_dir(), cookie, xsrf,
                                                instance.team.slug)
            logging.debug(f'competition created for team {instance.team.slug}')
            for user in instance.team.users.all():
                logging.debug(f'change workspace for {user.pnet_login} to {get_user_workspace_relative_path()}/{instance.team.slug}')
                change_user_workspace(
                    get_pnet_url(), cookie, xsrf, user.pnet_login, f'{get_user_workspace_relative_path()}/{instance.team.slug}'
                )

            logout(get_pnet_url())

    def delete_from_platform(self, final=False):
        if self.deleted and not final:
            return
        if self.competition.lab.get_platform() == "PN":
            url = get_pnet_url()
            Login = 'pnet_scripts'
            Pass = 'eve'
            cookie, xsrf = pf_login(url, Login, Pass)
            delete_lab_with_session_destroy(url, self.competition.lab.slug, get_pnet_base_dir(), cookie, xsrf,
                                            self.team.slug)
            for user in self.team.users.all():
                change_user_workspace(
                    get_pnet_url(), cookie, xsrf, user.pnet_login, f'{get_user_workspace_relative_path()}/{user.pnet_login}'
                )

            logout(url)

        self.deleted = True
        if not final:
            self.save()

    @classmethod
    def on_through_delete(cls, sender, instance, **kwargs):
        logging.debug('on_through_delete call')
        instance.delete_from_platform(final=True)


post_save.connect(Competition2User.post_create, sender=Competition2User)
post_save.connect(TeamCompetition2Team.post_create, sender=TeamCompetition2Team)
post_delete.connect(TeamCompetition2Team.on_through_delete, sender=TeamCompetition2Team)
