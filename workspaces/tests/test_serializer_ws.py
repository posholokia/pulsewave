from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import crypto

from rest_framework.test import APITestCase, APIClient

from rest_framework_simplejwt.tokens import RefreshToken, AccessToken

from workspaces.models import WorkSpace, InvitedUsers, Board
from workspaces.serializers import WorkSpaceSerializer, InviteUserSerializer, UserListSerializer

User = get_user_model()


class WorkSpaceSerializersTestCase(APITestCase):
    def setUp(self):
        user_data = {
            'email': 'user1@example.com',
            'password': 'Pass!234',
            'is_active': True,
        }

        self.user = User.objects.create_user(**user_data)
        user_token = RefreshToken.for_user(self.user).access_token
        user_data['email'] = 'test-user2@example.com'
        self.user2 = User.objects.create_user(**user_data)
        user_data['email'] = 'user3@example.com'
        self.user3 = User.objects.create_user(**user_data)

        self.ws1 = WorkSpace.objects.create(owner=self.user, name='User1 WorkSpace1')
        self.ws1.users.add(self.user)
        self.ws1.invited.add(self.user2)
        self.board = Board.objects.create(name='test board', work_space=self.ws1)
        self.board.members.add(self.user)
        self.ws2 = WorkSpace.objects.create(owner=self.user, name='User1 WorkSpace2')
        self.ws2.users.add(self.user)
        ws3 = WorkSpace.objects.create(owner=self.user2, name='User2 WorkSpace1')
        ws3.users.add(self.user2)
        ws4 = WorkSpace.objects.create(owner=self.user2, name='User2 WorkSpace2')
        ws4.users.add(self.user2)

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'JWT {user_token}')

        self.EXAMPLE_WS = {
            'id': self.ws1.id,
            'name': 'User1 WorkSpace1',
            'users': [{
                'id': self.user.id,
                'email': 'user1@example.com',
                'name': '',
                'represent_name': 'user1',
                'avatar': None,
                'role': 'Owner',
            }],
            'invited': [{
                'id': self.user2.id,
                'email': 'test-user2@example.com',
                'name': '',
                'represent_name': 'test-user2',
                'avatar': None,
                'role': 'Invited',

            }],
            'boards': [{
                'id': self.board.id,
                'name': 'test board',
            }]
        }

        self.no_auth_client = APIClient()

        self.token = crypto.get_random_string(length=32)
        InvitedUsers.objects.create(user=self.user2, workspace=self.ws1, token=self.token)

    def test_ws_create(self):
        data = {
            'name': 'My WorkSpace'
        }
        response = self.client.post(reverse('workspace-list'), data).data
        self.assertEquals(3, len(response))
        self.assertEquals(WorkSpaceSerializer(WorkSpace.objects.filter(users=self.user), many=True).data, response)
        self.assertIn(self.EXAMPLE_WS, response)

    def test_ws_get_list(self):
        response = self.client.get(reverse('workspace-list')).data

        self.assertEquals(2, len(response))
        self.assertEquals(WorkSpaceSerializer(WorkSpace.objects.filter(users=self.user), many=True).data, response)

        self.assertIn(self.EXAMPLE_WS, response)

    def test_get_ws(self):
        response = self.client.get(reverse('workspace-detail', kwargs={'pk': self.ws1.id})).data

        self.assertEquals(WorkSpaceSerializer(WorkSpace.objects.get(pk=self.ws1.id)).data, response)
        self.assertEquals(self.EXAMPLE_WS, response)

    def test_patch_ws(self):
        data = {
            'name': 'Changed name',
        }
        response = self.client.patch(reverse('workspace-detail', kwargs={'pk': self.ws1.id}), data=data).data

        self.EXAMPLE_WS['name'] = 'Changed name'
        self.assertEquals(self.EXAMPLE_WS, response)

    def test_put_ws(self):
        data = {
            'name': 'Changed name',
        }
        response = self.client.put(reverse('workspace-detail', kwargs={'pk': self.ws1.id}), data=data).data

        self.EXAMPLE_WS['name'] = 'Changed name'
        self.assertEquals(self.EXAMPLE_WS, response)

    def test_delete_ws(self):
        response = self.client.delete(reverse('workspace-detail', kwargs={'pk': self.ws1.id})).data

        self.assertEquals(None, response)

    def test_invite_exists_user(self):
        data = {
            'email': 'user3@example.com',
        }
        new_user = {'id': self.user3.id,
                    'email': 'user3@example.com',
                    'name': '',
                    'represent_name': 'user3',
                    'avatar': None,
                    'role': 'Invited', }

        response = self.client.post(reverse('workspace-invite_user', kwargs={'pk': self.ws1.id}), data).data
        self.assertEquals(WorkSpaceSerializer(self.ws1).data, response)
        self.assertIn(new_user, response['invited'])

    def test_invite_new_user(self):
        data = {
            'email': 'new_user@example.com',
        }
        response = self.client.post(reverse('workspace-invite_user', kwargs={'pk': self.ws1.id}), data).data

        new_user = User.objects.get(email='new_user@example.com')
        user = {'id': new_user.id,
                'email': 'new_user@example.com',
                'name': '',
                'represent_name': 'new_user',
                'avatar': None,
                'role': 'Invited', }

        self.assertEquals(WorkSpaceSerializer(self.ws1).data, response)
        self.assertIn(user, response['invited'])

    def test_confirm_invite_exists_user(self):
        token = crypto.get_random_string(length=32)
        InvitedUsers.objects.create(user=self.user2, workspace=self.ws1, token=token)

        response = self.client.post(reverse('workspace-confirm_invite'), {'token': token}).data

        self.assertEquals(None, response)

    def test_confirm_invite_new_user(self):
        inactive_user = {
            'email': 'invited-user@example.com',
            'is_active': False,
        }
        invited_user = User.objects.create_user(**inactive_user)
        self.ws1.invited.add(invited_user)

        token = crypto.get_random_string(length=32)
        InvitedUsers.objects.create(user=invited_user, workspace=self.ws1, token=token)

        response = self.no_auth_client.post(reverse('workspace-confirm_invite'), {'token': token}).data

        invitation_data = {'token': token,
                           'user': 'invited-user@example.com',
                           'workspace': self.ws1.id}
        self.assertEquals(InviteUserSerializer(InvitedUsers.objects.get(token=token)).data, response)
        self.assertEquals(invitation_data, response)

    def test_kick_user(self):
        data = {'user_id': self.user2.id, }
        response = self.client.post(reverse('workspace-kick_user', kwargs={'pk': self.ws1.id}), data).data
        self.EXAMPLE_WS['invited'] = []

        self.assertEquals(WorkSpaceSerializer(self.ws1).data, response)
        self.assertEquals(self.EXAMPLE_WS, response)

    def test_resend_invite(self):
        invite_data = {'email': 'test-user2@example.com', }
        self.client.post(reverse('workspace-invite_user', kwargs={'pk': self.ws1.id}), invite_data)

        data = {'user_id': self.user2.id, }
        response = self.client.post(reverse('workspace-resend_invite', kwargs={'pk': self.ws1.id}), data).data

        self.assertEquals(None, response)

    def test_search_user(self):
        response = self.client.get(reverse('search_user'), data={'users': 'tes', 'workspace': self.ws1.id})

        found_users = {
            'id': self.user2.id,
            'name': 'test-user2',
            'email': 'test-user2@example.com',
            'added': False,
            'invited': True,
        }

        view = response.renderer_context['view']

        self.assertEquals(UserListSerializer(instance=self.user2, context={'view': view}).data, *response.data)
        self.assertEquals(found_users, *response.data)

    def test_reset_password_invited(self):
        inactive_user = {
            'email': 'invited-user@example.com',
            'is_active': False,
        }
        invited_user = User.objects.create_user(**inactive_user)
        self.ws1.invited.add(invited_user)

        token = crypto.get_random_string(length=32)
        InvitedUsers.objects.create(user=invited_user, workspace=self.ws1, token=token)

        data = {
            'new_password': 'Pass!234',
            're_new_password': 'Pass!234',
            'token': token,
        }

        response = self.no_auth_client.post(reverse('users-reset_password_invited'), data)
        access = response.data['access']
        refresh = response.data['refresh']

        self.assertEquals(invited_user.id, AccessToken(token=access)['user_id'])
        self.assertEquals(invited_user.id, RefreshToken(token=refresh)['user_id'])
