from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    APPROVER = "APPROVER", "Approver"
    FRANCHISE = "FRANCHISE", "Franchise"
    PARENT = "PARENT", "Parent"
    DRIVER = "DRIVER", "Driver"


class UserManager(BaseUserManager):
    def create_user(self, email: str, password: str | None = None, role: str = UserRole.PARENT, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, role=role, **extra_fields)
        user.set_password(password)
        user.is_active = extra_fields.get("is_active", True)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", UserRole.ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True, blank=True, null=True)
    full_name = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=20, choices=UserRole.choices)

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    # Legacy MySQL column names on `users` (nullable; separate from auth password column `password`).
    code = models.CharField(max_length=255, blank=True, null=True)
    active = models.CharField(max_length=10, blank=True, null=True)
    last_session = models.CharField(max_length=255, blank=True, null=True)
    blocked = models.CharField(max_length=10, blank=True, null=True)
    tries = models.IntegerField(blank=True, null=True)
    last_try = models.BigIntegerField(blank=True, null=True)
    mask_id = models.IntegerField(blank=True, null=True)
    group_id = models.IntegerField(blank=True, null=True)
    activation_time = models.BigIntegerField(blank=True, null=True)
    last_action = models.BigIntegerField(blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "users"

    def __str__(self) -> str:
        identifier = self.username or self.email
        return f"{identifier} ({self.role})"

    def normalized_role(self) -> str:
        """Uppercase role for comparisons (legacy imports used lowercase)."""
        return str(self.role or "").strip().upper()

    @property
    def is_admin(self) -> bool:
        return self.normalized_role() == UserRole.ADMIN.value

    @property
    def is_approver(self) -> bool:
        return self.normalized_role() == UserRole.APPROVER.value

    @property
    def is_franchise(self) -> bool:
        return self.normalized_role() == UserRole.FRANCHISE.value

    @property
    def is_parent(self) -> bool:
        return self.normalized_role() == UserRole.PARENT.value

    @property
    def is_driver(self) -> bool:
        return self.normalized_role() == UserRole.DRIVER.value
