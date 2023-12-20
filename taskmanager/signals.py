from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .tasks import delete_inactive_user

User = get_user_model()


@receiver(post_save, sender=User)
def delete_user_task(sender, instance, **kwargs):
    delete_inactive_user.apply_async((instance.id,), countdown=24*60*60)
