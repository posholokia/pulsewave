from celery import shared_task

from workspaces.models import InvitedUsers


# @shared_task
# def delete_invited(pk):
#     invite = InvitedUsers.objects.filter(pk=pk).first()
#     if invite:
#         invite.delete()
