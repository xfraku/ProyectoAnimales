"""Compatibility helpers for callers of the previous version."""
from domain import email_address
from settings import AppError


def es_correo_valido(correo):
    try:
        email_address(correo)
        return True
    except AppError:
        return False
