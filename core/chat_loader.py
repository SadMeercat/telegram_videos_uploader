"""
Модуль для загрузки списка чатов
"""
import asyncio
from typing import List, Dict, Any
from PyQt5.QtCore import QThread, pyqtSignal
from pyrogram import Client
from pyrogram.enums import ChatType


class ChatLoader(QThread):
    """Поток для загрузки списка чатов"""
    
    chats_loaded = pyqtSignal(list)  # Список чатов
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(str)  # Статус загрузки
    
    def __init__(self, api_id: int, api_hash: str):
        """
        Инициализация загрузчика чатов
        
        Args:
            api_id: API ID Telegram
            api_hash: API Hash Telegram
        """
        super().__init__()
        self.api_id = api_id
        self.api_hash = api_hash
    
    def run(self) -> None:
        """Запуск потока загрузки"""
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.load_chats())
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            loop.close()
    
    async def load_chats(self) -> None:
        """Загружает список доступных чатов"""
        client = None
        try:
            client = Client(
                "uploader_session",
                api_id=self.api_id,
                api_hash=self.api_hash
            )
            
            await client.connect()
            
            # Проверяем авторизацию
            try:
                me = await client.get_me()
                if not me:
                    raise Exception("Пользователь не авторизован")
                print(f"[CHAT_LOADER] Загружаем чаты для: {me.first_name}")
            except Exception as e:
                raise Exception(f"Ошибка авторизации: {e}")
            
            self.progress_updated.emit("Получаем список диалогов...")
            
            chats = []
            dialog_count = 0
            
            # Получаем все диалоги
            async for dialog in client.get_dialogs():
                dialog_count += 1
                
                if dialog_count % 50 == 0:
                    self.progress_updated.emit(f"Обработано диалогов: {dialog_count}")
                
                chat = dialog.chat
                
                # Фильтруем чаты
                if not self._should_include_chat(chat):
                    continue
                
                # Подготавливаем информацию о чате
                chat_info = self._prepare_chat_info(chat)
                chats.append(chat_info)
                
                print(f"[CHAT_LOADER] Добавлен чат: {chat_info['title']}")
            
            # Сортируем чаты по названию
            chats.sort(key=lambda x: x['title'].lower())
            
            print(f"[CHAT_LOADER] Загружено {len(chats)} чатов из {dialog_count} диалогов")
            self.chats_loaded.emit(chats)
            
        except Exception as e:
            print(f"[CHAT_LOADER] Ошибка загрузки чатов: {e}")
            self.error_occurred.emit(str(e))
        finally:
            if client:
                await client.disconnect()
    
    def _should_include_chat(self, chat) -> bool:
        """
        Определяет, должен ли чат быть включен в список
        
        Args:
            chat: Объект чата
            
        Returns:
            True если чат должен быть включен
        """
        # Исключаем служебные чаты
        if (hasattr(chat, 'is_self') and chat.is_self) or \
           (hasattr(chat, 'is_support') and chat.is_support) or \
           (hasattr(chat, 'is_verified') and chat.is_verified):
            return False
        
        # Исключаем удаленные аккаунты
        if hasattr(chat, 'is_deleted') and chat.is_deleted:
            return False
        
        # Исключаем заблокированные чаты
        if hasattr(chat, 'is_restricted') and chat.is_restricted:
            return False
        
        # Включаем только определенные типы чатов
        if chat.type in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
            return True
        
        return False
    
    def _prepare_chat_info(self, chat) -> Dict[str, Any]:
        """
        Подготавливает информацию о чате для отображения
        
        Args:
            chat: Объект чата
            
        Returns:
            Словарь с информацией о чате
        """
        # Определяем тип чата
        if chat.type == ChatType.PRIVATE:
            chat_type = "Личный чат"
            # Для личных чатов формируем имя
            title_parts = []
            if hasattr(chat, 'first_name') and chat.first_name:
                title_parts.append(chat.first_name)
            if hasattr(chat, 'last_name') and chat.last_name:
                title_parts.append(chat.last_name)
            if hasattr(chat, 'username') and chat.username:
                title_parts.append(f"@{chat.username}")
            
            title = " ".join(title_parts) if title_parts else f"Пользователь {chat.id}"
            
        elif chat.type == ChatType.GROUP:
            chat_type = "Группа"
            title = getattr(chat, 'title', None) or f"Группа {chat.id}"
            
        elif chat.type == ChatType.SUPERGROUP:
            chat_type = "Супергруппа"
            title = getattr(chat, 'title', None) or f"Супергруппа {chat.id}"
            
        else:
            chat_type = "Неизвестный тип"
            title = f"Чат {chat.id}"
        
        # Добавляем username если есть
        if hasattr(chat, 'username') and chat.username and chat.type != ChatType.PRIVATE:
            title += f" (@{chat.username})"
        
        return {
            'id': chat.id,
            'title': title,
            'type': chat_type,
            'username': getattr(chat, 'username', None)
        }