from django.contrib import admin

from .models import JobRun, Notification, NotificationLog, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'kind', 'category', 'created_at', 'read_at')
    list_filter = ('category', 'kind')
    readonly_fields = [f.name for f in Notification._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'due', 'kind', 'channel', 'bucket', 'created_at')
    list_filter = ('channel', 'kind')
    readonly_fields = [f.name for f in NotificationLog._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'inbox', 'push', 'email')


@admin.register(JobRun)
class JobRunAdmin(admin.ModelAdmin):
    list_display = ('name', 'run_day', 'status', 'started_at', 'finished_at')
    list_filter = ('name', 'status')
    readonly_fields = [f.name for f in JobRun._meta.fields]

    def has_add_permission(self, request):
        return False
