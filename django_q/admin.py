"""Admin module for Django."""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from django_q.conf import Conf, croniter
from django_q.models import Failure, OrmQ, Schedule, Success
from django_q.tasks import async_task
from django.db.models import Q
from django.db import connection

class TaskAdmin(admin.ModelAdmin):
    """model admin for success tasks."""

    list_display = ("name", "func", "started", "stopped", "time_taken", "group")

    def has_add_permission(self, request):
        """Don't allow adds."""
        return False

    def get_queryset(self, request):
        """Only show successes."""
        qs = super(TaskAdmin, self).get_queryset(request)
        if connection.vendor == "djongo":
            ids=[]
            for data in qs.filter(Q(attempt_count__gt = 0)):
                if data.success:
                    ids.append(data.id)
            return qs.filter(id__in = ids)
        else:
            return qs.filter(success=True)

    search_fields = ("name", "func", "group")
    readonly_fields = []
    list_filter = ("group",)

    def get_readonly_fields(self, request, obj=None):
        """Set all fields readonly."""
        return list(self.readonly_fields) + [field.name for field in obj._meta.fields]


def retry_failed(FailAdmin, request, queryset):
    """Submit selected tasks back to the queue."""
    for task in queryset:
        async_task(task.func, *task.args or (), hook=task.hook, **task.kwargs or {})
        task.delete()


retry_failed.short_description = _("Resubmit selected tasks to queue")


class FailAdmin(admin.ModelAdmin):
    """model admin for failed tasks."""

    list_display = ("name", "func", "started", "stopped", "short_result")

    def has_add_permission(self, request):
        """Don't allow adds."""
        return False

    actions = [retry_failed]
    search_fields = ("name", "func")
    list_filter = ("group",)
    readonly_fields = []

    def get_readonly_fields(self, request, obj=None):
        """Set all fields readonly."""
        return list(self.readonly_fields) + [field.name for field in obj._meta.fields]


class ScheduleAdmin(admin.ModelAdmin):
    """model admin for schedules"""

    list_display = (
        "id",
        "name",
        "func",
        "schedule_type",
        "repeats",
        "cluster",
        "next_run",
        "last_run",
        "success",
    )

    # optional cron strings
    if not croniter:
        readonly_fields = ("cron",)

    list_filter = ("next_run", "schedule_type", "cluster")
    search_fields = ("func",)
    list_display_links = ("id", "name")


class QueueAdmin(admin.ModelAdmin):
    """queue admin for ORM broker"""

    list_display = ("id", "key", "task_id", "name", "func", "lock")

    def save_model(self, request, obj, form, change):
        obj.save(using=Conf.ORM)

    def delete_model(self, request, obj):
        obj.delete(using=Conf.ORM)

    def get_queryset(self, request):
        return super(QueueAdmin, self).get_queryset(request).using(Conf.ORM)

    def has_add_permission(self, request):
        """Don't allow adds."""
        return False

    list_filter = ("key",)


admin.site.register(Schedule, ScheduleAdmin)
admin.site.register(Success, TaskAdmin)
admin.site.register(Failure, FailAdmin)

if Conf.ORM or Conf.TESTING:
    admin.site.register(OrmQ, QueueAdmin)
