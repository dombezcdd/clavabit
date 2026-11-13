# -*- coding: utf-8 -*-
"""Общий логгер бота."""
import logging

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s",
                    level=logging.WARNING)
log = logging.getLogger("bot")
