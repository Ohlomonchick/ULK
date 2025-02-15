from django.db import models


class ConfigEntry(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()

    class Meta:
        verbose_name = 'Переменная окружения'
        verbose_name_plural = 'Переменные окружения'

    def __str__(self):
        return f"{self.key} = {self.value}"
