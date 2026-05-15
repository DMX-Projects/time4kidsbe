"""
Single password hasher: passwords in PostgreSQL as ``plain$<password>``.

Also accepts **bare** passwords in the column (no ``plain$`` prefix), e.g. values
pasted directly in pgAdmin — so ``flmlogin123`` in ``users.password`` still verifies.
Django's global ``check_password()`` cannot identify bare strings (no ``$``), so
``accounts.models.User.check_password`` routes those to this hasher before falling
back to Django defaults. After a successful login, bare values are re-saved as
``plain$...`` (see ``must_update``).

**Insecure** — anyone with DB read access sees real passwords.
"""

from __future__ import annotations

from django.contrib.auth.hashers import BasePasswordHasher
from django.utils.crypto import constant_time_compare


def _norm_encoded(encoded: str | None) -> str:
    return str(encoded or "").strip()


class PlaintextPasswordHasher(BasePasswordHasher):
    """Encode ``plain$<secret>``; verify that or a bare literal stored in ``password``."""

    algorithm = "plain"

    def encode(self, password: str, salt: str | None = None) -> str:
        return f"{self.algorithm}${password}"

    def identify(self, encoded: str) -> bool:
        es = _norm_encoded(encoded)
        if not es:
            return False
        if es.startswith(f"{self.algorithm}$"):
            return True
        if "$" not in es:
            return True
        return False

    def verify(self, password: str, encoded: str) -> bool:
        es = _norm_encoded(encoded)
        if not es:
            return False
        if es.startswith(f"{self.algorithm}$"):
            try:
                _algo, stored = es.split("$", 1)
            except ValueError:
                return False
            return constant_time_compare(password, stored)
        if "$" not in es:
            return constant_time_compare(password, es)
        return False

    def must_update(self, encoded: str) -> bool:
        es = _norm_encoded(encoded)
        if not es:
            return False
        return not es.startswith(f"{self.algorithm}$")

    def safe_summary(self, encoded: str) -> list[tuple[str, str]]:
        return [("algorithm", self.algorithm), ("password", "********************")]

    def decode(self, encoded: str) -> dict:
        es = _norm_encoded(encoded)
        if es.startswith(f"{self.algorithm}$"):
            algorithm, secret = es.split("$", 1)
            if algorithm != self.algorithm:
                raise ValueError("Unknown algorithm")
            return {"algorithm": algorithm, "hash": secret, "salt": None}
        if "$" not in es:
            return {"algorithm": self.algorithm, "hash": es, "salt": None}
        raise ValueError("Unknown password encoding")
