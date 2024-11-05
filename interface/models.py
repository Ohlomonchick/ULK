from django.db import models
from django.utils.text import slugify
from django_summernote.models import AbstractAttachment
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from slugify import slugify
from rest_framework import serializers
import requests
import os
from django.core.exceptions import ValidationError
from django.utils import timezone
from interface.eveFunctions import pf_login, create_lab, logout, create_all_lab_nodes_and_connectiors, delete_lab_with_session_destroy
from .validators import validate_top_level_array
import json


def default_json():
    return [{}]


class Lab(models.Model):
    name = models.CharField('Имя', max_length=255, primary_key=True)
    description = models.TextField('Описание')
    answer_flag = models.CharField('Ответный флаг', max_length=1024, blank=True,null=True)
    slug = models.SlugField('Название в адресной строке', unique=True)

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
        print(self.slug)
        address = os.environ.get('CREATE_ADDRESS', "")
        port = os.environ.get('CREATE_PORT', "")

        if port and address:
            serializer = LabSerializer(self)
            requests.post(f"http://{address}:{port}", data=serializer.data)

        super(Lab, self).save(*args, **kwargs)


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
    
    def save(self, *args, **kwargs):
        if not self.pk:
            if not self.username:
                self.username = self.last_name + "_" + self.first_name

            if not self.platoon_id:
                default_platoon, created = Platoon.objects.get_or_create(number=0)
                self.platoon = default_platoon

        super(User, self).save(*args, **kwargs)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'


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

    def clean(self):
        if self.start >= self.finish:
            raise ValidationError("Начало должно быть позже конца!")
        if self.finish <= timezone.now():
            raise ValidationError("Экзамен уже закончился!")

    def delete(self, *args, **kwargs):
        url = "http://172.18.4.160"
        Login = 'pnet_scripts'
        Pass = 'eve'
        cookie, xsrf = pf_login(url, Login, Pass)
        AllUsers = User.objects.filter(platoon_id__in=self.platoons.all())
        for user in AllUsers:
            delete_lab_with_session_destroy(url, self.lab.name, "/Practice work/Test_Labs/api_test_dir", cookie, xsrf, user.username)
        logout(url)
        super(Competition, self).delete(*args, **kwargs)

    class Meta:
        verbose_name = 'Экзамен'
        verbose_name_plural = 'Экзамены'

    def save(self, *args, **kwargs):
        self.slug = slugify(self.lab.name + str(self.start))
        super(Competition, self).save(*args, **kwargs)


class IssuedLabs(models.Model):
    lab = models.ForeignKey(Lab, related_name="lab_for_issue", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_of_appointment = models.DateTimeField('Дата назначения')
    end_date = models.DateTimeField('Дата окончания')
    done = models.BooleanField('Завершено', default=False)

    def save(self, *args, **kwargs):

        url = "http://172.18.4.160"
        Login = 'pnet_scripts'
        Pass = 'eve'
        cookie, xsrf = pf_login(url, Login, Pass)
        create_lab(url, self.lab.name, "", "/Practice work/Test_Labs/api_test_dir", cookie, xsrf, self.user.username)
        create_all_lab_nodes_and_connectiors(url, self.lab, "/Practice work/Test_Labs/api_test_dir", cookie, xsrf, self.user.username)
        logout(url)
        super(IssuedLabs, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        url = "http://172.18.4.160"
        Login = 'pnet_scripts'
        Pass = 'eve'
        cookie, xsrf = pf_login(url, Login, Pass)
        delete_lab_with_session_destroy(url, self.lab.name, "/Practice work/Test_Labs/api_test_dir", cookie, xsrf, self.user.username)
        logout(url)
        super(IssuedLabs, self).delete(*args, **kwargs)

    # def __str__(self):
    #     return str(self.lab.name) + " " + str(self.user.username)

    class Meta:
        verbose_name = 'Назначенная работа'
        verbose_name_plural = 'Назначенные работы'