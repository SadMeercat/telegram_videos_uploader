"""
Модуль для работы с настройками приложения
"""
import json
import os
from typing import Any, Optional


class Settings:
    """Класс для работы с настройками приложения"""
    
    def __init__(self, filename: str = "settings.json"):
        """
        Инициализация настроек
        
        Args:
            filename: Имя файла с настройками
        """
        self.filename = filename
        self.data = {}
        self.load()
    
    def load(self) -> None:
        """Загружает настройки из файла"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")
            self.data = {}
    
    def save(self) -> None:
        """Сохраняет настройки в файл"""
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Получает значение настройки
        
        Args:
            key: Ключ настройки
            default: Значение по умолчанию
            
        Returns:
            Значение настройки или default
        """
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Устанавливает значение настройки
        
        Args:
            key: Ключ настройки
            value: Значение настройки
        """
        self.data[key] = value
        self.save()
    
    def validate_api_settings(self, api_id: str, api_hash: str, phone: str) -> tuple[bool, str]:
        """
        Валидирует настройки API
        
        Args:
            api_id: API ID
            api_hash: API Hash
            phone: Номер телефона
            
        Returns:
            Кортеж (валидно, сообщение об ошибке)
        """
        if not api_id:
            return False, "API ID не указан"
        if not api_hash:
            return False, "API Hash не указан"
        if not phone:
            return False, "Номер телефона не указан"
        
        try:
            int(api_id)
        except ValueError:
            return False, "API ID должен быть числом"
            
        return True, ""