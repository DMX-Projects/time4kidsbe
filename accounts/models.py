from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    APPROVER = "APPROVER", "Approver"
    CRM = "CRM", "CRM"
    FRANCHISE = "FRANCHISE", "Franchise"
    PARENT = "PARENT", "Parent"
    DRIVER = "DRIVER", "Driver"


class CrmZone(models.TextChoices):
    EAST = "EAST", "East"
    WEST = "WEST", "West"
    NORTH = "NORTH", "North"
    SOUTH = "SOUTH", "South"


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
    # Blank = national CRM (all zones). EAST/WEST/NORTH/SOUTH restricts leads & reports.
    crm_zone = models.CharField(
        max_length=10,
        choices=CrmZone.choices,
        blank=True,
        default="",
        help_text="CRM only: blank = all India; otherwise only that zone's states/cities/centres.",
    )
    # Blank = full zone (or national). NORTH_R1 / SOUTH_R2 / etc. narrows to a region inside the zone.
    crm_region = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="CRM only: blank = full zone/national; otherwise a region code (e.g. NORTH_R1).",
    )

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

    def check_password(self, raw_password):
        """
        Plaintext / ``plain$...`` values are not valid Django "encoded" strings when
        there is no ``$`` (bare password): ``identify_hasher`` treats the whole string
        as an algorithm name and ``check_password`` never runs our hasher. Handle
        those rows here, then delegate for normal hashed passwords.
        """
        from users.hashers import PlaintextPasswordHasher

        def setter(pw: str) -> None:
            self.set_password(pw)
            self._password = None
            self.save(update_fields=["password"])

        encoded = self.password
        hasher = PlaintextPasswordHasher()
        if encoded is not None and hasher.identify(encoded):
            ok = hasher.verify(raw_password or "", encoded)
            if ok and hasher.must_update(encoded):
                setter(raw_password or "")
            return ok
        return super().check_password(raw_password)

    async def acheck_password(self, raw_password):
        from users.hashers import PlaintextPasswordHasher

        encoded = self.password
        hasher = PlaintextPasswordHasher()
        if encoded is not None and hasher.identify(encoded):
            ok = hasher.verify(raw_password or "", encoded)
            if ok and hasher.must_update(encoded):
                self.set_password(raw_password or "")
                self._password = None
                await self.asave(update_fields=["password"])
            return ok
        return await super().acheck_password(raw_password)

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
    def is_crm(self) -> bool:
        return self.normalized_role() == UserRole.CRM.value

    @property
    def is_franchise(self) -> bool:
        return self.normalized_role() == UserRole.FRANCHISE.value

    @property
    def is_parent(self) -> bool:
        return self.normalized_role() == UserRole.PARENT.value

    @property
    def is_driver(self) -> bool:
        return self.normalized_role() == UserRole.DRIVER.value


class ParentRegistration(models.Model):
    """
    Parent sign-up from /login/register/ (separate from admission ``enquiry`` leads).
    """

    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_PROGRESS = "in-progress", "In Progress"
        CLOSED = "closed", "Closed"

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registration_records",
    )
    parent_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(
        max_length=10,
        blank=True,
        validators=[RegexValidator(r"^\d{10}$", "Phone number must be exactly 10 digits.")],
    )
    child_name = models.CharField(max_length=255, blank=True)
    child_age = models.CharField(max_length=50, blank=True)
    program = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    franchise = models.ForeignKey(
        "franchises.Franchise",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parent_registrations",
    )
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "parent_registration"
        ordering = ["-created_at"]
        verbose_name = "Parent registration"
        verbose_name_plural = "Parent registrations"

    def __str__(self) -> str:
        return f"Registration: {self.parent_name} ({self.email})"
