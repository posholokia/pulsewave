"""
Этот файл содержит дополнения и исправления схемы генерации OpenAPI
документации библиотеки drf-spectacular.
"""

from drf_spectacular.extensions import OpenApiViewExtension
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiTypes

from workspaces import serializers


class Fix1(OpenApiViewExtension):
    target_class = 'workspaces.views.UserList'

    def view_replacement(self):
        class Fixed(self.target_class):
            """Список всех пользователей для поиска.\n\n
               Поиск ведется по почте, начало передается через query параметр users.\n\n
               Например: /api/user_list/?users=foobar\n\n
               Можно передать дополнительный параметр workspace для исклчения юзеров, уже
               приглашенных/присутствующих в этом РП: /api/user_list/?users=foo&workspace=17"""
            @extend_schema(parameters=[
                OpenApiParameter("users", OpenApiTypes.STR),
                OpenApiParameter("workspace", OpenApiTypes.INT),
            ])
            def get(self, request, *args, **kwargs):
                return super().get(request, *args, **kwargs)

        return Fixed


class Fix2(OpenApiViewExtension):
    target_class = 'workspaces.views.BoardCreateWithoutWorkSpace'

    def view_replacement(self):
        class Fixed(self.target_class):
            """Создание доски без указания РП, будет создано дефолтное РП для этой доски"""
            pass

        return Fixed


class Fix3(OpenApiViewExtension):
    target_class = 'workspaces.views.TaskViewSet'

    def view_replacement(self):
        @extend_schema_view(list=extend_schema(description='Список всех задач колонки.'),
                            create=extend_schema(
                                description='Создать задачу\n\n'
                                            'responsible: Список ответсвенны пользователей. Передается массивом из id,'
                                            'например {"responsible": [1,2,3]}\n\n'
                                            'deadline: Срок выполнения задачи\n\n'
                                            'description: Описание\n\n'
                                            'priority: Приоритет, число от 0 до 3, где 0 - высочайший приоритет\n\n'
                                            'color_mark: Цвет метки\n\n'
                                            'name_mark: Название метки', ),
                            retrieve=extend_schema(description='Информация о конкретной задаче'),
                            update=extend_schema(
                                description='Обновить задачу.\n\n'
                                            'Для преремещения между колонок нужно передать column - id новой '
                                            'колонки и index - куда ее вставить.'
                            ),
                            partial_update=extend_schema(
                                description='Частично обновить задачу.\n\n'
                                            'Перемещение между колонками возможно только PUT запросом'
                            ),
                            destroy=extend_schema(description='Удалить задачу'),
                            )
        class Fixed(self.target_class):
            """Создание доски без указания РП, будет создано дефолтное РП для этой доски"""
            pass

        return Fixed
