"""
Auth utils for TIDAL.
"""

from tidalapi import Session

from tidal_playlist_mixer.config import UserConfig


class TidalAuth:
    """
    Helper utility for TIDAL auth.
    """

    @classmethod
    def login(cls: type, fn_print=print) -> Session:
        """
        Run interactive OAuth login and return a logged in session.
        """
        session = Session()
        session.login_oauth_simple(fn_print=fn_print)
        if not session.check_login():
            raise RuntimeError("Failed to login to TIDAL")
        return session

    @classmethod
    def get_session(cls: type) -> Session:
        """
        Get a TIDAL session from stored user credentials.
        """
        user_config = UserConfig.load_user_config()
        if not user_config:
            raise RuntimeError("No user config found. Please login first")

        session = Session()
        ok = session.load_oauth_session(
            token_type=user_config.token_type,
            access_token=user_config.access_token,
            refresh_token=user_config.refresh_token,
            expiry_time=user_config.expiry_time,
        )
        if not ok or not session.check_login():
            raise RuntimeError("Failed to restore TIDAL session. Please login again")
        return session

    @classmethod
    def user_config_from_session(cls: type, session: Session) -> UserConfig:
        """
        Build persisted user config from the active session.
        """
        if session.user is None or session.user.id is None:
            raise RuntimeError("No logged in TIDAL user found")

        return UserConfig(
            user_id=session.user.id,
            token_type=session.token_type,
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            expiry_time=session.expiry_time,
        )
