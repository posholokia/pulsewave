from datetime import timedelta

from django.utils.timezone import now
from django.contrib.auth import get_user_model

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from pulsewave.settings import WORKSAPCES
from taskmanager.serializers import CurrentUserSerializer
from . import mixins
from .models import WorkSpace, Board, InvitedUsers, Task, Column

User = get_user_model()


class CreateWorkSpaceSerializer(serializers.ModelSerializer):
    """Сериализотор создания РП"""
    # поле owner скрыто для редактирования и автоматически заполняется текущим пользователем
    owner = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = WorkSpace
        fields = (
            'owner',
            'name',
        )

    def create(self, validated_data):
        """
        При создании РП, пользователь, его создавший автоматически доабвляется
        в список пользователей РП
        """
        instance = super().create(validated_data)
        user = validated_data.get('owner')
        instance.users.add(user)
        return instance


class WorkspaceBoardsSerializer(serializers.ModelSerializer):
    """Сериализация досок внутри РП"""

    class Meta:
        model = Board
        fields = (
            'id',
            'name',
        )


class UserListWorkSpace(serializers.ModelSerializer):
    """Сериализация пользователей внутри РП"""
    represent_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        read_only_fields = ['email']
        fields = (
            'id',
            'email',
            'name',
            'represent_name',
            'avatar',
            'role',
        )

    def get_role(self, obj):
        workspace = self.context.get("workspace", None)

        if not workspace:
            return 'Invited'
        elif workspace.owner.id == obj.id:
            return 'Owner'
        else:
            return 'Member'

    def get_represent_name(self, obj):
        return obj.name if obj.name else obj.email.split('@')[0]


class WorkSpaceSerializer(serializers.ModelSerializer):
    boards = WorkspaceBoardsSerializer(many=True, read_only=True, source='board')
    users = serializers.SerializerMethodField()
    invited = UserListWorkSpace(many=True, read_only=True)

    class Meta:
        model = WorkSpace
        fields = (
            'id',
            'name',
            'users',
            'invited',
            'boards',
        )

    def get_users(self, obj):
        users_list = obj.users.all()
        users = UserListWorkSpace(users_list, many=True, read_only=True, context={'workspace': obj}).data
        return users

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['boards'] = sorted(representation['boards'], key=lambda x: x['id'], reverse=True)
        return representation


class WorkSpaceInviteSerializer(mixins.GetWorkSpaceMixin,
                                mixins.GetOrCreateUserMixin,
                                mixins.CheckWorkSpaceUsersMixin,
                                mixins.CheckWorkSpaceInvitedMixin,
                                serializers.Serializer):
    """
    Сериализотор пришлашения пользователей.
    Сериализует почту добавленного пользователя.
    """
    email = serializers.EmailField()

    default_error_messages = {
        'already_invited': 'Пользователь уже приглашен в это рабочее пространство',
        'already_added': 'Пользователь уже добавлен в это рабочее пространство',
    }

    def validate(self, attrs):
        user_email = attrs['email']
        self.workspace = self.get_workspace()
        self.user = self.get_or_create_user(user_email)

        if self.user_is_added_to_workspace():
            raise ValidationError(
                {"email": self.default_error_messages['already_added']},
                'already_added'
            )

        if self.user_is_invited_to_workspace():
            raise ValidationError(
                {"email": self.default_error_messages['already_invited']},
                'already_invited'
            )

        return attrs


class InviteUserSerializer(mixins.GetInvitedMixin,
                           mixins.CheckWorkSpaceUsersMixin,
                           mixins.CheckWorkSpaceInvitedMixin,
                           serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    default_error_messages = {
        'invalid_token': 'Недействительный токен',
        'token_expired': 'Срок действия токена истек',
        'already_invited': 'Пользователь уже был добавлен в это РП',
    }

    class Meta:
        model = InvitedUsers
        read_only_fields = ['user', 'workspace']
        fields = (
            'token',
            'user',
            'workspace',
        )

    def get_user(self, obj):
        return obj.user.email

    def validate(self, attrs):
        self.get_invitation(**attrs)

        time_out = timedelta(seconds=WORKSAPCES['INVITE_TOKEN_TIMEOUT'])
        expired_token = self.invitation.created_at + time_out

        if now() > expired_token:
            raise ValidationError(
                {"token": self.default_error_messages['token_expired']},
                'token_expired'
            )

        return attrs


class UserListSerializer(serializers.ModelSerializer):
    """
    Сериализатор списка пользователей при поиске.
    """

    name = serializers.SerializerMethodField()
    added = serializers.SerializerMethodField()
    invited = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'name',
            'email',
            'added',
            'invited',
        )

    def get_name(self, obj):
        return obj.representation_name()

    def get_added(self, obj):
        workspace_id = self.context.get('view').request.query_params.get('workspace')
        if obj.joined_workspaces.filter(id=workspace_id).exists():
            return True
        return False

    def get_invited(self, obj):
        workspace_id = self.context.get('view').request.query_params.get('workspace')
        if obj.invited_to_workspaces.filter(id=workspace_id).exists():
            return True
        return False


class UserIDSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()

    def validate(self, attrs):
        try:
            self.user = User.objects.get(pk=attrs['user_id'])
            return attrs
        except User.DoesNotExist:
            raise ValidationError(
                {"user_id": self.default_error_messages['invalid_user']},
                'invalid_user'
            )


class ResendInviteSerializer(mixins.GetWorkSpaceMixin,
                             mixins.CheckWorkSpaceUsersMixin,
                             mixins.CheckWorkSpaceInvitedMixin,
                             UserIDSerializer):
    """
    Сериализатор повторной отправки приглашения
    """
    default_error_messages = {
        'already_invited': 'Пользователь уже принял приглашение',
        'incorrect_invite': 'Пользователя нет в списке приглашенных в это РП',
        'invalid_user': 'Такого пользователя не существует',
    }

    def validate(self, attrs):
        attrs = super().validate(attrs)

        self.workspace = self.get_workspace()

        if self.user_is_added_to_workspace():
            raise ValidationError(
                {"user_id": self.default_error_messages['already_invited']},
                'already_invited'
            )

        if self.user_is_invited_to_workspace():
            return attrs

        raise ValidationError(
            {"user_id": self.default_error_messages["incorrect_invite"]},
            'incorrect_invite'
        )


class CreateBoardSerializer(serializers.ModelSerializer):
    """
    Сериализатор создания доски
    """
    work_space = serializers.PrimaryKeyRelatedField(queryset=WorkSpace.objects.all(), required=False)

    class Meta:
        model = Board
        fields = (
            'id',
            'name',
            'work_space',
        )

    def create(self, validated_data):
        workspace_id = self.context['view'].kwargs.get('workspace_id', None)
        validated_data['work_space_id'] = workspace_id
        instance = Board.objects.create(**validated_data)
        return instance


class CreateBoardNoWorkSpaceSerializer(mixins.DefaultWorkSpaceMixin,
                                       serializers.ModelSerializer):
    """Создание доски вне РП, РП создается автоматически для доски"""

    class Meta:
        model = Board
        read_only_fields = ['work_space']
        fields = (
            'id',
            'name',
            'work_space',
        )

    def create(self, validated_data):
        user = self.context.get('request', None).user
        workspace = self.create_default_workspace(user, create_for_board=True)
        validated_data['work_space'] = workspace
        instance = Board.objects.create(**validated_data)
        return instance


class TaskCreateSerializer(serializers.ModelSerializer):
    """Сериализатор создания задач"""

    class Meta:
        model = Task
        read_only_fields = ['column', 'index', 'responsible', ]
        fields = (
            'id',
            'name',
            'index',
            'column',
            'responsible',
            'deadline',
            'description',
            # 'file',
            'priority',
            'color_mark',
            'name_mark',
        )

    def create(self, validated_data):
        number_of_tasks = len(self.context["view"].get_queryset())
        column_id = self.context['view'].kwargs['column_id']

        validated_data['index'] = number_of_tasks
        validated_data['column_id'] = column_id

        instance = Task.objects.create(**validated_data)
        return instance


class TaskListSerializer(mixins.ShiftIndexMixin,
                         serializers.ModelSerializer):
    """Сериализатор списка задач"""
    responsible = CurrentUserSerializer(many=True, read_only=True)

    class Meta:
        model = Task
        read_only_fields = ['column']
        fields = (
            'id',
            'name',
            'index',
            'column',
            'responsible',
            'priority',
            'color_mark',
            'name_mark',
        )


