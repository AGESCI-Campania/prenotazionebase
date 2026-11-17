from django.contrib import admin

from .models import Listino, VersioneListino, VoceListino


class VoceListinoInline(admin.TabularInline):
    model = VoceListino
    extra = 0

    def _modificabile(self, obj: VersioneListino | None) -> bool:
        return obj is None or not obj.in_uso()

    def has_add_permission(self, request, obj=None):
        return self._modificabile(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._modificabile(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._modificabile(obj) and super().has_delete_permission(request, obj)


@admin.register(Listino)
class ListinoAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo")


@admin.register(VersioneListino)
class VersioneListinoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "pubblicata_il", "valida_dal")
    list_filter = ("listino",)
    inlines = (VoceListinoInline,)

    def has_change_permission(self, request, obj=None):
        return (obj is None or not obj.in_uso()) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return (obj is None or not obj.in_uso()) and super().has_delete_permission(request, obj)
