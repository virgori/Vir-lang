"""W-IR lowering passes."""

from src.wir.lower.h_to_m import lower_h_to_m
from src.wir.lower.m_to_l import lower_m_to_l

__all__ = ["lower_h_to_m", "lower_m_to_l"]
