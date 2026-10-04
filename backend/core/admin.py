from django.contrib import admin

from .models import ClothRoll, CureLockSetting, DipRun, Loft

admin.site.register(Loft)
admin.site.register(ClothRoll)
admin.site.register(DipRun)
admin.site.register(CureLockSetting)
