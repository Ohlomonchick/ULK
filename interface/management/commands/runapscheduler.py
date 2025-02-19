# runapscheduler.py
import logging
import datetime
import time

from django.conf import settings
from django.utils import timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.core.management.base import BaseCommand
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from django_apscheduler import util

from interface.models import Competition2User, TeamCompetition2Team

logger = logging.getLogger(__name__)


@util.close_old_connections
def delete_labs_job():
    """
    Удаляем лабы и соревнования через час после их окончания
    """
    delete_time = timezone.now() + datetime.timedelta(hours=1)
    competitions2users = Competition2User.objects.filter(competition__finish__gte=delete_time, deleted=False)

    for competition2user in competitions2users:
        competition2user.delete_from_platform()
        time.sleep(20)


@util.close_old_connections
def delete_competition2team_job():
    """
    Удаляем лабы и соревнования через час после их окончания
    """
    delete_time = timezone.now() + datetime.timedelta(minutes=10)
    competitions2teams = TeamCompetition2Team.objects.filter(competition__finish__gte=delete_time, deleted=False)

    for competition2user in competitions2teams:
        competition2user.delete_from_platform()
        time.sleep(20)


# The `close_old_connections` decorator ensures that database connections, that have become
# unusable or are obsolete, are closed before and after your job has run. You should use it
# to wrap any jobs that you schedule that access the Django database in any way.
@util.close_old_connections
def delete_old_job_executions(max_age=604_800):
    """
    This job deletes APScheduler job execution entries older than `max_age` from the database.
    It helps to prevent the database from filling up with old historical records that are no
    longer useful.

    :param max_age: The maximum length of time to retain historical job execution records.
                    Defaults to 7 days.
    """
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


class Command(BaseCommand):
    help = "Runs APScheduler."

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        scheduler.add_job(
            delete_labs_job,
            trigger=CronTrigger(hour="*/1"),  # Every hour
            id="delete_labs_job",  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'delete_labs_job'.")

        scheduler.add_job(
            delete_competition2team_job,
            trigger=CronTrigger(minute="*/15"),  # Every 15 minutes
            id="delete_competition2team_job",
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'delete_competition2team_job'.")

        scheduler.add_job(
            delete_old_job_executions,
            trigger=CronTrigger(
                day_of_week="mon", hour="00", minute="00"
            ),  # Midnight on Monday, before start of the next work week.
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
        )
        logger.info(
            "Added weekly job: 'delete_old_job_executions'."
        )

        try:
            logger.info("Starting scheduler...")
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Stopping scheduler...")
            scheduler.shutdown()
            logger.info("Scheduler shut down successfully!")
