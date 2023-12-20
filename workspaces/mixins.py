from typing import Optional, Union

from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.db.models import F

from rest_framework.exceptions import ValidationError

from taskmanager.email import InviteUserEmail
from .models import WorkSpace, InvitedUsers, Board, Column, Task

User = get_user_model()


class GetInvitedMixin:
    def get_invitation(self, **key) -> None:
        self.invitation = (
            InvitedUsers.objects.filter(**key)
            .select_related('user', 'workspace')
            .first()
        )
        if self.invitation is None:
            raise ValidationError(
                {"token": self.default_error_messages['invalid_token']},
                'invalid_token'
            )


class GetWorkSpaceMixin:
    def get_workspace(self) -> WorkSpace:
        try:
            pk = self.context.get('view').kwargs.get('pk')
            workspace = (
                WorkSpace.objects
                .prefetch_related('users', 'invited', 'board', )
                .get(pk=pk)
            )
            return workspace

        except WorkSpace.DoesNotExist:
            raise ValidationError(
                {"detail": 'Такого РП не существует'},
            )


class CheckWorkSpaceUsersMixin:
    """Проверка, что пользователь является участником РП"""
    def user_is_added_to_workspace(self) -> bool:
        if (self.user.id, ) in self.workspace.users.all().values_list('id'):
            return True

        return False


class CheckWorkSpaceInvitedMixin:
    """Проверка, что пользователь приглашен в РП"""
    def user_is_invited_to_workspace(self) -> bool:
        if (self.user.id, ) in self.workspace.invited.all().values_list('id'):
            return True

        return False


class GetInvitationMixin:
    def get_or_create_invitation(self, user: User, workspace: WorkSpace) -> InvitedUsers:
        try:
            invitation = InvitedUsers.objects.get(user=user, workspace=workspace)
        except InvitedUsers.DoesNotExist:
            invitation = InvitedUsers.objects.create(
                user=user,
                token=get_random_string(length=32),
                workspace=workspace,
            )

        context = {
            'invitation': invitation,
            'workspace': workspace.name,
        }
        to = [invitation.user.email]
        InviteUserEmail(self.request, context).send(to)

        return invitation


class GetOrCreateUserMixin:
    def get_or_create_user(self, email: str) -> User:
        """При добавлении пользователя в РП находит указанного пользователя или создает нового"""
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            user_data = {'email': email, 'password': None, 'is_active': False, }
            user = User.objects.create_user(**user_data)

        return user


class UserNoAuthOrThisUser:
    def check_auth_user(self, user: User) -> bool:
        """
        Проверка, если пользователь авторизован, то это нужный пользователь.
        (Например, что по приглашению перешел тот же пользователь, которого пригласили)
        """
        if any([isinstance(self.request.user, AnonymousUser), self.request.user == user]):
            return True

        return False


class DefaultWorkSpaceMixin:
    """Создание РП по умолчанию"""
    def create_default_workspace(self, user: User, create_for_board: Optional[bool] = None) -> WorkSpace:
        workspace = WorkSpace.objects.create(owner=user, name='Рабочее пространство 1')
        workspace.users.add(user)

        if not create_for_board:
            Board.objects.create(name='Доска 1', work_space=workspace)

        return workspace


class ColumnValidateMixin:
    def column_validate(self, new_index: int, new_col: Column):
        valid_columns = self.instance.column.board.column_board.all().values_list('id')
        if (new_col.id, ) not in valid_columns:
            raise ValidationError(
                {"column": 'Задачи можно перемещать только между колонками внутри доски'},
                'invalid_column'
            )

        with transaction.atomic():
            # меняем номер колонки, чтобы при валидации индекса задачи
            # не было ошибок в крайних случаях (0 или максимальное значение индекса)
            self.instance.column = new_col
            self.instance.save()

            if new_index is not None:
                self.index_validate(new_index, new_col)


class IndexValidateMixin:
    def index_validate(self, new_index: int, new_col: Optional[Column] = None):
        """
        Валидация нового индекса обьекта. Проверяет, что индекс не выходит за
        пределы количества обьектов
        """
        if new_col is not None:
            # условие применяется для задач, если задачу перемещают между колонками,
            # список обьектов нужно получить из другой колонки
            # self.objects = Task.objects.filter(column=new_col).order_by('index')
            self.objects = new_col.task.all().order_by('index')
        else:
            self.objects = self.context['view'].get_queryset()

        if new_index >= len(self.objects) or new_index < 0:
            raise ValidationError(
                {"index": f'Порядковый номер должен соответсвовать количеству обьектов: '
                          f'0 <= index <= {len(self.objects) - 1}'},
                'invalid_index'
            )


class ShiftIndexMixin:
    def shift_indexes(self, instance: Union[Task, Column], new_index: int) -> Union[Task, Column]:
        """Функция пересчитывает порядковые номера обьектов при их перемещении"""
        if new_index > instance.index:
            instance = self.left_shift(instance, new_index)
        elif new_index < instance.index:
            instance = self.right_shift(instance, new_index)

        return instance

    def insert_object(self, instance: Task, new_index: int) -> Task:
        """Функция перемещения задачи между колонками"""
        # присваиваем индекс None, так как при вставке задачи в новую колонку вставка идет с конца
        instance.index = None
        return self.right_shift(instance, new_index)

    def left_shift(self, instance: Union[Task, Column], new_index: int) -> Union[Task, Column]:
        """Сдвиг порядковых номеров влево при перемещении обьекта вправо"""
        slice_objects = self.objects[instance.index: new_index + 1]

        with transaction.atomic():
            for obj in slice_objects:
                obj.index -= 1
            instance.index = new_index
            instance.__class__.objects.bulk_update(slice_objects, ['index'])
            return instance

    def right_shift(self, instance: Union[Task, Column], new_index: int) -> Union[Task, Column]:
        """Сдвиг порядковых номеров вправо при перемещении обьекта влево"""
        # если индекс None, то пересчет порядковых номеров идет до последнего элемента
        right_border = instance.index + 1 if instance.index is not None else None
        slice_objects = self.objects[new_index: right_border]

        with transaction.atomic():
            for obj in slice_objects:
                obj.index += 1

            instance.index = new_index
            instance.__class__.objects.bulk_update(slice_objects, ['index'])
            return instance


class ShiftIndexAfterDeleteMixin:
    def delete_shift_index(self, instance: Union[Task, Column]) -> None:
        """Пересчет порядковых номеров при удалении объекта"""
        model_class = instance.__class__
        column_id = self.kwargs.get('column_id', None)

        with transaction.atomic():
            objs = model_class.objects.filter(index__gte=instance.index + 1)

            if model_class == Task:
                assert column_id is not None
                objs = objs.filter(column_id=column_id)

            objs.update(index=F('index') - 1)
