from rest_framework.permissions import BasePermission

from workspaces.models import Board, Column


class UserInWorkSpaceUsers(BasePermission):
    """Настройка прав для досок, пользователь является участником РП"""
    def has_permission(self, request, view):
        workspace_id = int(view.kwargs.get('workspace_id', None))
        if (workspace_id, ) in request.user.joined_workspaces.all().only('id').values_list('id'):
            return True

        return False


class UserIsBoardMember(BasePermission):
    """Настройка прав для колонок, пользователь является участником РП"""

    def has_permission(self, request, view):
        board_id = int(view.kwargs.get('board_id', None))
        user = request.user.id

        try:
            board = (Board.objects
                     .select_related('work_space')
                     .only('work_space__users')
                     .get(pk=board_id))
            if (user, ) in board.work_space.users.all().values_list('id'):
                return True
        except Board.DoesNotExist:
            return False

        return False


class UserHasAccessTasks(BasePermission):
    """Только участники РП имеют доступ к задачам"""

    def has_permission(self, request, view):
        column_id = int(view.kwargs.get('column_id', None))
        user = request.user.id

        try:
            column = (Column.objects.select_related('board__work_space')
                      .only('board__work_space__users')
                      .get(pk=column_id))
            if (user, ) in column.board.work_space.users.all().values_list('id'):
                return True

        except Column.DoesNotExist:
            return False
        return False
