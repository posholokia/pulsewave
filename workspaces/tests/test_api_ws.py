from datetime import timedelta

from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from rest_framework_simplejwt.tokens import RefreshToken

from freezegun import freeze_time

from pulsewave.settings import WORKSAPCES
from workspaces.models import WorkSpace, InvitedUsers

from freezegun import freeze_time

User = get_user_model()


class BoardTestCase(APITestCase):
    def setUp(self):
        user_data = {
            'email': 'user1@example.com',
            'password': 'Pass!234',
            'is_active': True,
        }
        self.user = User.objects.create_user(**user_data)
        self.user.save()
        user_token = RefreshToken.for_user(self.user).access_token

        self.ws1 = WorkSpace.objects.create(owner=self.user, name='WorkSpace1')
        self.ws1.users.add(self.user)
        self.ws1.save()

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'JWT {user_token}')

        user_data['email'] = 'user2@example.com'
        self.user_two = User.objects.create_user(**user_data)
        self.user_two.save()
        ws2 = WorkSpace.objects.create(owner=self.user_two, name='WorkSpace2')
        ws2.users.add(self.user_two)
        ws2.save()

    def test_ws_create(self):
        data = {
            'name': 'My WorkSpace'
        }
        response = self.client.post(reverse('workspace-list'), data)
        self.assertEquals(status.HTTP_201_CREATED, response.status_code)
        self.assertEquals(2, len(WorkSpace.objects.filter(owner=self.user)))

        ws = WorkSpace.objects.get(name='My WorkSpace')
        self.assertEquals(self.user, ws.owner)
        self.assertIn(self.user, ws.users.all())

    def test_ws_create_fail_name(self):
        data = {
            'name': 'My WorkSpace name is very, very long, longer than necessary'
        }

        response = self.client.post(reverse('workspace-list'), data)
        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)
        error_code = response.data['name'][0].code
        self.assertEquals('max_length', error_code)

    def test_ws_get_list(self):
        response = self.client.get(reverse('workspace-list'))
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.assertEquals(1, len(response.data))

    def test_get_ws(self):
        response = self.client.get(reverse('workspace-detail', kwargs={'pk': self.ws1.id}))
        self.assertEquals(status.HTTP_200_OK, response.status_code)

    def test_patch_ws(self):
        data = {
            'name': 'Changed name',
        }
        response = self.client.patch(reverse('workspace-detail', kwargs={'pk': self.ws1.id}),
                                     data=data)
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.ws1.refresh_from_db()
        self.assertEquals('Changed name', self.ws1.name)

    def test_put_ws(self):
        data = {
            'name': 'Changed name',
        }
        response = self.client.put(reverse('workspace-detail', kwargs={'pk': self.ws1.id}),
                                   data=data)
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.ws1.refresh_from_db()
        self.assertEquals('Changed name', self.ws1.name)

    def test_delete_ws(self):
        response = self.client.delete(reverse('workspace-detail', kwargs={'pk': self.ws1.id}))
        self.assertEquals(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertEquals(0, len(self.user.owned_workspaces.all()))

    def test_invite_exists_user(self):
        data = {
            'email': 'user2@example.com',
        }
        response = self.client.post(reverse('workspace-invite_user', kwargs={'pk': self.ws1.id}), data)
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.assertIn(self.user_two, self.ws1.invited.all())

        invited_users = InvitedUsers.objects.filter(
            user__email=data['email'],
            workspace=self.ws1,
        ).exists()
        self.assertEquals(True, invited_users)

    def test_invite_new_user(self):
        data = {
            'email': 'new_user@example.com',
        }
        response = self.client.post(reverse('workspace-invite_user', kwargs={'pk': self.ws1.id}), data)
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.assertIn(('new_user@example.com', ), User.objects.all().values_list('email'))
        self.assertIn(('new_user@example.com', ), self.ws1.invited.all().values_list('email'))

        invited_users = InvitedUsers.objects.filter(
            user__email=data['email'],
            workspace=self.ws1,
        ).exists()
        self.assertEquals(True, invited_users)

    def test_fail_invite_user_added(self):
        data = {
            'email': 'user2@example.com',
        }
        self.ws1.users.add(self.user_two)
        response = self.client.post(reverse('workspace-invite_user', kwargs={'pk': self.ws1.id}), data)
        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)

        invited_users = InvitedUsers.objects.filter(
            user__email=data['email'],
            workspace=self.ws1,
        ).exists()
        self.assertEquals(False, invited_users)

    def test_fail_invite_user_invited(self):
        data = {
            'email': 'user2@example.com',
        }
        self.ws1.invited.add(self.user_two)
        response = self.client.post(reverse('workspace-invite_user', kwargs={'pk': self.ws1.id}), data)
        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)

        invited_users = InvitedUsers.objects.filter(
            user__email=data['email'],
            workspace=self.ws1,
        ).exists()
        self.assertEquals(False, invited_users)

    def test_confirm_invite_exists_user(self):
        data = {
            'email': 'user2@example.com',
        }
        self.client.post(reverse('workspace-invite_user', kwargs={'pk': self.ws1.id}), data)
        token = InvitedUsers.objects.get(user__email=data['email']).token

        response = self.client.post(reverse('workspace-confirm_invite'), {'token': token})
        self.assertEquals(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertEquals(0, len(self.ws1.invited.all()))
        self.assertEquals(2, len(self.ws1.users.all()))
        self.assertEquals(False, InvitedUsers.objects.filter(user__email=data['email']).exists())

    def test_confirm_invite_new_user(self):
        data = {
            'email': 'user3@example.com',
        }
        self.client.post(reverse('workspace-invite_user', kwargs={'pk': self.ws1.id}), data)
        token = InvitedUsers.objects.get(user__email=data['email']).token

        response = self.client.post(reverse('workspace-confirm_invite'), {'token': token})
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.assertEquals(0, len(self.ws1.invited.all()))
        self.assertEquals(2, len(self.ws1.users.all()))
        self.assertEquals(False, InvitedUsers.objects.filter(user__email=data['email']).exists())

    def test_invite_confirm_expired_token(self):
        no_auth_client = APIClient()
        data = {
            'email': 'user2@example.com',
        }
        self.client.post(reverse('workspace-invite_user', kwargs={'pk': self.ws1.id}), data)
        token = InvitedUsers.objects.get(user__email=data['email']).token

        timeout = timezone.now() + timedelta(seconds=(WORKSAPCES['INVITE_TOKEN_TIMEOUT']))
        with freeze_time(timeout + timedelta(seconds=1)):
            response = no_auth_client.post(reverse('workspace-confirm_invite'), {'token': token})
            self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)
            self.assertEquals('token_expired', response.data['token'][0].code)

        with freeze_time(timeout - timedelta(seconds=1)):
            response = no_auth_client.post(reverse('workspace-confirm_invite'), {'token': token})
            self.assertEquals(status.HTTP_204_NO_CONTENT, response.status_code)

    def test_fail_invite_confirm(self):
        no_auth_client = APIClient()
        data = {
            'email': 'user2@example.com',
        }
        self.client.post(reverse('workspace-invite_user', kwargs={'pk': self.ws1.id}), data)
        token = InvitedUsers.objects.get(user__email=data['email']).token
        InvitedUsers.objects.get(user__email=data['email']).delete()

        response = no_auth_client.post(reverse('workspace-confirm_invite'), {'token': token})
        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEquals('invalid_token', response.data['token'][0].code)

    def test_fail_invite_user_added(self):
        no_auth_client = APIClient()
        data = {
            'email': 'user2@example.com',
        }
        self.client.post(reverse('workspace-invite_user', kwargs={'pk': self.ws1.id}), data)
        token = InvitedUsers.objects.get(user__email=data['email']).token
        self.ws1.users.add(self.user_two)

        response = no_auth_client.post(reverse('workspace-confirm_invite'), {'token': token})
        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEquals('already_invited', response.data['token'][0].code)

    def test_fail_confirm_invitation_canceled(self):
        no_auth_client = APIClient()
        data = {
            'email': 'user2@example.com',
        }
        self.client.post(reverse('workspace-invite_user', kwargs={'pk': self.ws1.id}), data)
        token = InvitedUsers.objects.get(user__email=data['email']).token
        self.ws1.invited.remove(self.user_two)

        response = no_auth_client.post(reverse('workspace-confirm_invite'), {'token': token})
        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEquals('invalid_token', response.data['token'][0].code)

    def test_kick_user(self):
        data = {'user_id': self.user_two.id, }
        self.ws1.users.add(self.user_two)
        response = self.client.post(reverse('workspace-kick_user', kwargs={'pk': self.ws1.id}), data)
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.assertEquals(1, len(self.ws1.users.all()))

        self.ws1.invited.add(self.user_two)
        response = self.client.post(reverse('workspace-kick_user', kwargs={'pk': self.ws1.id}), data)
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.assertEquals(0, len(self.ws1.invited.all()))

    def test_fail_kick_wp_owner(self):
        data = {'user_id': self.user.id, }
        response = self.client.post(reverse('workspace-kick_user', kwargs={'pk': self.ws1.id}), data)

        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn(self.user, self.ws1.users.all())

    def test_resend_invite(self):
        invite_data = {'email': 'user2@example.com', }
        self.client.post(reverse('workspace-invite_user', kwargs={'pk': self.ws1.id}), invite_data)

        data = {'user_id': self.user_two.id, }
        response = self.client.post(reverse('workspace-resend_invite', kwargs={'pk': self.ws1.id}), data)
        self.assertEquals(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertEquals(True, InvitedUsers.objects.filter(user__email=invite_data['email']).exists())

    def test_fail_resend_invite(self):
        data = {'user_id': self.user_two.id, }
        response = self.client.post(reverse('workspace-resend_invite', kwargs={'pk': self.ws1.id}), data)
        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)

        invite_data = {'email': 'user2@example.com', }
        self.client.post(reverse('workspace-invite_user', kwargs={'pk': self.ws1.id}), invite_data)
        self.ws1.users.add(self.user_two)

        response = self.client.post(reverse('workspace-resend_invite', kwargs={'pk': self.ws1.id}), data)
        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)

