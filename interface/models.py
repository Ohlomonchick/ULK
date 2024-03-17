from django.db import models
from django.utils.text import slugify
from django_summernote.models import AbstractAttachment
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.template.defaultfilters import slugify
from rest_framework import serializers
import requests
import os


class Lab(models.Model):
    name = models.CharField('Имя', max_length=255, primary_key=True)
    description = models.TextField('Описание')
    answer_flag = models.CharField('Ответный флаг', max_length=1024, blank=True,null=True)
    slug = models.SlugField('Название в адресной строке', unique=True)

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name = 'Лабораторная работа'
        verbose_name_plural = 'Лабораторные работы'

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        serializer = LabSerializer(self)

        address = os.environ.get('CREATE_ADDRESS', "192.0.0.1")
        port = os.environ.get('CREATE_PORT', "5555")
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
        return str(self.lab.name + " " +self.user.username)

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
            self.username = self.last_name + "_" + self.first_name
            self.set_password("test.test") 
        super(User, self).save(args, kwargs)

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

    platoons = models.ManyToManyField(Platoon)

    class Meta:
        verbose_name = 'Соревнование'
        verbose_name_plural = 'Соревнования'

    def save(self, *args, **kwargs):
        self.slug = slugify(self.lab.name + str(self.start))
        super(Competition, self).save(*args, **kwargs)


class IssuedLabs(models.Model):
    lab = models.ForeignKey(Lab, related_name="lab_for_issue", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_of_appointment = models.DateField('Дата назначения')
    end_date = models.DateField('Дата окончания')
    done = models.BooleanField('Завершено',default = False)

    # def __str__(self):
    #     return str(self.lab.name) + " " + str(self.user.username)

    class Meta:
        verbose_name = 'Назначенная работа'
        verbose_name_plural = 'Назначенные работы'