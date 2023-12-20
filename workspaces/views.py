import string
import random

from rest_framework import viewsets, permissions, status, generics
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from django_eventstream import send_event

from drf_spectacular.utils import extend_schema, extend_schema_view

from taskmanager.serializers import CurrentUserSerializer
from .models import WorkSpace, Board, InvitedUsers, Column, Task
from . import serializers, mixins
from .permissions import UserInWorkSpaceUsers, UserIsBoardMember, UserHasAccessTasks
from .serializers import InviteUserSerializer

User = get_user_model()


@extend_schema_view(
    list=extend_schema(description='Список всех Рабочих пространств авторизованного пользователя'),
    create=extend_schema(description='Создать Рабочее пространство'),
    retrieve=extend_schema(description='Информация о конктретном рабочем пространстве'),
    update=extend_schema(description='Обновить все данные РП (на данный момент только имя)'),
    partial_update=extend_schema(description='Частично обновить данные РП (на данный момент только имя)'),
    destroy=extend_schema(description='Удалить РП'),
)
class WorkSpaceViewSet(mixins.GetInvitationMixin,
                       mixins.UserNoAuthOrThisUser,
                       mixins.CheckWorkSpaceUsersMixin,
                       viewsets.ModelViewSet):
    serializer_class = serializers.WorkSpaceSerializer
    queryset = WorkSpace.objects.all().select_related('owner').prefetch_related('users', 'invited', 'board')
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return serializers.CreateWorkSpaceSerializer
        elif self.action == 'invite_user':
            return serializers.WorkSpaceInviteSerializer
        elif self.action == 'confirm_invite':
            return serializers.InviteUserSerializer
        elif self.action == 'kick_user':
            return serializers.UserIDSerializer
        elif self.action == 'resend_invite':
            return serializers.ResendInviteSerializer

        return self.serializer_class

    def get_permissions(self):
        if self.action == "confirm_invite":
            self.permission_classes = [permissions.AllowAny, ]

        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        queryset = queryset.filter(users=user)
        return queryset.order_by('created_at')  # вывод РП сортируется по дате создания

    @extend_schema(responses={201: serializers.WorkSpaceSerializer(many=True)}, )
    def create(self, request, *args, **kwargs):
        """
        Создание рабочего пространства.
        Изменен только ответ Клиенту - вместо созданного обьекта возвращается массив объектов.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        queryset = self.get_queryset()
        serialized_data = self.serializer_class(queryset, many=True).data
        return Response(data=serialized_data, status=status.HTTP_201_CREATED)

    @extend_schema(description='Пригласить пользователя по email.\n\n'
                               'Пользователи добавляются по одному.'
                               'Если пользователя не существует, он будет создан.',
                   responses={200: serializers.WorkSpaceSerializer}, )
    @action(methods=['post'], detail=True, url_name='invite_user')
    def invite_user(self, request, *args, **kwargs):
        """
        Представление для приглашения пользователей в РП.
        Если приглашенного пользователя не существует, он будет создан с пустым паролем.
        Пользователь сперва добавляется в список приглашенных: invited.
        Затем отправляется ссылка на почту с приглашением.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, workspace = serializer.user, serializer.workspace
        workspace.invited.add(user)
        self.get_or_create_invitation(user, workspace)

        return Response(data=self.serializer_class(workspace).data, status=status.HTTP_200_OK)

    @extend_schema(
        description='Подтверждение приглашения в РП.\n\nПройдя по ссылке пользователь будет добавлен в РП. '
                    'Ссылка на приглашение: invite/workspace/{token}\n\n'
                    'Если ответ 200 - у пользователя нет пароля, отправить на '
                    '/auth/users/reset_password_invited/\n\nОтвет 204 - у пользователя есть пароль ',
        responses={204: None, 200: InviteUserSerializer, },
    )
    @action(['post'], detail=False, url_name='confirm_invite')
    def confirm_invite(self, request, *args, **kwargs):
        """
        Добавление пользователя в РП и удаление из приглашенных.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        self.user = serializer.invitation.user
        self.workspace = serializer.invitation.workspace

        if not self.check_auth_user(self.user):
            return Response(status=status.HTTP_403_FORBIDDEN)

        # если пользователь уже добавлен в РП, но не закончил регистрацию, нужно вернуть ответ,
        # по которому его направят на установку пароля
        data = InviteUserSerializer(serializer.invitation).data
        if not self.user.has_usable_password() and self.user_is_added_to_workspace():
            return Response(data=data, status=status.HTTP_200_OK)

        self.workspace.invited.remove(self.user)
        self.workspace.users.add(self.user)

        if self.user.has_usable_password():
            serializer.invitation.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(data=data, status=status.HTTP_200_OK)

    @extend_schema(description='Удаление пользователей из РП\n\nУдаление как из участников так и из приглашенных',
                   responses={200: serializers.WorkSpaceSerializer}, )
    @action(['post'], detail=True, url_name='kick_user')
    def kick_user(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.data['user_id']

        self.workspace = WorkSpace.objects.get(pk=kwargs['pk'])

        if user_id == self.workspace.owner_id:
            return Response(data={'detail': 'Нельзя удалить владельца РП'},
                            status=status.HTTP_400_BAD_REQUEST)

        self.kick_from_workspace(user_id)

        workspace_data = self.serializer_class(self.workspace).data
        return Response(data=workspace_data, status=status.HTTP_200_OK)

    @extend_schema(description='Повторная отправка ссылки с приглашением пользователя.',
                   responses={204: None, }, )
    @action(['post'], detail=True, url_name='resend_invite')
    def resend_invite(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.user
        workspace = serializer.workspace

        self.get_or_create_invitation(user, workspace)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def kick_from_workspace(self, user_id):
        self.workspace.users.remove(user_id)
        self.workspace.invited.remove(user_id)
        InvitedUsers.objects.filter(user_id=user_id).delete()


class UserList(generics.ListAPIView):
    """
    Вывод списка всех пользователей при поиске по имени и почте.
    """
    serializer_class = serializers.UserListSerializer
    queryset = User.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        filter_email = self.request.query_params.get('users')

        if filter_email and len(filter_email) > 2:
            queryset = (queryset
                        .filter(email__istartswith=filter_email, is_active=True)
                        .exclude(pk=self.request.user.id)
                        )

            return queryset
        return None


class TestSSEMessage(generics.CreateAPIView):
    """
    Создать SSE - передает случайную строку.\n\n
    Слушать /events/\n\n
    channel: test\n\n
    event_type: test_message
    """
    serializer_class = None
    queryset = None

    def post(self, request, *args, **kwargs):
        message = ''.join(random.choice(string.ascii_letters) for _ in range(10))
        send_event('test', 'test_message', {'message': message})
        return Response(status=status.HTTP_204_NO_CONTENT)


class TestSSEUser(generics.CreateAPIView):
    """
    Создать SSE - передает текущего юзера.\n\n
    Слушать /events/\n\n
    channel: test\n\n
    event_type: test_user
    """
    serializer_class = CurrentUserSerializer
    queryset = User.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        user = self.serializer_class(user).data
        send_event('test', 'test_user', {'user': user})
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(list=extend_schema(description='Список всех досок указанного РП.'),
                    create=extend_schema(description='Создать Доску'),
                    retrieve=extend_schema(description='Информация о конкретной доске'),
                    update=extend_schema(description='Обновить доску'),
                    partial_update=extend_schema(description='Частично обновить доску'),
                    destroy=extend_schema(description='Удалить доску'),
                    )
class BoardViewSet(viewsets.ModelViewSet):
    """Представление досок"""
    serializer_class = serializers.BoardSerializer
    queryset = Board.objects.all().prefetch_related('column_board', 'members')
    permission_classes = [permissions.IsAuthenticated, UserInWorkSpaceUsers]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        workspace = self.kwargs.get('workspace_id')
        queryset = (queryset
                    .filter(work_space__users=user)
                    .filter(work_space_id=workspace)
                    )

        return queryset.order_by('-id')

    def get_serializer_class(self):
        if self.action == 'create':
            return serializers.CreateBoardSerializer

        return super().get_serializer_class()


class BoardCreateWithoutWorkSpace(mixins.DefaultWorkSpaceMixin,
                                  generics.CreateAPIView):
    """Создание доски вне РП"""
    serializer_class = serializers.CreateBoardNoWorkSpaceSerializer
    queryset = Board.objects.all()
    permission_classes = [permissions.IsAuthenticated]


@extend_schema_view(list=extend_schema(description='Список всех колонок доски.'),
                    create=extend_schema(description='Создать колонку на доске'),
                    retrieve=extend_schema(description='Информация о конкретной колонке'),
                    update=extend_schema(description='Обновить колонку (название и порядковый номер)'),
                    partial_update=extend_schema(description='Частично обновить колонку (название/порядковый номер)'),
                    destroy=extend_schema(description='Удалить колонку'),
                    )
class ColumnViewSet(mixins.ShiftIndexMixin,
                    mixins.ShiftIndexAfterDeleteMixin,
                    viewsets.ModelViewSet):
    serializer_class = serializers.ColumnSerializer
    queryset = Column.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserIsBoardMember]

    def get_serializer_class(self):
        if self.action == 'create':
            return serializers.CreateColumnSerializer

        return super().get_serializer_class()

    def get_queryset(self):
        """Колонки отфилрованы по доске"""
        queryset = super().get_queryset()
        board_id = self.kwargs.get('board_id', None)
        queryset = queryset.filter(board_id=board_id)
        return queryset.order_by('index')

    def destroy(self, request, *args, **kwargs):
        """
        При удалении колонки перезаписывает порядковые номера оставшихся колонок
        """
        instance = self.get_object()
        self.delete_shift_index(instance)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TaskViewSet(mixins.ShiftIndexMixin,
                  mixins.ShiftIndexAfterDeleteMixin,
                  viewsets.ModelViewSet):
    serializer_class = serializers.TaskSerializer
    queryset = Task.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasAccessTasks]

    def get_serializer_class(self):
        if self.action == 'create':
            return serializers.TaskCreateSerializer

        return super().get_serializer_class()

    def get_queryset(self):
        """Задачи фильтруются по колонкам"""
        queryset = super().get_queryset()
        column_id = self.kwargs.get('column_id', None)
        queryset = (queryset
                    .filter(column_id=column_id)
                    .select_related('column')
                    .select_related('column__board')
                    )
        return queryset.order_by('index')

    def destroy(self, request, *args, **kwargs):
        """
        При удалении задачи перезаписывает порядковые номера оставшихся задач
        """
        instance = self.get_object()
        self.delete_shift_index(instance)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def update(self, request, *args, **kwargs):
        """Обновление задач"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        current_column = kwargs.get('column_id', None)
        new_column = serializer.validated_data.get('column', None)

        # если задачу переместили в другую колонку, в текущей порядковые номера нужно сдвинуть
        if new_column is not None and new_column != current_column:
            self.delete_shift_index(instance)

        return Response(serializer.data)
