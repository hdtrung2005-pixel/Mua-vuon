"""
Base models dùng chung cho toàn hệ thống.
Mọi model nghiệp vụ nên kế thừa BaseModel để có sẵn created_at/updated_at,
tránh phải khai báo lại ở từng app.
"""
from django.db import models


class BaseModel(models.Model):
    """Abstract base model: tự động có created_at, updated_at."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
