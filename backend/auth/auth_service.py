import time
from flask import session
from backend.auth.user_model import user_repository, User

class AuthService:
    """Authentication business logic and session state management."""

    @staticmethod
    def authenticate(username: str, password: str) -> tuple[User | None, str | None]:
        """
        Validates credentials securely.
        Returns (User, None) on success or (None, generic_error) on failure.
        """
        if not username or not username.strip():
            return None, "Username is required."
        if not password or not password.strip():
            return None, "Password is required."

        user = user_repository.get_by_username(username.strip())
        if not user or not user.check_password(password):
            return None, "Invalid username or password."

        # Check account status
        if user.status != "ACTIVE":
            return None, "Account disabled."

        return user, None

    @staticmethod
    def create_session(user: User):
        """Establishes an authenticated secure session."""
        session.clear()
        session.permanent = True
        session["user_id"] = user.user_id
        session["username"] = user.username
        session["role"] = user.role.upper()
        session["display_name"] = user.display_name
        session["authenticated_at"] = int(time.time())

    @staticmethod
    def terminate_session():
        """Clears and invalidates the session."""
        session.clear()

    @staticmethod
    def is_authenticated() -> bool:
        """Checks if current session contains authenticated identity."""
        return "user_id" in session and "username" in session

    @staticmethod
    def get_current_user_info() -> dict | None:
        """Retrieves safe dictionary of current session user."""
        if not AuthService.is_authenticated():
            return None
        
        # Verify user still exists and is active
        user_id = session.get("user_id")
        user = user_repository.get_by_id(user_id) if user_id else None
        if not user or user.status != "ACTIVE":
            return None

        return {
            "id": user.user_id,
            "username": user.username,
            "role": user.role.upper(),
            "status": user.status,
            "display_name": user.display_name,
            "authenticated_at": session.get("authenticated_at")
        }
