from rest_framework import generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth import get_user_model
from django.utils.timezone import now
from django.db.utils import IntegrityError

from djoser.views import UserViewSet
from djoser.serializers import UidAndTokenSerializer

from drf_spectacular.utils import extend_schema

from taskmanager.email import ChangeEmail
from taskmanager.serializers import (ChangeEmailSerializer,
                                     ChangeEmailConfirmSerializer,
                                     PasswordResetSerializer,
                                     InvitedPasswordSerializer)
from workspaces import mixins

User = get_user_model()


class CustomUserViewSet(mixins.DefaultWorkSpaceMixin,
                        UserViewSet):
    """
    Вьюсет на базе вьюсета библиотеки Djoser.
    Часть методов переопределена под требования проекта.
    """

    def get_serializer_class(self):
        if self.action == 'check_link':
            return UidAndTokenSerializer
        elif self.action == 'reset_password':
            return PasswordResetSerializer
        elif self.action == 'reset_password_invited':
            return InvitedPasswordSerializer

        return super().get_serializer_class()

    def get_permissions(self):
        if self.action == 'reset_password_invited':
            self.permission_classes = [permissions.AllowAny]

        return super().get_permissions()

    @action(['post'], detail=False)
    def activation(self, request, *args, **kwargs):
        """
        Метод активации учетной записи пользователя.
        В качестве ответа возвращаются JWT токены, чтобы юзер сразу был авторизован после активации.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user

        super().activation(request, *args, **kwargs)

        self.create_default_workspace(user)

        refresh = RefreshToken.for_user(user)

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_200_OK)

    @extend_schema(description='Проверка действительности ссылки восстановления пароля',
                   responses={204: None, },)
    @action(methods=['post'], detail=False, permission_classes=[permissions.AllowAny])
    def check_link(self, request, *args, **kwargs):
        """
        Проверка что ссылка /{uid}/{token}/ действительна, чтобы при повторном переходе по использованной ссылке
        на фронте сразу вывели сообщение об ошибке, а не после отправки пароля.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["post"], detail=False)
    def reset_password_confirm(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.user.set_password(serializer.data["new_password"])
        serializer.user.is_active = True

        if hasattr(serializer.user, "last_login"):
            serializer.user.last_login = now()
        serializer.user.save()

        self.create_default_workspace(serializer.user)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["post"], detail=False, url_name='reset_password_invited')
    def reset_password_invited(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.invited_user.user
        user.set_password(serializer.data["new_password"])
        user.is_active = True
        user.save()

        serializer.invited_user.delete()

        refresh = RefreshToken.for_user(user)

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_200_OK)

    def set_username(self, request, *args, **kwargs):
        """
        Метод не используется.
        """
        pass

    def reset_username(self, request, *args, **kwargs):
        """
        Метод не используется.
        """
        pass

    def reset_username_confirm(self, request, *args, **kwargs):
        """
        Метод не используется.
        """
        pass


class ChangeEmailView(generics.GenericAPIView):
    """
    Запрос на смену почты. Пользователю будет отправлена ссылка для подтверждения на указанную почту.
    """
    serializer_class = ChangeEmailSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={204: None, })
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        context = serializer.validated_data
        to = [context['new_email']]
        ChangeEmail(self.request, context).send(to)

        return Response(status=status.HTTP_204_NO_CONTENT)


class ChangeEmailConfirmView(generics.GenericAPIView):
    """
    Подтверждение смены почты пользователя.
    Токен получить из ссылки auth/change_email/{token}.
    """
    serializer_class = ChangeEmailConfirmSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={204: None, })
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        new_email = serializer.validated_data
        user.email = new_email

        try:
            user.save()
        except IntegrityError:
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={'new_email': 'Эта электронная почта уже используется'})
        else:
            return Response(status=status.HTTP_204_NO_CONTENT)


# class CreateSuperuser(generics.CreateAPIView):
#     serializer_class = UserCreateSerializer
#     permission_classes = [permissions.AllowAny]
#
#     def post(self, request, *args, **kwargs):
#         user = User.objects.get(email='ilya.posholokk@gmail.com')
#         user.is_superuser = user.is_staff = True
#         user.save()
#         return Response(status=status.HTTP_204_NO_CONTENT)
