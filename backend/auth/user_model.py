import os
import json
import uuid
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from backend.config import Config

VALID_ROLES = {"ADMIN", "ENGINEER", "OPERATOR", "VIEWER", "USER"}

class User:
    """Represents a system user with secure credential hashing and role-based access control."""
    def __init__(self, user_id: str, username: str, password_hash: str, role: str = "USER", status: str = "ACTIVE", display_name: str = "", created_at: str = None):
        self.user_id = user_id
        self.username = username
        self.password_hash = password_hash
        self.role = role.upper() if role.upper() in VALID_ROLES else "USER"
        self.status = status.upper()  # 'ACTIVE' or 'DISABLED'
        self.display_name = display_name or username
        self.created_at = created_at or datetime.datetime.utcnow().isoformat()

    def check_password(self, password: str) -> bool:
        """Verifies candidate plaintext password against stored secure hash."""
        if not password or not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def set_password(self, new_password: str):
        """Hashes and updates password using scrypt."""
        self.password_hash = generate_password_hash(new_password, method="scrypt")

    def to_safe_dict(self) -> dict:
        """Returns safe user representation without exposing sensitive hashes."""
        return {
            "id": self.user_id,
            "username": self.username,
            "role": self.role,
            "status": self.status,
            "display_name": self.display_name,
            "created_at": self.created_at
        }

    def to_storage_dict(self) -> dict:
        """Internal representation for persistent storage."""
        return {
            "id": self.user_id,
            "username": self.username,
            "password_hash": self.password_hash,
            "role": self.role,
            "status": self.status,
            "display_name": self.display_name,
            "created_at": self.created_at
        }


