from rest_framework import permissions


class IsAdminRole(permissions.BasePermission):
    """仅角色为 admin 的用户可写；其他认证用户只读。"""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return getattr(request.user, "role", None) == "admin"
