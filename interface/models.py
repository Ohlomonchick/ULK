from django.db import models
from django.db.models.signals import post_save
from django.utils.text import slugify
from django_summernote.models import AbstractAttachment
from django.contrib.auth.models import AbstractUser

from slugify import slugify
from rest_framework import serializers
import requests
from django.core.exceptions import ValidationError
from django.utils import timezone
from interface.eveFunctions import pf_login, create_lab, logout, create_all_lab_nodes_and_connectiors, \
    delete_lab_with_session_destroy
from .validators import validate_top_level_array
from .config import *


def default_json():
    return [{}]


def get_platform_choices():
    return [
        ("PN", "PNETLab"),
        ("NO", "Без платформы")
    ]


class Lab(models.Model):
    name = models.CharField('Имя', max_length=255, primary_key=True)
    description = models.TextField('Описание')
    answer_flag = models.CharField('Ответный флаг', max_length=1024, blank=True, null=True)
    slug = models.SlugField('Название в адресной строке', unique=True)
    platform = models.CharField(max_length=3, choices=get_platform_choices, default="NO")

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

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        address = os.environ.get('CREATE_ADDRESS', "")
        port = os.environ.get('CREATE_PORT', "")

        if port and address and self.get_platform() == "PN":
            serializer = LabSerializer(self)
            requests.post(f"http://{address}:{port}", data=serializer.data)

        super(Lab, self).save(*args, **kwargs)

    def get_platform(self):
        return self.platform


class LabSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lab
        fields = ("name", "description")


class Answers(models.Model):
    lab = models.ForeignKey(Lab, related_name="lab", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    datetime = models.DateTimeField(null=True)

    def __str__(self):
        return str(self.lab.name + " " + self.user.username)

    class Meta:
        verbose_name = 'Ответ'
        verbose_name_plural = 'Ответы'


class Platoon(models.Model):
    number = models.fields.IntegerField('Номер взвода')

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
            if not self.username:
                self.username = self.last_name + "_" + self.first_name
            if not self.platoon_id:
                default_platoon, created = Platoon.objects.get_or_create(number=0)
                self.platoon = default_platoon
        self.pnet_login = slugify(self.username)

        super(User, self).save(*args, **kwargs)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'


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


class Competition(models.Model):
    slug = models.SlugField('Название в адресной строке', unique=True)
    start = models.DateTimeField("Начало")
    finish = models.DateTimeField("Конец")
    lab = models.ForeignKey(Lab,
                            related_name="competitions",
                            on_delete=models.CASCADE,
                            verbose_name="Лабораторная работа",
                            null=True)

    platoons = models.ManyToManyField(Platoon, verbose_name="Взвода")
    participants = models.IntegerField("Количество участников", null=True, default=0)
    level = models.ForeignKey(LabLevel, related_name="competitions", on_delete=models.CASCADE,
                              verbose_name="Вариант",  null=True, blank=True)
    tasks = models.ManyToManyField(LabTask, blank=True, verbose_name="Задания")
    deleted = models.BooleanField(default=False)

    def clean(self):
        if self.start >= self.finish:
            raise ValidationError("Начало должно быть позже конца!")
        if self.finish <= timezone.now():
            raise ValidationError("Экзамен уже закончился!")

    def delete_from_platform(self):
        if self.deleted:
            return
        if self.lab.get_platform() == "PN":
            Login = 'pnet_scripts'
            Pass = 'eve'
            cookie, xsrf = pf_login(PNET_URL, Login, Pass)
            AllUsers = User.objects.filter(platoon_id__in=self.platoons.all())
            for user in AllUsers:
                delete_lab_with_session_destroy(PNET_URL, self.lab.name, PNET_BASE_DIR, cookie,
                                                xsrf, user.username)
            logout(PNET_URL)
        self.deleted = True
        self.save()

    def delete(self, *args, **kwargs):
        self.delete_from_platform()
        super(Competition, self).delete(*args, **kwargs)

    class Meta:
        verbose_name = 'Экзамен'
        verbose_name_plural = 'Экзамены'

    def save(self, *args, **kwargs):
        self.slug = slugify(self.lab.name + str(self.start))
        super(Competition, self).save(*args, **kwargs)


class IssuedLabs(models.Model):
    lab = models.ForeignKey(
        Lab,
        related_name="lab_for_issue",
        on_delete=models.CASCADE,
        verbose_name="Лабораторная работа"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  verbose_name='Кому назначаем')
    date_of_appointment = models.DateTimeField('Начало', blank=False)
    end_date = models.DateTimeField('Конец', blank=False)
    done = models.BooleanField('Завершено', default=False)
    level = models.ForeignKey(LabLevel, related_name="issued", on_delete=models.CASCADE,
                              verbose_name="Вариант", null=True, blank=True)
    tasks = models.ManyToManyField(LabTask, blank=True, verbose_name="Задания")
    deleted = models.BooleanField(default=False)

    def clean(self):
        if self.date_of_appointment >= self.end_date:
            raise ValidationError("Начало должно быть позже конца!")
        if self.end_date <= timezone.now():
            raise ValidationError("Экзамен уже закончился!")

    @classmethod
    def post_create(cls, sender, instance, created, *args, **kwargs):
        if not created:
            return
        if instance.lab.get_platform() == "PN":
            Login = 'pnet_scripts'
            Pass = 'eve'
            cookie, xsrf = pf_login(PNET_URL, Login, Pass)
            create_lab(PNET_URL, instance.lab.name, "", PNET_BASE_DIR, cookie, xsrf,
                       instance.user.username)
            create_all_lab_nodes_and_connectiors(PNET_URL, instance.lab, PNET_BASE_DIR, cookie, xsrf,
                                                 instance.user.username)
            logout(PNET_URL)
        print(instance)

    def save(self, *args, **kwargs):
        super(IssuedLabs, self).save(*args, **kwargs)

    def delete_from_platform(self):
        if self.deleted:
            return
        if self.lab.get_platform() == "PN":
            url = PNET_URL
            Login = 'pnet_scripts'
            Pass = 'eve'
            cookie, xsrf = pf_login(url, Login, Pass)
            delete_lab_with_session_destroy(url, self.lab.name, PNET_BASE_DIR, cookie, xsrf,
                                            self.user.username)
            logout(url)

        self.deleted = True
        self.save()

    def delete(self, *args, **kwargs):
        self.delete_from_platform()
        super(IssuedLabs, self).delete(*args, **kwargs)

    # def __str__(self):
    #     return str(self.lab.name) + " " + str(self.user.username)

    class Meta:
        verbose_name = 'Назначенная работа'
        verbose_name_plural = 'Назначенные работы'


class Competition2User(models.Model):
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name='competition_users'
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


post_save.connect(IssuedLabs.post_create, sender=IssuedLabs)
