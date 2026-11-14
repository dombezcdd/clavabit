# -*- coding: utf-8 -*-
"""Точка входа: python bot.py (или python main.py). Вся логика лежит в пакетах проекта."""
import sys
import traceback

try:
    from app import main
except Exception:   # ошибку запуска покажем в логах хостинга
    traceback.print_exc()
    sys.stderr.flush()
    raise

if __name__ == "__main__":
    main()
