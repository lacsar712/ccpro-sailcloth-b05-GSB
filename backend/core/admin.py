from django.contrib import admin

from .models import ClothRoll, DipRun, Loft, SystemSetting


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ("id", "cured_readonly", "updated_at")
    fields = ("cured_readonly",)

    def has_add_permission(self, request):
        return not SystemSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Loft)
admin.site.register(ClothRoll)
admin.site.register(DipRun)
