from django.contrib.auth.models import AbstractUser
from django.db import models

class StafUser(AbstractUser):
    """Custom user model for staff"""
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('manager', 'Manager'),
        ('programmer', 'Programmer'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='programmer')
    gitlab_username = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Staf'
        verbose_name_plural = 'Staf'

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"
