# -*- coding: utf-8 -*-
"""Обложка «Сотрудничество»: готовая картинка assets/coop.jpg."""

import io
import os


def coop_card():
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "coop.jpg")
    return io.BytesIO(open(p, "rb").read())
