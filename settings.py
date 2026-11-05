"""Configuration shared by Streamlit, command line tests and services."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def setting(name, default=None):
    if name in os.environ:
        return os.environ[name]
    import streamlit as st
    try:
        return st.secrets.get(name, default)
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return default


class AppError(Exception):
    """An actionable, non-sensitive message suitable for the interface."""


class AccessError(AppError):
    pass
