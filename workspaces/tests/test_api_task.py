from django.urls import reverse
from django.contrib.auth import get_user_model

from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from rest_framework_simplejwt.tokens import RefreshToken

from workspaces.models import WorkSpace, Board, Column, Task

User = get_user_model()


class TaskTestCase(APITestCase):
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
        self.column1 = Column.objects.create(name='Column1', board=self.board, index=0)
        self.column2 = Column.objects.create(name='Column2', board=self.board, index=1)
        self.task1 = Task.objects.create(name='task1', index=0, column=self.column1)

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
        self.column3 = Column.objects.create(name='Column1 Board2', board=self.board2, index=0)
        self.task2 = Task.objects.create(name='task2', index=0, column=self.column3)
        self.task3 = Task.objects.create(name='task3', index=1, column=self.column3)

    def test_task_create(self):
        data = {'name': 'My Task'}
        response = self.client.post(reverse('task-list', kwargs={'column_id': self.column1.id}), data)
        self.assertEquals(status.HTTP_201_CREATED, response.status_code)
        self.assertEquals(2, len(Column.objects.get(pk=self.column1.id).task.all()))

    def test_task_create_else_board(self):
        data = {'name': 'My Task'}
        response = self.client.post(reverse('task-list', kwargs={'column_id': self.column3.id}), data)
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)
        self.assertEquals(2, len(Column.objects.get(pk=self.column3.id).task.all()))

    def test_index_task_create(self):
        expected_indexes = [(0,), (1,), (2,), (3,), (4,), (5,), (6,), (7,), (8,), (9,), (10,)]
        for i in range(10):
            data = {'name': 'My Task'}
            self.client.post(reverse('task-list', kwargs={'column_id': self.column1.id}), data)

        all_indexes = list(Task.objects.filter(column=self.column1).values_list('index'))
        self.assertEquals(expected_indexes, all_indexes)

    def test_get_task_list(self):
        client = APIClient()
        client.force_authenticate(self.user2)
        response = client.get(reverse('task-list', kwargs={'column_id': self.column3.id}))
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.assertEquals(2, len(response.data))

    def test_get_task_list_else_board(self):
        response = self.client.get(reverse('task-list', kwargs={'column_id': self.column3.id}))
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_get_task_list_not_exists_column(self):
        response = self.client.get(reverse('task-list', kwargs={'column_id': 65162}))
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_get_task(self):
        response = self.client.get(
            reverse('task-detail', kwargs={'column_id': self.column1.id, 'pk': self.task1.id})
        )
        self.assertEquals(status.HTTP_200_OK, response.status_code)

    def test_get_else_task(self):
        response = self.client.get(
            reverse('task-detail', kwargs={'column_id': self.column3.id, 'pk': self.task3.id})
        )
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_get_task_not_exists(self):
        response = self.client.get(
            reverse('task-detail', kwargs={'column_id': self.column1.id, 'pk': 65467869})
        )
        self.assertEquals(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_patch_task(self):
        data = {'name': 'Changed name'}
        response = self.client.patch(
            reverse('task-detail', kwargs={'column_id': self.column1.id, 'pk': self.task1.id}),
            data
        )
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.task1.refresh_from_db()
        self.assertEquals('Changed name', self.task1.name)

    def test_patch_task_shift_right(self):
        task2 = Task.objects.create(name='task2', index=1, column=self.column1)
        task3 = Task.objects.create(name='task3', index=2, column=self.column1)
        task4 = Task.objects.create(name='task4', index=3, column=self.column1)
        data = {'index': '2'}
        self.client.patch(
            reverse('task-detail', kwargs={'column_id': self.column1.id, 'pk': self.task1.id}),
            data
        )
        self.task1.refresh_from_db()
        task2.refresh_from_db()
        task3.refresh_from_db()
        task4.refresh_from_db()

        self.assertEquals(2, self.task1.index)
        self.assertEquals(0, task2.index)
        self.assertEquals(1, task3.index)
        self.assertEquals(3, task4.index)

    def test_patch_task_shift_left(self):
        task2 = Task.objects.create(name='task2', index=1, column=self.column1)
        task3 = Task.objects.create(name='task3', index=2, column=self.column1)
        task4 = Task.objects.create(name='task4', index=3, column=self.column1)
        data = {'index': '0'}
        self.client.patch(
            reverse('task-detail', kwargs={'column_id': self.column1.id, 'pk': task4.id}),
            data
        )
        self.task1.refresh_from_db()
        task2.refresh_from_db()
        task3.refresh_from_db()
        task4.refresh_from_db()

        self.assertEquals(1, self.task1.index)
        self.assertEquals(2, task2.index)
        self.assertEquals(3, task3.index)
        self.assertEquals(0, task4.index)

    def test_patch_task_invalid_index(self):
        data = {'index': -256}
        response = self.client.patch(
            reverse('task-detail', kwargs={'column_id': self.column1.id, 'pk': self.task1.id}),
            data
        )
        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)

        data = {'index': 2}
        response = self.client.patch(
            reverse('task-detail', kwargs={'column_id': self.column1.id, 'pk': self.task1.id}),
            data
        )
        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)

        data = {'index': 'A'}
        response = self.client.patch(
            reverse('task-detail', kwargs={'column_id': self.column1.id, 'pk': self.task1.id}),
            data
        )
        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_patch_else_task(self):
        data = {'name': 'Changed name'}
        response = self.client.patch(
            reverse('task-detail', kwargs={'column_id': self.column3.id, 'pk': self.task3.id}),
            data
        )
        self.assertEquals(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_patch_not_exists_task(self):
        data = {'name': 'Changed name'}
        response = self.client.patch(
            reverse('task-detail', kwargs={'column_id': self.column1.id, 'pk': 46872}),
            data
        )
        self.assertEquals(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_put_task(self):
        task2 = Task.objects.create(name='task2', index=1, column=self.column1)
        data = {
            'name': 'Changed name',
            'index': 1,
            'column': self.column1.id,
            'responsible': [],
        }
        response = self.client.put(
            reverse('task-detail', kwargs={'column_id': self.column1.id, 'pk': self.task1.id}),
            data
        )
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.task1.refresh_from_db()
        task2.refresh_from_db()
        self.assertEquals('Changed name', self.task1.name)
        self.assertEquals(1, self.task1.index)
        self.assertEquals(0, task2.index)

    def test_delete_task(self):
        task2 = Task.objects.create(name='task2', index=1, column=self.column1)
        task3 = Task.objects.create(name='task3', index=2, column=self.column1)

        response = self.client.delete(
            reverse('task-detail', kwargs={'column_id': self.column1.id, 'pk': self.task1.id}),
        )
        task2.refresh_from_db()
        task3.refresh_from_db()

        self.assertEquals(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertEquals(2, len(Column.objects.get(pk=self.column1.id).task.all()))
        self.assertEquals(0, task2.index)
        self.assertEquals(1, task3.index)

    def test_move_task_between_columns(self):
        data = {
            'index': 0,
            'name': self.task1.name,
            'column': self.column2.id,
            'responsible': [],
        }
        response = self.client.put(
            reverse('task-detail', kwargs={'column_id': self.column1.id, 'pk': self.task1.id}),
            data,
        )
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.assertEquals(0, len(Column.objects.get(pk=self.column1.id).task.all()))
        self.assertEquals(1, len(Column.objects.get(pk=self.column2.id).task.all()))

    def test_move_task_to_else_column(self):
        board = Board.objects.create(work_space=self.ws, name='Board2')
        col = Column.objects.create(name='Col', board=board, index=0)

        data = {
            'index': 0,
            'name': self.task1.name,
            'column': col.id,
        }
        response = self.client.put(
            reverse('task-detail', kwargs={'column_id': self.column1.id, 'pk': self.task1.id}),
            data,
        )
        self.assertEquals(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEquals(0, len(Column.objects.get(pk=col.id).task.all()))
        self.assertEquals(1, len(Column.objects.get(pk=self.column1.id).task.all()))

    def test_indexing_after_move_task(self):
        task2 = Task.objects.create(name='task2', index=0, column=self.column2)
        task3 = Task.objects.create(name='task3', index=1, column=self.column2)
        task4 = Task.objects.create(name='task4', index=2, column=self.column2)

        data = {
            'index': 0,
            'name': self.task1.name,
            'column': self.column2.id,
            'responsible': [],
        }
        response = self.client.put(
            reverse('task-detail', kwargs={'column_id': self.column1.id, 'pk': self.task1.id}),
            data,
        )
        self.assertEquals(status.HTTP_200_OK, response.status_code)
        self.assertEquals(0, len(Column.objects.get(pk=self.column1.id).task.all()))
        self.assertEquals(4, len(Column.objects.get(pk=self.column2.id).task.all()))

        self.task1.refresh_from_db()
        task2.refresh_from_db()
        task3.refresh_from_db()
        task4.refresh_from_db()

        self.assertEquals(1, task2.index)
        self.assertEquals(2, task3.index)
        self.assertEquals(3, task4.index)
