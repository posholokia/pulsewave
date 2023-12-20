from django.urls import reverse
from django.contrib.auth import get_user_model

from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from rest_framework_simplejwt.tokens import RefreshToken

from workspaces.models import WorkSpace, Board, Column

User = get_user_model()


class ColumnTestCase(APITestCase):
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
        self.column = Column.objects.create(name='Column1', board=self.board, index=0)

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
        self.column2 = Column.objects.create(name='Column1 Board2', board=self.board2, index=0)

    def test_column_create(self):
        data = {'name': 'My Column'}
        response = self.client.post(reverse('column-list', kwargs={'board_id': self.board.id}), data)
        self.assertEquals(status.HTTP_201_CREATED, response.status_code)
        self.assertEquals(2, len(Board.objects.get(pk=self.board.id).column_board.all()))

    def test_create_index_column(self):
        expected_indexes = [(0,), (1,), (2,), (3,), (4,), (5,), (6,), (7,), (8,), (9,), (10,)]
        for i in range(10):
            data = {'name': 'My Column'}
            self.client.post(reverse('column-list', kwargs={'board_id': self.board.id}), data)

        all_indexes = list(Column.objects.filter(board=self.board).values_list('index'))
        self.assertEquals(expected_indexes, all_indexes)

    def test_get_column_list(self):
        response = self.client.get(reverse('column-list', kwargs={'board_id': self.board.id}))
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.assertEquals(1, len(response.data))

    def test_get_column_list_else_board(self):
        response = self.client.get(reverse('column-list', kwargs={'board_id': self.board2.id}))
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_get_column_list_not_exists_board(self):
        response = self.client.get(reverse('column-list', kwargs={'board_id': 65162}))
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_get_column(self):
        response = self.client.get(
            reverse('column-detail', kwargs={'board_id': self.board.id, 'pk': self.column.id})
        )
        self.assertEquals(status.HTTP_200_OK, response.status_code)

    def test_get_else_column(self):
        response = self.client.get(
            reverse('column-detail', kwargs={'board_id': self.board2.id, 'pk': self.column2.id})
        )
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_get_column_not_exists(self):
        response = self.client.get(
            reverse('column-detail', kwargs={'board_id': self.board.id, 'pk': 65467869})
        )
        self.assertEquals(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_patch_column(self):
        data = {'name': 'Changed name'}
        response = self.client.patch(
            reverse('column-detail', kwargs={'board_id': self.board.id, 'pk': self.column.id}),
            data
        )
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.column.refresh_from_db()
        self.assertEquals('Changed name', self.column.name)

    def test_patch_column_shift_right(self):
        col2 = Column.objects.create(name='Column2', board=self.board, index=1)
        col3 = Column.objects.create(name='Column3', board=self.board, index=2)
        col4 = Column.objects.create(name='Column4', board=self.board, index=3)
        data = {'index': '2'}
        self.client.patch(
            reverse('column-detail', kwargs={'board_id': self.board.id, 'pk': self.column.id}),
            data
        )
        self.column.refresh_from_db()
        col2.refresh_from_db()
        col3.refresh_from_db()
        col4.refresh_from_db()

        self.assertEquals(2, self.column.index)
        self.assertEquals(0, col2.index)
        self.assertEquals(1, col3.index)
        self.assertEquals(3, col4.index)

    def test_patch_column_shift_left(self):
        col2 = Column.objects.create(name='Column2', board=self.board, index=1)
        col3 = Column.objects.create(name='Column3', board=self.board, index=2)
        col4 = Column.objects.create(name='Column4', board=self.board, index=3)
        data = {'index': '0'}
        self.client.patch(
            reverse('column-detail', kwargs={'board_id': self.board.id, 'pk': col4.id}),
            data
        )
        self.column.refresh_from_db()
        col2.refresh_from_db()
        col3.refresh_from_db()
        col4.refresh_from_db()

        self.assertEquals(1, self.column.index)
        self.assertEquals(2, col2.index)
        self.assertEquals(3, col3.index)
        self.assertEquals(0, col4.index)

    def test_patch_column_invalid_index(self):
        data = {'index': -256}
        response = self.client.patch(
            reverse('column-detail', kwargs={'board_id': self.board.id, 'pk': self.column.id}),
            data
        )
        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)

        data = {'index': 2}
        response = self.client.patch(
            reverse('column-detail', kwargs={'board_id': self.board.id, 'pk': self.column.id}),
            data
        )
        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)

        data = {'index': 'A'}
        response = self.client.patch(
            reverse('column-detail', kwargs={'board_id': self.board.id, 'pk': self.column.id}),
            data
        )
        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_patch_else_column(self):
        data = {'name': 'Changed name'}
        response = self.client.patch(
            reverse('column-detail', kwargs={'board_id': self.board2.id, 'pk': self.column2.id}),
            data
        )
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_patch_not_exists_column(self):
        data = {'name': 'Changed name'}
        response = self.client.patch(
            reverse('column-detail', kwargs={'board_id': self.board.id, 'pk': 46872}),
            data
        )
        self.assertEquals(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_put_column(self):
        col = Column.objects.create(name='Column2', board=self.board, index=1)
        data = {
            'name': 'Changed name',
            'index': 1,
        }
        response = self.client.put(
            reverse('column-detail', kwargs={'board_id': self.board.id, 'pk': self.column.id}),
            data
        )
        print(f'\n\n{response.json()=}\n\n')
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.column.refresh_from_db()
        col.refresh_from_db()
        self.assertEquals('Changed name', self.column.name)
        self.assertEquals(1, self.column.index)
        self.assertEquals(0, col.index)

    def test_delete_column(self):
        col2 = Column.objects.create(name='Column2', board=self.board, index=1)
        col3 = Column.objects.create(name='Column3', board=self.board, index=2)

        response = self.client.delete(
            reverse('column-detail', kwargs={'board_id': self.board.id, 'pk': self.column.id}),
        )
        col2.refresh_from_db()
        col3.refresh_from_db()

        self.assertEquals(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertEquals(2, len(Board.objects.get(pk=self.board.id).column_board.all()))
        self.assertEquals(0, col2.index)
        self.assertEquals(1, col3.index)
