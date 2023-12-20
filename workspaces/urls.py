from django.urls import path
from workspaces.views import UserList, WorkSpaceViewSet, TestSSEMessage, TestSSEUser, BoardViewSet, ColumnViewSet, \
    BoardCreateWithoutWorkSpace, TaskViewSet
from rest_framework import routers

router = routers.DefaultRouter()
router.register('workspace', WorkSpaceViewSet, basename='workspace')
router.register(r'workspace/(?P<workspace_id>\d+)/boards', BoardViewSet, basename='boards')
router.register(r'boards/(?P<board_id>\d+)/column', ColumnViewSet, basename='column')
router.register(r'column/(?P<column_id>\d+)/task', TaskViewSet, basename='task')


urlpatterns = [
    path('user_list/', UserList.as_view(), name='search_user'),
    path('board_create/', BoardCreateWithoutWorkSpace.as_view(), name='out_ws_create_board'),
    path('sse_random_string/', TestSSEMessage.as_view()),
    path('sse_user/', TestSSEUser.as_view()),
]

urlpatterns += router.urls
