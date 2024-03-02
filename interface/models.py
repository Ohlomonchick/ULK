from django.db import models
from django.utils.text import slugify
from django_summernote.models import AbstractAttachment
from django.contrib.auth.models import AbstractUser
from django.conf import settings


class Lab(models.Model):
    name = models.CharField('Имя', max_length=255, primary_key=True)
    description = models.TextField('Описание')
    answer_flag = models.CharField('Ответный флаг', max_length=1024, null=True)
    slug = models.SlugField('Название в адресной строке', unique=True)

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name = 'Лабораторная работа'
        verbose_name_plural = 'Лабораторные работы'

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super(Lab, self).save(*args, **kwargs)


class Answers(models.Model):
    lab = models.ForeignKey(Lab, related_name="lab", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)


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
    name = models.CharField('Имя', max_length=127, null=True)
    second_name = models.CharField('Фамилия', max_length=127, null=True)
    platoon = models.ForeignKey(Platoon,
                                related_name="students",
                                on_delete=models.CASCADE,
                                verbose_name="взвод",
                                null=True)
    
    def save(self, *args, **kwargs):
        super(User, self).save(args, kwargs)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'


class IssuedLabs(models.Model):
    lab = models.ForeignKey(Lab, related_name="lab_for_issue", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_of_appointment = models.DateField('Дата назначения')
    end_date = models.DateField('Дата окончания')
    done = models.BooleanField('Завершено')

    # def __str__(self):
    #     return str(self.lab.name) + " " + str(self.user.username)

    class Meta:
        verbose_name = 'Назначенная работа'
        verbose_name_plural = 'Назначенные работы'

