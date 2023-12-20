from django.urls import reverse
from django.contrib.auth import get_user_model

from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from rest_framework_simplejwt.tokens import RefreshToken

from workspaces.models import WorkSpace, Board

User = get_user_model()


class BoardTestCase(APITestCase):
    def setUp(self):
        user_data = {
            'email': 'user1@example.com',
            'password': 'Pass!234',
            'is_active': True,
        }
        self.user = User.objects.create_user(**user_data)
        user_token = RefreshToken.for_user(self.user).access_token

        self.ws = WorkSpace.objects.create(owner=self.user, name='WorkSpace1')
        self.ws.users.add(self.user)
        self.board = Board.objects.create(work_space=self.ws, name='Board1')

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'JWT {user_token}')

        user_data2 = {
            'email': 'user2@example.com',
            'password': 'Pass!234',
            'is_active': True,
        }
        self.user2 = User.objects.create_user(**user_data2)
        self.ws2 = WorkSpace.objects.create(owner=self.user, name='WorkSpace2')
        self.ws2.users.add(self.user2)
        self.board2 = Board.objects.create(work_space=self.ws2, name='Board1 WS2')

    def test_board_create(self):
        data = {'name': 'My Board'}
        response = self.client.post(reverse('boards-list', kwargs={'workspace_id': self.ws.id}), data)
        self.assertEquals(status.HTTP_201_CREATED, response.status_code)
        self.assertEquals(2, len(WorkSpace.objects.get(pk=self.ws.id).board.all()))

    def test_denied_board_create(self):
        data = {'name': 'My Board'}
        client = APIClient()
        client.force_authenticate(self.user2)

        response = client.post(reverse('boards-list', kwargs={'workspace_id': self.ws.id}), data)
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)
        self.assertEquals(1, len(WorkSpace.objects.get(pk=self.ws.id).board.all()))

    def test_board_create_not_exists_ws(self):
        data = {'name': 'My Board'}
        client = APIClient()
        client.force_authenticate(self.user2)

        response = client.post(reverse('boards-list', kwargs={'workspace_id': 654879}), data)
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_board_create_else_ws(self):
        data = {'name': 'My Board'}

        response = self.client.post(reverse('boards-list', kwargs={'workspace_id': self.ws2.id}), data)
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_create_board_no_ws(self):
        data = {
            'name': 'My Board'
        }
        response = self.client.post(reverse('out_ws_create_board'), data)
        self.assertEquals(status.HTTP_201_CREATED, response.status_code)
        self.assertEquals(1, len(WorkSpace.objects.get(pk=self.ws.id).board.all()))

        new_ws_id = response.data["work_space"]
        assert WorkSpace.objects.filter(pk=new_ws_id).exists()
        self.assertNotEqual(new_ws_id, self.ws.id)

    def test_board_create_fail_name(self):
        data = {
            'name': 'My Board name is very, very long, longer than necessary'
        }

        response = self.client.post(reverse('boards-list', kwargs={'workspace_id': self.ws.id}), data)
        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)
        error_code = response.data['name'][0].code
        self.assertEquals('max_length', error_code)

    def test_board_get_list(self):
        response = self.client.get(reverse('boards-list', kwargs={'workspace_id': self.ws.id}))
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.assertEquals(1, len(response.data))

    def test_get_board_list_else_ws(self):
        response = self.client.get(reverse('boards-list', kwargs={'workspace_id': self.ws2.id}))
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_get_board_list_no_wxists_ws(self):
        response = self.client.get(reverse('boards-list', kwargs={'workspace_id': 65419815}))
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_get_board(self):
        response = self.client.get(
            reverse('boards-detail', kwargs={'workspace_id': self.ws.id, 'pk': self.board.id}),
        )
        self.assertEquals(status.HTTP_200_OK, response.status_code)

    def test_get_not_exists_board(self):
        response = self.client.get(
            reverse('boards-detail', kwargs={'workspace_id': self.ws.id, 'pk': 1894541}),
        )
        self.assertEquals(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_get_not_exists_board_else_ws(self):
        response = self.client.get(
            reverse('boards-detail', kwargs={'workspace_id': self.ws2.id, 'pk': 1894541}),
        )
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_get_else_board(self):
        response = self.client.get(
            reverse('boards-detail', kwargs={'workspace_id': self.ws2.id, 'pk': self.board2.id}),
        )
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_patch_board(self):
        data = {
            'name': 'Changed name',
        }
        response = self.client.patch(
            reverse('boards-detail', kwargs={'workspace_id': self.ws.id, 'pk': self.board.id}),
            data=data,
        )
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.board.refresh_from_db()
        self.assertEquals('Changed name', self.board.name)

    def test_patch_not_exists_board(self):
        data = {
            'name': 'Changed name',
        }
        response = self.client.patch(
            reverse('boards-detail', kwargs={'workspace_id': self.ws.id, 'pk': self.board2.id}),
            data=data,
        )
        self.assertEquals(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_patch_else_board(self):
        data = {
            'name': 'Changed name',
        }
        response = self.client.patch(
            reverse('boards-detail', kwargs={'workspace_id': self.ws2.id, 'pk': self.board2.id}),
            data=data,
        )
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_put_board(self):
        data = {
            'name': 'Changed name',
        }
        response = self.client.put(
            reverse('boards-detail', kwargs={'workspace_id': self.ws.id, 'pk': self.board.id}),
            data=data,
        )
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.board.refresh_from_db()
        self.assertEquals('Changed name', self.board.name)

    def test_put_not_exists_board(self):
        data = {
            'name': 'Changed name',
        }
        response = self.client.put(
            reverse('boards-detail', kwargs={'workspace_id': self.ws.id, 'pk': self.board2.id}),
            data=data,
        )
        self.assertEquals(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_put_else_board(self):
        data = {
            'name': 'Changed name',
        }
        response = self.client.put(
            reverse('boards-detail', kwargs={'workspace_id': self.ws2.id, 'pk': self.board2.id}),
            data=data,
        )
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_delete_board(self):
        response = self.client.delete(
            reverse('boards-detail', kwargs={'workspace_id': self.ws.id, 'pk': self.board.id}),
        )
        self.assertEquals(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertEquals(0, len(self.user.joined_workspaces.get(pk=self.ws.id).board.all()))

    def test_delete_else_board(self):
        response = self.client.delete(
            reverse('boards-detail', kwargs={'workspace_id': self.ws2.id, 'pk': self.board2.id}),
        )
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_delete_not_exists_board(self):
        response = self.client.delete(
            reverse('boards-detail', kwargs={'workspace_id': self.ws.id, 'pk': 6594616}),
        )
        self.assertEquals(status.HTTP_404_NOT_FOUND, response.status_code)