class TaskUsersListSerializer(serializers.ListSerializer):
    def validate(self, attrs):
        column_id = self.context["view"].kwargs['column_id']
        column = (Column.objects.select_related('board__work_space')
                  .only('board__work_space__users')
                  .get(pk=column_id))
        users = column.board.work_space.users.all().values_list('id')
        for user_id in attrs:
            if (user_id,) not in users:
                raise ValidationError(
                    {"responsible": f'Пользователь id:{user_id} не добавлен в рабочее пространство'},
                    'invalid_user'
                )
        return attrs

    def to_representation(self, data):
        iterable = data.all()

        return [
            CurrentUserSerializer(item).data for item in iterable
        ]


class TaskSerializer(mixins.ShiftIndexMixin,
                     mixins.IndexValidateMixin,
                     mixins.ColumnValidateMixin,
                     serializers.ModelSerializer):
    """Сериализатор задач"""
    responsible = TaskUsersListSerializer(child=serializers.IntegerField())

    class Meta:
        model = Task
        fields = (
            'id',
            'name',
            'index',
            'column',
            'responsible',
            'deadline',
            'description',
            # 'file',
            'priority',
            'color_mark',
            'name_mark',
        )

    # def to_representation(self, instance):
    #     representation = super().to_representation(instance)
    #     users = self.instance.responsible.all()
    #     representation['responsible'] = CurrentUserSerializer(users, many=True).data
    #     return representation

    def validate(self, attrs):
        new_index = attrs.get('index', None)
        new_col = attrs.get('column', None)

        if (new_col is not None) and (self.instance.column != new_col):
            self.column_validate(new_index, new_col)
            return attrs
        elif new_index is not None:
            self.index_validate(new_index, new_col)  # 1
            # если у задачи не сменилась колонка, удаляем из атрибутов,
            # обновлять ее у обьекта не требуется
            # иначе в методе update сработает insert вместо shift
            attrs.pop('column', None)

        return attrs

    def update(self, instance, validated_data):
        """При перемещении задач их порядковые номера нужно пересчитать"""
        new_index = validated_data.pop('index', None)
        new_col = validated_data.pop('column', None)
        users = validated_data.pop('responsible', None)

        if users is not None:
            instance.responsible.set(users)

        if new_col is not None:
            instance = self.insert_object(instance, new_index)
        elif new_index is not None:
            instance = self.shift_indexes(instance, new_index)

        return super().update(instance, validated_data)


class CreateColumnSerializer(serializers.ModelSerializer):
    class Meta:
        model = Column
        read_only_fields = ['index', 'board']
        fields = (
            'id',
            'name',
            'board',
            'index',
        )

    def create(self, validated_data):
        number_of_columns = len(self.context["view"].get_queryset())
        board_pk = self.context['view'].kwargs['board_id']

        validated_data['index'] = number_of_columns
        validated_data['board_id'] = board_pk

        instance = Column.objects.create(**validated_data)
        return instance


class ColumnSerializer(mixins.ShiftIndexMixin,
                       mixins.IndexValidateMixin,
                       serializers.ModelSerializer):
    """Сериализатор колонки с задачами"""
    tasks = TaskListSerializer(many=True, source='task', read_only=True)

    class Meta:
        model = Column
        read_only_fields = ['board']
        fields = (
            'id',
            'name',
            'index',
            'board',
            'tasks',
        )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['tasks'] = sorted(representation['tasks'], key=lambda x: x['index'])
        return representation

    def validate(self, attrs):
        new_index = attrs.get('index', None)

        if new_index is not None:
            self.index_validate(new_index)

        return attrs

    def update(self, instance, validated_data):
        new_index = validated_data.pop('index', None)

        if new_index is not None:
            instance = self.shift_indexes(instance, new_index)

        return super().update(instance, validated_data)


class BoardSerializer(serializers.ModelSerializer):
    """
    Сериализатор доски
    """
    # members = CurrentUserSerializer(many=True, read_only=True)
    columns = ColumnSerializer(many=True, read_only=True, source='column_board')

    class Meta:
        model = Board
        read_only_fields = ['members', 'work_space']
        fields = (
            'id',
            'name',
            'work_space',
            'members',
            'columns',
        )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['columns'] = sorted(representation['columns'], key=lambda x: x['index'])
        users = instance.work_space.users.all()
        # удалить после реализации добавления участников доски
        representation['members'] = CurrentUserSerializer(users, many=True).data
        return representation