class UserRepository:
    """
    Manages user store with persistent storage and role-based safeguards.
    """
    DEFAULT_ACCOUNTS = [
        {
            "user_id": "usr_admin_01",
            "username": "admin",
            "password": "Admin@123",
            "role": "ADMIN",
            "status": "ACTIVE",
            "display_name": "System Administrator"
        },
        {
            "user_id": "usr_engineer_02",
            "username": "engineer",
            "password": "Engg@123",
            "role": "ENGINEER",
            "status": "ACTIVE",
            "display_name": "SCADA Engineer"
        },
        {
            "user_id": "usr_operator_03",
            "username": "operator",
            "password": "Oper@123",
            "role": "OPERATOR",
            "status": "ACTIVE",
            "display_name": "Substation Operator"
        },
        {
            "user_id": "usr_viewer_04",
            "username": "viewer",
            "password": "View@123",
            "role": "VIEWER",
            "status": "ACTIVE",
            "display_name": "Telemetry Viewer"
        }
    ]

    def __init__(self):
        self._users = {}  # keyed by lowercase username
        self._users_by_id = {}
        self._storage_path = os.environ.get("USERS_DB_PATH") or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "data", "users.json")
        )
        self._load_or_initialize()

    def _ensure_data_dir(self):
        directory = os.path.dirname(self._storage_path)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def _save_to_disk(self):
        """Persists user store to JSON safely."""
        try:
            self._ensure_data_dir()
            data = [u.to_storage_dict() for u in self._users_by_id.values()]
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            # In-memory remains active if disk write fails
            pass

    def _load_or_initialize(self):
        """Loads users from disk or initializes default accounts."""
        loaded = False
        if os.path.exists(self._storage_path):
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        for item in data:
                            user = User(
                                user_id=item["id"],
                                username=item["username"],
                                password_hash=item["password_hash"],
                                role=item.get("role", "USER"),
                                status=item.get("status", "ACTIVE"),
                                display_name=item.get("display_name", ""),
                                created_at=item.get("created_at")
                            )
                            self._users[user.username.lower()] = user
                            self._users_by_id[user.user_id] = user
                        loaded = True
            except Exception:
                loaded = False

        if not loaded:
            self._seed_default_accounts()
            return

        # Verification & Migration for existing data:
        modified = False
        # 1. Ensure at least one active admin
        admin = self.get_by_username("admin")
        if not admin or admin.role != "ADMIN" or admin.status != "ACTIVE":
            if not any(u.role == "ADMIN" and u.status == "ACTIVE" for u in self._users.values()):
                self._create_or_restore_admin()
                modified = True

        # 2. Check if admin still has the obsolete password hash for "SchneiderEMS@2026!"
        if admin and admin.check_password("SchneiderEMS@2026!"):
            admin.set_password("Admin@123")
            modified = True

        # 3. Ensure default authorized roles (engineer, operator, viewer) are present
        for acc in self.DEFAULT_ACCOUNTS:
            uname = acc["username"].lower()
            if uname not in self._users:
                u = User(
                    user_id=acc["user_id"],
                    username=acc["username"],
                    password_hash=generate_password_hash(acc["password"], method="scrypt"),
                    role=acc["role"],
                    status=acc["status"],
                    display_name=acc["display_name"]
                )
                self._users[uname] = u
                self._users_by_id[u.user_id] = u
                modified = True

        if modified:
            self._save_to_disk()

    def _seed_default_accounts(self):
        """Seeds initial authorized accounts securely."""
        self._users.clear()
        self._users_by_id.clear()

        for acc in self.DEFAULT_ACCOUNTS:
            pwd = Config.ADMIN_PASSWORD if acc["role"] == "ADMIN" else acc["password"]
            u = User(
                user_id=acc["user_id"],
                username=acc["username"],
                password_hash=generate_password_hash(pwd, method="scrypt"),
                role=acc["role"],
                status=acc["status"],
                display_name=acc["display_name"]
            )
            self._users[acc["username"].lower()] = u
            self._users_by_id[u.user_id] = u

        self._save_to_disk()

    def _create_or_restore_admin(self):
        """Initializes administrator account securely from configuration."""
        admin_username = Config.ADMIN_USERNAME
        admin_password = Config.ADMIN_PASSWORD
        
        admin_hash = generate_password_hash(admin_password, method="scrypt")
        admin_user = User(
            user_id="usr_admin_01",
            username=admin_username,
            password_hash=admin_hash,
            role="ADMIN",
            status="ACTIVE",
            display_name="System Administrator"
        )
        self._users[admin_username.lower()] = admin_user
        self._users_by_id[admin_user.user_id] = admin_user
        self._save_to_disk()

    def get_by_username(self, username: str) -> User | None:
        """Finds user by case-insensitive username."""
        if not username:
            return None
        return self._users.get(username.strip().lower())

    def get_by_id(self, user_id: str) -> User | None:
        """Finds user by user_id."""
        return self._users_by_id.get(user_id)

    def get_all(self) -> list[User]:
        """Returns all users."""
        return list(self._users_by_id.values())

    def count_active_admins(self) -> int:
        """Counts how many active ADMIN accounts exist."""
        return sum(1 for u in self._users_by_id.values() if u.role == "ADMIN" and u.status == "ACTIVE")

    def create_user(self, username: str, password: str, role: str = "USER", status: str = "ACTIVE") -> tuple[User | None, str | None]:
        """Creates a new user account with role validation."""
        username = username.strip()
        if not username:
            return None, "Username is required."
        if len(username) < 3:
            return None, "Username must be at least 3 characters long."
        if not password or len(password) < 6:
            return None, "Password must be at least 6 characters long."

        if username.lower() in self._users:
            return None, "A user with this username already exists."

        role = role.upper() if role.upper() in VALID_ROLES else "USER"
        status = "DISABLED" if status.upper() == "DISABLED" else "ACTIVE"

        user_id = f"usr_{uuid.uuid4().hex[:8]}"
        password_hash = generate_password_hash(password, method="scrypt")
        
        user = User(
            user_id=user_id,
            username=username,
            password_hash=password_hash,
            role=role,
            status=status,
            display_name=username
        )
        self._users[username.lower()] = user
        self._users_by_id[user_id] = user
        self._save_to_disk()
        return user, None

    def update_user(self, user_id: str, new_username: str, role: str, status: str) -> tuple[User | None, str | None]:
        """Updates user details with admin lockout prevention."""
        user = self.get_by_id(user_id)
        if not user:
            return None, "User not found."

        new_username = new_username.strip()
        if not new_username:
            return None, "Username cannot be empty."

        # Check duplicate username
        existing = self.get_by_username(new_username)
        if existing and existing.user_id != user_id:
            return None, "Another account already uses this username."

        role = role.upper() if role.upper() in VALID_ROLES else "USER"
        status = "DISABLED" if status.upper() == "DISABLED" else "ACTIVE"

        # Lockout check: if demoting or disabling the only active admin
        if user.role == "ADMIN" and user.status == "ACTIVE":
            if (role != "ADMIN" or status != "ACTIVE") and self.count_active_admins() <= 1:
                return None, "At least one active administrator account must remain available."

        # If username changed, update keys in dictionary
        old_username_key = user.username.lower()
        if old_username_key in self._users:
            del self._users[old_username_key]

        user.username = new_username
        user.display_name = new_username
        user.role = role
        user.status = status
        self._users[new_username.lower()] = user
        self._save_to_disk()
        return user, None

    def reset_password(self, user_id: str, new_password: str) -> tuple[bool, str | None]:
        """Updates user password hash."""
        user = self.get_by_id(user_id)
        if not user:
            return False, "User not found."
        if not new_password or len(new_password) < 6:
            return False, "Password must be at least 6 characters long."

        user.set_password(new_password)
        self._save_to_disk()
        return True, None

    def set_status(self, user_id: str, status: str) -> tuple[bool, str | None]:
        """Toggles or sets user status."""
        user = self.get_by_id(user_id)
        if not user:
            return False, "User not found."

        status = "DISABLED" if status.upper() == "DISABLED" else "ACTIVE"
        if user.role == "ADMIN" and user.status == "ACTIVE" and status == "DISABLED":
            if self.count_active_admins() <= 1:
                return False, "At least one active administrator account must remain available."

        user.status = status
        self._save_to_disk()
        return True, None

    def delete_user(self, user_id: str) -> tuple[bool, str | None]:
        """Deletes user with last-admin safeguard."""
        user = self.get_by_id(user_id)
        if not user:
            return False, "User not found."

        if user.role == "ADMIN" and self.count_active_admins() <= 1:
            return False, "At least one active administrator account must remain available."

        username_key = user.username.lower()
        if username_key in self._users:
            del self._users[username_key]
        if user_id in self._users_by_id:
            del self._users_by_id[user_id]

        self._save_to_disk()
        return True, None


# Singleton instance
user_repository = UserRepository()
