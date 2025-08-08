import sys
import os
import asyncio
import traceback
import time
import threading
import re
import json
import subprocess
import struct
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QPushButton, QLabel, QLineEdit, QTextEdit, 
                             QFileDialog, QMessageBox, QProgressBar, QGroupBox,
                             QComboBox, QListWidget, QListWidgetItem, QSplitter)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QFont
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid
from datetime import datetime
import json


class Settings:
    """Класс для работы с настройками"""
    def __init__(self, filename="settings.json"):
        self.filename = filename
        self.data = {}
        self.load()
    
    def load(self):
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")
            self.data = {}
    
    def save(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")
    
    def get(self, key, default=None):
        return self.data.get(key, default)
    
    def set(self, key, value):
        self.data[key] = value
        self.save()


class ChatLoader(QThread):
    """Поток для загрузки списка чатов"""
    chats_loaded = pyqtSignal(list)  # Список чатов
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(str)  # Статус загрузки
    
    def __init__(self, api_id, api_hash):
        super().__init__()
        self.api_id = api_id
        self.api_hash = api_hash
    
    def run(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.load_chats())
        except Exception as e:
            self.error_occurred.emit(f"Ошибка загрузки чатов: {str(e)}")
        finally:
            loop.close()
    
    async def load_chats(self):
        """Загружает список доступных чатов"""
        client = None
        try:
            self.progress_updated.emit("Подключение к Telegram...")
            
            client = Client(
                name="uploader_session",
                api_id=self.api_id,
                api_hash=self.api_hash,
                workdir=os.path.dirname(os.path.abspath(__file__))
            )
            
            await client.connect()
            
            # Проверяем авторизацию и получаем информацию о себе
            try:
                me = await client.get_me()
                self.progress_updated.emit(f"Подключен как: {me.first_name}")
                my_id = me.id
            except Exception:
                self.error_occurred.emit("Необходима авторизация")
                return
            
            chats = []
            
            # Загружаем диалоги (личные чаты и группы)
            self.progress_updated.emit("Загрузка диалогов...")
            async for dialog in client.get_dialogs(limit=100):
                chat = dialog.chat
                
                # Пропускаем каналы (только для чтения)
                if hasattr(chat, 'type') and chat.type.name == 'CHANNEL':
                    continue
                
                # Пропускаем супергруппы которые являются каналами
                if hasattr(chat, 'type') and chat.type.name == 'SUPERGROUP':
                    if getattr(chat, 'is_broadcast', False):
                        continue  # Это канал, пропускаем
                
                # Пропускаем ботов в личных чатах
                if hasattr(chat, 'type') and chat.type.name == 'PRIVATE':
                    # Проверяем, не является ли это ботом
                    if getattr(chat, 'is_bot', False):
                        continue
                
                # Определяем тип чата
                if hasattr(chat, 'type'):
                    if chat.type.name == 'PRIVATE':
                        # Личная переписка
                        # Проверяем является ли это "Избранными" (Saved Messages)
                        if chat.id == my_id:
                            chat_name = "💾 Избранные"
                        else:
                            first_name = getattr(chat, 'first_name', '') or ''
                            last_name = getattr(chat, 'last_name', '') or ''
                            username = getattr(chat, 'username', '')
                            
                            name_parts = [first_name, last_name]
                            chat_name = " ".join(filter(None, name_parts))
                            
                            if username:
                                chat_name += f" (@{username})"
                            
                            if not chat_name.strip():
                                chat_name = f"User {chat.id}"
                            
                            chat_name = "👤 " + chat_name
                    
                    elif chat.type.name == 'GROUP':
                        # Обычная группа
                        chat_name = f"👥 {chat.title}"
                    
                    elif chat.type.name == 'SUPERGROUP':
                        # Супергруппа (уже проверили, что не канал)
                        chat_name = f"👥 {chat.title}"
                    
                    else:
                        # Пропускаем неизвестные типы
                        continue
                else:
                    # Fallback для старых версий pyrogram - только если это не канал
                    if hasattr(chat, 'title'):
                        chat_name = f"� {chat.title}"
                    elif hasattr(chat, 'first_name'):
                        chat_name = f"👤 {chat.first_name}"
                    else:
                        continue  # Пропускаем неопределенные
                
                # Добавляем информацию о правах
                permissions_info = ""
                if hasattr(dialog.chat, 'permissions'):
                    perms = dialog.chat.permissions
                    if hasattr(perms, 'can_send_messages') and not perms.can_send_messages:
                        permissions_info = " [Только чтение]"
                
                chats.append({
                    'id': chat.id,
                    'name': chat_name + permissions_info,
                    'type': getattr(chat, 'type', 'unknown'),
                    'username': getattr(chat, 'username', ''),
                    'can_send': not permissions_info
                })
            
            # Сортируем чаты: сначала Избранные, потом личные, потом группы
            def sort_key(chat):
                name = chat['name']
                if name.startswith('💾'):  # Избранные
                    return (0, name)
                elif name.startswith('👤'):  # Личные
                    return (1, name)
                elif name.startswith('👥'):  # Группы
                    return (2, name)
                else:
                    return (3, name)
            
            chats.sort(key=sort_key)
            
            self.progress_updated.emit(f"Загружено {len(chats)} чатов (без каналов и ботов)")
            self.chats_loaded.emit(chats)
            
        except Exception as e:
            print(f"Ошибка загрузки чатов: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            self.error_occurred.emit(f"Ошибка: {str(e)}")
        finally:
            if client:
                await client.disconnect()


class TelegramAuth(QThread):
    """Поток для авторизации в Telegram"""
    step_completed = pyqtSignal(str, str, str)  # step, status, data
    error_occurred = pyqtSignal(str)
    code_requested = pyqtSignal()  # Сигнал для запроса кода от пользователя
    
    def __init__(self, api_id, api_hash, phone):
        super().__init__()
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.user_code = None
        self.user_password = None
        self.code_event = None  # Событие для ожидания ввода кода
        self.client = None
        self.phone_code_hash = None
        
    def set_code(self, code):
        """Устанавливает код и сигнализирует потоку продолжить"""
        self.user_code = code
        if self.code_event:
            self.code_event.set()
    
    def set_password(self, password):
        self.user_password = password
        
    def run(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.full_authorization_flow())
        except Exception as e:
            self.error_occurred.emit(f"Ошибка: {str(e)}")
        finally:
            loop.close()
    
    async def full_authorization_flow(self):
        """Полный цикл авторизации в одном потоке"""
        try:
            print(f"[AUTH] Начинаем полную авторизацию для {self.phone}")
            
            # Создаем клиент
            self.client = Client(
                name="uploader_session",
                api_id=self.api_id,
                api_hash=self.api_hash,
                workdir=os.path.dirname(os.path.abspath(__file__))
            )
            
            await self.client.connect()
            print("[AUTH] Подключение установлено")
            
            # Отправляем код
            result = await self.client.send_code(phone_number=self.phone)
            self.phone_code_hash = getattr(result, 'phone_code_hash', '')
            
            print(f"[AUTH] Код отправлен, phone_code_hash: {self.phone_code_hash}")
            self.step_completed.emit("code_sent", "success", self.phone_code_hash)
            
            # Ждем ввода кода от пользователя
            await self.wait_for_user_code()
            
            # Теперь подтверждаем код в той же сессии
            await self.confirm_code_in_same_session()
            
        except Exception as e:
            print(f"[AUTH] Ошибка авторизации: {e}")
            print(f"[AUTH] Traceback: {traceback.format_exc()}")
            self.error_occurred.emit(f"Ошибка авторизации: {str(e)}")
        finally:
            if self.client:
                try:
                    await self.client.disconnect()
                except Exception as e:
                    print(f"[AUTH] Ошибка при отключении: {e}")
    
    async def wait_for_user_code(self):
        """Ждем ввода кода от пользователя"""
        import threading
        
        self.code_event = threading.Event()
        
        # Ждем пока пользователь не введет код (с таймаутом 120 секунд)
        loop = asyncio.get_event_loop()
        
        def wait_for_code():
            return self.code_event.wait(timeout=120)  # 2 минуты
        
        # Запускаем ожидание в отдельном потоке, чтобы не блокировать event loop
        code_received = await loop.run_in_executor(None, wait_for_code)
        
        if not code_received:
            raise Exception("Время ожидания кода истекло")
            
        print(f"[AUTH] Получен код от пользователя: {self.user_code}")
    
    async def confirm_code_in_same_session(self):
        """Подтверждаем код в той же сессии"""
        try:
            print(f"[AUTH] Подтверждение кода: {self.user_code}")
            print(f"[AUTH] Используем phone_code_hash: {self.phone_code_hash}")
            
            signed_in = await self.client.sign_in(
                phone_number=self.phone,
                phone_code_hash=self.phone_code_hash,
                phone_code=self.user_code
            )
            
            # Получаем информацию о пользователе
            me = await self.client.get_me()
            user_info = f"{me.first_name or ''} {me.last_name or ''}".strip()
            if me.username:
                user_info += f" (@{me.username})"
            
            print(f"[AUTH] Авторизация успешна: {user_info}")
            self.step_completed.emit("auth_success", "success", user_info)
            
        except SessionPasswordNeeded:
            print("[AUTH] Обнаружена двухфакторная аутентификация")
            if self.user_password:
                print("[AUTH] Есть пароль 2FA, проверяем...")
                try:
                    await self.client.check_password(self.user_password)
                    me = await self.client.get_me()
                    user_info = f"{me.first_name or ''} {me.last_name or ''}".strip()
                    if me.username:
                        user_info += f" (@{me.username})"
                    print(f"[AUTH] Авторизация с 2FA успешна: {user_info}")
                    self.step_completed.emit("auth_success", "success", user_info)
                except Exception as pwd_error:
                    print(f"[AUTH] Ошибка пароля 2FA: {pwd_error}")
                    self.step_completed.emit("need_password", "error", f"Неверный пароль 2FA: {pwd_error}")
            else:
                print("[AUTH] Требуется пароль 2FA, но не указан")
                self.step_completed.emit("need_password", "info", "Требуется пароль двухфакторной аутентификации")
    
    async def check_authorization(self):
        """Проверяет авторизацию"""
        client = None
        try:
            client = Client(
                name="uploader_session",
                api_id=self.api_id,
                api_hash=self.api_hash,
                workdir=os.path.dirname(os.path.abspath(__file__))
            )
            
            await client.connect()
            
            # Проверяем авторизацию
            try:
                me = await client.get_me()
                user_info = f"{me.first_name or ''} {me.last_name or ''}".strip()
                if me.username:
                    user_info += f" (@{me.username})"
                self.step_completed.emit("already_authorized", "success", user_info)
            except:
                self.step_completed.emit("not_authorized", "info", "")
                
        except Exception as e:
            self.step_completed.emit("not_authorized", "info", "")
        finally:
            if client:
                await client.disconnect()


class TelegramAuthChecker(QThread):
    """Отдельный поток только для проверки авторизации"""
    step_completed = pyqtSignal(str, str, str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, api_id, api_hash, phone):
        super().__init__()
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
    
    def run(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.check_authorization())
        except Exception as e:
            self.error_occurred.emit(f"Ошибка: {str(e)}")
        finally:
            loop.close()
    
    async def check_authorization(self):
        """Проверяет авторизацию"""
        client = None
        try:
            client = Client(
                name="uploader_session",
                api_id=self.api_id,
                api_hash=self.api_hash,
                workdir=os.path.dirname(os.path.abspath(__file__))
            )
            
            await client.connect()
            
            # Проверяем авторизацию
            try:
                me = await client.get_me()
                user_info = f"{me.first_name or ''} {me.last_name or ''}".strip()
                if me.username:
                    user_info += f" (@{me.username})"
                self.step_completed.emit("already_authorized", "success", user_info)
            except:
                self.step_completed.emit("not_authorized", "info", "")
                
        except Exception as e:
            self.step_completed.emit("not_authorized", "info", "")
        finally:
            if client:
                await client.disconnect()


def get_video_metadata(video_path):
    """Извлекает метаданные видео (длительность, разрешение) с помощью moviepy"""
    try:
        # Используем moviepy для извлечения метаданных
        try:
            from moviepy import VideoFileClip
            print("[VIDEO_META] Открываем видео с помощью moviepy...")
            
            clip = VideoFileClip(video_path)
            duration = clip.duration
            width, height = clip.size
            clip.close()  # Освобождаем ресурсы
            
            print(f"[VIDEO_META] moviepy успешно: длительность={duration}с ({duration//60:.0f}:{duration%60:02.0f}), разрешение={width}x{height}")
            return {
                'duration': int(duration) if duration and duration > 0 else None,
                'width': width if width and width > 0 else None,
                'height': height if height and height > 0 else None
            }
        except ImportError as ie:
            print(f"[VIDEO_META] moviepy не найдена: {ie}")
        except Exception as e:
            print(f"[VIDEO_META] moviepy ошибка: {e}")
        
        # Fallback: Оценка по размеру файла и расширению
        print("[VIDEO_META] Используем оценку по размеру файла...")
        file_size = os.path.getsize(video_path)
        file_ext = os.path.splitext(video_path)[1].lower()
        
        # Разные оценки битрейта в зависимости от формата
        if file_ext in ['.mp4', '.mkv', '.mov']:
            # Современные кодеки, обычно хорошее сжатие
            estimated_bitrate = 2 * 1024 * 1024  # 2 Мбит/с
        elif file_ext in ['.avi', '.wmv']:
            # Старые форматы, обычно меньше сжатие
            estimated_bitrate = 4 * 1024 * 1024  # 4 Мбит/с
        elif file_ext in ['.webm']:
            # WebM обычно хорошо сжат
            estimated_bitrate = 1.5 * 1024 * 1024  # 1.5 Мбит/с
        else:
            # По умолчанию
            estimated_bitrate = 3 * 1024 * 1024  # 3 Мбит/с
        
        estimated_duration = max(10, int((file_size * 8) / estimated_bitrate))  # Минимум 10 секунд
        
        print(f"[VIDEO_META] Оценка по размеру файла: {file_size/(1024*1024):.1f}МБ -> ~{estimated_duration}с ({estimated_duration//60:.0f}:{estimated_duration%60:02.0f})")
        return {
            'duration': estimated_duration,
            'width': None,
            'height': None
        }
        
    except Exception as e:
        print(f"[VIDEO_META] Ошибка извлечения метаданных: {e}")
        return {'duration': None, 'width': None, 'height': None}


class VideoUploader(QThread):
    """Поток для загрузки видео"""
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    file_uploaded = pyqtSignal(str)
    file_progress = pyqtSignal(str, int, str)  # filename, percentage, speed
    finished = pyqtSignal(bool, str)
    
    def __init__(self, api_id, api_hash, chat_id, video_folder, delay_seconds=1, max_concurrent=4, prefix_text=""):
        super().__init__()
        self.api_id = api_id
        self.api_hash = api_hash
        self.chat_id = chat_id
        self.video_folder = video_folder
        self.delay_seconds = delay_seconds
        self.max_concurrent = max_concurrent  # Количество параллельных передач
        self.prefix_text = prefix_text  # ДОБАВЛЕНО: префикс для названий файлов
        self.should_stop = False
        self.current_file = ""
        self.start_time = None
    
    def progress_callback(self, current, total):
        """Callback для отслеживания прогресса загрузки файла"""
        if self.should_stop:
            return
            
        percentage = int((current / total) * 100) if total > 0 else 0
        
        # Расширенная статистика скорости
        if self.start_time:
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                speed_bps = current / elapsed
                
                # Адаптивная оптимизация для медленных соединений
                if speed_bps < 100 * 1024:  # Меньше 100 КБ/с
                    print(f"[SPEED] Медленная скорость: {speed_bps/1024:.1f} КБ/с - возможна оптимизация")
                
                # Форматирование с ETA
                if speed_bps > 1024 * 1024:
                    speed_str = f"{speed_bps / (1024 * 1024):.1f} МБ/с"
                elif speed_bps > 1024:
                    speed_str = f"{speed_bps / 1024:.1f} КБ/с"
                else:
                    speed_str = f"{speed_bps:.0f} Б/с"
                
                # Расчет времени до завершения
                remaining_bytes = total - current
                eta_seconds = remaining_bytes / speed_bps if speed_bps > 0 else 0
                if eta_seconds < 3600:  # Меньше часа
                    eta_str = f" | Осталось: {eta_seconds/60:.1f}мин"
                else:
                    eta_str = f" | Осталось: {eta_seconds/3600:.1f}ч"
                
                speed_str += eta_str if eta_seconds > 10 else ""
            else:
                speed_str = "Вычисляется..."
        else:
            speed_str = "Начинаем..."
        
        # Отправляем сигнал с прогрессом
        self.file_progress.emit(self.current_file, percentage, speed_str)
    
    def stop_upload(self):
        """Останавливает загрузку видео"""
        self.should_stop = True
        print(f"[UPLOAD] Флаг остановки установлен: should_stop = {self.should_stop}")
        
        # Прерываем текущую операцию если возможно
        if hasattr(self, '_current_upload_task'):
            try:
                self._current_upload_task.cancel()
                print(f"[UPLOAD] Задача загрузки отменена")
            except Exception as e:
                print(f"[UPLOAD] Не удалось отменить задачу: {e}")
    
    def run(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.upload_videos())
        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            loop.close()
    
    async def upload_videos(self):
        client = None
        try:
            print(f"[UPLOAD] Начинаем процесс загрузки видео")
            print(f"[UPLOAD] API ID: {self.api_id}, Chat ID: {self.chat_id}")
            print(f"[UPLOAD] Папка с видео: {self.video_folder}")
            print(f"[UPLOAD] 🚀 Настройки скорости: {self.max_concurrent} параллельных передач")
            
            # Подключаемся с оптимизацией для больших файлов
            client = Client(
                name="uploader_session",
                api_id=self.api_id,
                api_hash=self.api_hash,
                workdir=os.path.dirname(os.path.abspath(__file__)),
                # Динамическая оптимизация для скорости загрузки больших файлов
                max_concurrent_transmissions=self.max_concurrent,  # Настраиваемое количество передач
                sleep_threshold=300,  # Увеличиваем порог для sleep
                workers=min(8, self.max_concurrent * 2)  # Адаптивное количество воркеров
            )
            
            print(f"[UPLOAD] ✅ Клиент создан с оптимизациями:")
            print(f"[UPLOAD]   - max_concurrent_transmissions: {self.max_concurrent}")
            print(f"[UPLOAD]   - workers: {min(8, self.max_concurrent * 2)}")
            print(f"[UPLOAD]   - sleep_threshold: 300")
            
            print(f"[UPLOAD] Подключаемся к Telegram...")
            await client.connect()
            print(f"[UPLOAD] Подключение установлено")
            
            # Оптимизация соединения для больших файлов
            try:
                # Быстрое подключение к ближайшему DC - исправляем ошибку
                print(f"[UPLOAD] Определяем оптимальный дата-центр...")
                dialogs = []
                async for dialog in client.get_dialogs(limit=1):
                    dialogs.append(dialog)
                    break  # Берем только первый диалог для прогрева
                
                print(f"[UPLOAD] Прогрев соединения завершен")
                
                # Получаем информацию о DC для оптимизации
                if hasattr(client, 'session') and hasattr(client.session, 'dc_id'):
                    dc_id = client.session.dc_id
                    print(f"[UPLOAD] Подключен к DC {dc_id}")
                    self.status_updated.emit(f"Подключен к дата-центру {dc_id}")
                
                # Пробуем настроить размер чанка
                try:
                    # Попытка 1: через session
                    if hasattr(client.session, 'CHUNK_SIZE'):
                        original_chunk_size = client.session.CHUNK_SIZE
                        client.session.CHUNK_SIZE = 524288  # 512KB
                        print(f"[UPLOAD] Размер чанка увеличен с {original_chunk_size} до {client.session.CHUNK_SIZE}")
                    
                    # Попытка 2: через storage
                    elif hasattr(client, 'storage') and hasattr(client.storage, 'CHUNK_SIZE'):
                        original_chunk_size = client.storage.CHUNK_SIZE
                        client.storage.CHUNK_SIZE = 524288  # 512KB
                        print(f"[UPLOAD] Размер чанка (storage) увеличен с {original_chunk_size} до {client.storage.CHUNK_SIZE}")
                    
                    # Попытка 3: глобально для pyrogram
                    else:
                        import pyrogram
                        if hasattr(pyrogram, 'raw') and hasattr(pyrogram.raw, 'functions'):
                            print(f"[UPLOAD] Используем стандартные настройки Pyrogram")
                        else:
                            print(f"[UPLOAD] Размер чанка: используем по умолчанию")
                except Exception as chunk_error:
                    print(f"[UPLOAD] Настройка чанка не удалась: {chunk_error}")
                
                # Подтверждаем настройки оптимизации
                print(f"[UPLOAD] ✅ Применены настройки скорости:")
                print(f"[UPLOAD]   - Параллельные передачи: {self.max_concurrent}")
                print(f"[UPLOAD]   - Воркеры: {min(8, self.max_concurrent * 2)}")
                print(f"[UPLOAD]   - Режим: {'Максимальная' if self.max_concurrent >= 8 else 'Быстрая' if self.max_concurrent >= 4 else 'Обычная'} скорость")
                
            except Exception as opt_error:
                print(f"[UPLOAD] Предупреждение оптимизации: {opt_error}")
                # Продолжаем работу даже если оптимизация не удалась
            
            # Проверяем авторизацию
            me = await client.get_me()
            print(f"[UPLOAD] Авторизован как: {me.first_name} (ID: {me.id})")
            
            # Принудительно устанавливаем информацию о пользователе в клиенте
            # Это исправляет ошибку 'NoneType' object has no attribute 'is_premium'
            client.me = me
            print(f"[UPLOAD] Установлена информация о пользователе в клиенте")
            
            # Проверяем премиум статус для больших файлов
            is_premium = getattr(me, 'is_premium', False)
            
            # Определяем текст режима скорости
            if self.max_concurrent == 1:
                speed_mode = "Обычная скорость"
            elif self.max_concurrent == 4:
                speed_mode = "Быстрая скорость"
            else:
                speed_mode = "Максимальная скорость"
            
            if is_premium:
                print(f"[UPLOAD] ✅ Премиум аккаунт - поддержка файлов до 4 ГБ")
                self.status_updated.emit(f"Подключен как: {me.first_name} (Премиум) | {speed_mode}")
            else:
                print(f"[UPLOAD] ⚠️ Обычный аккаунт - лимит файлов 2 ГБ")
                self.status_updated.emit(f"Подключен как: {me.first_name} (лимит 2 ГБ) | {speed_mode}")
            
            # Загружаем диалоги для обновления кэша пиров (решает проблему PEER_ID_INVALID)
            print(f"[UPLOAD] Загружаем диалоги для обновления кэша пиров...")
            self.status_updated.emit("Обновляем список чатов...")
            dialogs_count = 0
            async for dialog in client.get_dialogs(limit=100):
                dialogs_count += 1
                if dialog.chat.id == int(self.chat_id):
                    print(f"[UPLOAD] Найден целевой чат: {dialog.chat.title or dialog.chat.first_name} (ID: {dialog.chat.id})")
            
            print(f"[UPLOAD] Загружено {dialogs_count} диалогов, кэш пиров обновлен")
            
            # Получаем список видео файлов
            video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.ogv']
            video_files = []
            
            for file in os.listdir(self.video_folder):
                if any(file.lower().endswith(ext) for ext in video_extensions):
                    video_files.append(file)
            
            if not video_files:
                self.finished.emit(False, "В папке нет видео файлов")
                return
            
            video_files.sort()
            self.status_updated.emit(f"Найдено {len(video_files)} видео файлов (отправляем как видео)")
            
            # Отправляем видео
            successful = 0
            for i, video_file in enumerate(video_files):
                if self.should_stop:
                    break
                
                video_path = os.path.join(self.video_folder, video_file)
                file_name = os.path.splitext(video_file)[0]
                
                self.status_updated.emit(f"Отправляем файл: {video_file} ({i+1}/{len(video_files)})")
                
                try:
                    file_size = os.path.getsize(video_path)
                    size_mb = file_size / (1024 * 1024)
                    
                    print(f"[UPLOAD] Начинаем отправку видео: {video_file}, размер: {size_mb:.1f} MB")
                    print(f"[UPLOAD] Chat ID: {self.chat_id}, путь: {video_path}")
                    print(f"[UPLOAD] client.me установлен: {client.me is not None}")
                    if client.me:
                        print(f"[UPLOAD] Премиум статус: {getattr(client.me, 'is_premium', 'не определен')}")
                    
                    # Отображаем статус загрузки
                    self.status_updated.emit(f"Отправляем видео: {video_file} ({size_mb:.1f} MB)")
                    
                    # Небольшая пауза перед отправкой (имитирует ручную отправку)
                    if i > 0:  # Не ждем перед первым файлом
                        await asyncio.sleep(0.5)
                    
                    # Устанавливаем текущий файл и время начала для отслеживания прогресса
                    self.current_file = video_file
                    self.start_time = time.time()
                    
                    # Проверяем доступность чата перед отправкой
                    try:
                        print(f"[UPLOAD] Проверяем доступность чата ID: {self.chat_id}")
                        peer = await client.resolve_peer(self.chat_id)
                        print(f"[UPLOAD] Чат найден: {peer}")
                    except Exception as peer_error:
                        print(f"[UPLOAD] Ошибка проверки чата: {peer_error}")
                        self.file_uploaded.emit(f"❌ {video_file}: Чат недоступен (ID: {self.chat_id})")
                        continue
                    
                    # ИСПРАВЛЕНО: Формируем caption с префиксом и без расширения файла
                    # Убираем расширение из имени файла
                    file_name_clean = os.path.splitext(video_file)[0]
                    
                    # Добавляем префикс если он указан
                    if self.prefix_text.strip():
                        caption_text = f"{self.prefix_text.strip()} {file_name_clean}"
                    else:
                        caption_text = file_name_clean
                    
                    # ДОБАВЛЕНО: Извлекаем метаданные видео для превью и длительности
                    self.status_updated.emit(f"Получаем информацию о видео: {video_file}")
                    video_metadata = get_video_metadata(video_path)
                    
                    duration = video_metadata.get('duration')
                    width = video_metadata.get('width')
                    height = video_metadata.get('height')
                    
                    # Логируем метаданные
                    if duration:
                        duration_str = f"{duration//60}:{duration%60:02d}" if duration >= 60 else f"{duration}с"
                        print(f"[UPLOAD] Метаданные видео: длительность={duration_str}")
                        if width and height:
                            print(f"[UPLOAD] Разрешение: {width}x{height}")
                    
                    # Отправка как видео с метаданными - оптимизировано для больших файлов
                    send_video_params = {
                        'chat_id': self.chat_id,
                        'video': video_path,
                        'caption': caption_text[:1024],  # Telegram ограничивает caption до 1024 символов
                        'progress': self.progress_callback,
                        'supports_streaming': True  # Включаем поддержку стриминга для лучшего воспроизведения
                    }
                    
                    # Добавляем метаданные если они найдены
                    if duration and duration > 0:
                        send_video_params['duration'] = duration
                    if width and height and width > 0 and height > 0:
                        send_video_params['width'] = width
                        send_video_params['height'] = height
                    
                    result = await client.send_video(**send_video_params)
                    
                    # Проверяем результат отправки
                    if result and hasattr(result, 'id'):
                        print(f"[UPLOAD] Успешно отправлено видео: {video_file}, Message ID: {result.id}")
                        successful += 1
                        
                        # Формируем сообщение с метаданными
                        result_msg = f"✅ {video_file} ({size_mb:.1f} MB)"
                        if duration and duration > 0:
                            if duration >= 60:
                                duration_str = f"{duration//60}:{duration%60:02d}"
                            else:
                                duration_str = f"{duration}с"
                            result_msg += f" [{duration_str}]"
                        if width and height:
                            result_msg += f" {width}x{height}"
                        result_msg += " - Отправлено как видео"
                        
                        self.file_uploaded.emit(result_msg)
                    else:
                        print(f"[UPLOAD] Видео отправлено, но результат неопределен: {video_file}")
                        successful += 1
                        
                        # Формируем сообщение с метаданными
                        result_msg = f"✅ {video_file} ({size_mb:.1f} MB)"
                        if duration and duration > 0:
                            if duration >= 60:
                                duration_str = f"{duration//60}:{duration%60:02d}"
                            else:
                                duration_str = f"{duration}с"
                            result_msg += f" [{duration_str}]"
                        if width and height:
                            result_msg += f" {width}x{height}"
                        result_msg += " - Отправлено как видео"
                        
                        self.file_uploaded.emit(result_msg)
                    
                    progress = int((i + 1) / len(video_files) * 100)
                    self.progress_updated.emit(progress)
                    
                    if i < len(video_files) - 1 and self.delay_seconds > 0:
                        self.status_updated.emit(f"Пауза {self.delay_seconds} сек...")
                        await asyncio.sleep(self.delay_seconds)
                        
                except Exception as e:
                    error_str = str(e)
                    print(f"[UPLOAD] Ошибка при отправке {video_file}: {error_str}")
                    print(f"[UPLOAD] Traceback: {traceback.format_exc()}")
                    
                    # Пробуем определить тип ошибки более точно
                    if hasattr(e, '__class__'):
                        print(f"[UPLOAD] Тип ошибки: {e.__class__.__name__}")
                    
                    self.file_uploaded.emit(f"❌ {video_file}: {error_str}")
            
            result_msg = f"Загружено {successful} из {len(video_files)} файлов"
            self.finished.emit(successful > 0, result_msg)
            
        except Exception as e:
            error_msg = f"Ошибка: {str(e)}"
            print(f"[UPLOAD] Общая ошибка загрузки: {error_msg}")
            print(f"[UPLOAD] Traceback общей ошибки: {traceback.format_exc()}")
            self.finished.emit(False, error_msg)
        finally:
            print(f"[UPLOAD] Завершаем работу, отключаемся от клиента")
            if client:
                await client.disconnect()
                print(f"[UPLOAD] Клиент отключен")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.phone_code_hash = None
        self.auth_thread = None
        self.upload_thread = None
        self.chat_loader_thread = None
        self.chats_list = []
        self.code_timer = None  # Таймер для обратного отсчета
        self.time_left = 0
        self.init_ui()
        self.load_settings()
        
    def init_ui(self):
        self.setWindowTitle("Telegram Video Uploader v3.1")
        self.setGeometry(100, 100, 1100, 600)  # Еще больше увеличили ширину и уменьшили высоту
        
        # Устанавливаем стильную иконку и тему
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f0f4ff, stop:1 #e8f0ff);
            }
            QWidget {
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 11px;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 2px solid #d0d0d0;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 5px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8f9fa);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                color: #2c3e50;
                background: transparent;
            }
            QLineEdit {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                padding: 8px 12px;
                background: white;
                font-size: 11px;
                selection-background-color: #2196F3;
            }
            QLineEdit:focus {
                border-color: #2196F3;
            }
            QLineEdit:disabled {
                background-color: #f5f5f5;
                color: #999;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4CAF50, stop:1 #45a049);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: bold;
                font-size: 11px;
                min-height: 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5CBF60, stop:1 #4CAF50);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #45a049, stop:1 #3e8e41);
            }
            QPushButton:disabled {
                background: #cccccc;
                color: #666666;
            }
            QComboBox {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                padding: 8px 12px;
                background: white;
                min-width: 100px;
            }
            QComboBox:focus {
                border-color: #2196F3;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 8px solid #666;
                margin-right: 5px;
            }
            QProgressBar {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                text-align: center;
                background: white;
                height: 20px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #2196F3);
                border-radius: 6px;
                margin: 2px;
            }
            QTextEdit {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background: white;
                padding: 8px;
                font-family: "Consolas", "Courier New", monospace;
                font-size: 10px;
            }
            QListWidget {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background: white;
                alternate-background-color: #f8f9fa;
                outline: none;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #f0f0f0;
                border-radius: 4px;
                margin: 2px;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2196F3, stop:1 #1976D2);
                color: white;
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e3f2fd, stop:1 #bbdefb);
                border-radius: 6px;
            }
            QSplitter::handle {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e0e0e0, stop:1 #d0d0d0);
                border-radius: 3px;
                margin: 2px;
            }
            QSplitter::handle:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2196F3, stop:1 #1976D2);
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Создаем горизонтальный разделитель для двух колонок
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setHandleWidth(8)
        central_widget_layout = QVBoxLayout(central_widget)
        central_widget_layout.setContentsMargins(8, 8, 8, 8)  # Еще больше уменьшили отступы
        central_widget_layout.addWidget(main_splitter)
        
        # Левая колонка - настройки
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(6)  # Еще больше уменьшили расстояние между элементами
        left_layout.setContentsMargins(6, 6, 6, 6)  # Еще больше уменьшили отступы
        main_splitter.addWidget(left_widget)
        
        # Правая колонка - выбор чатов
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(6)  # Еще больше уменьшили расстояние между элементами
        right_layout.setContentsMargins(6, 6, 6, 6)  # Еще больше уменьшили отступы
        main_splitter.addWidget(right_widget)
        
        # Устанавливаем пропорции (60% левая, 40% правая)
        main_splitter.setSizes([660, 440])
        
        # Красивый заголовок с градиентом
        title_widget = QWidget()
        title_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 15px;
                margin: 0px 0px 10px 0px;
            }
        """)
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(15, 6, 15, 6)  # Еще больше уменьшили вертикальные отступы
        
        title = QLabel("📹 Telegram Video Uploader")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))  # Еще больше уменьшили размер шрифта
        title.setStyleSheet("color: white; background: transparent; margin: 0px;")
        title_layout.addWidget(title)
        
        subtitle = QLabel("Быстрая загрузка видео в Telegram с метаданными")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setFont(QFont("Segoe UI", 8))  # Еще больше уменьшили размер шрифта
        subtitle.setStyleSheet("color: rgba(255, 255, 255, 0.9); background: transparent; margin: 0px;")
        title_layout.addWidget(subtitle)
        
        left_layout.addWidget(title_widget)
        
        # Горизонтальный контейнер для API и авторизации
        api_auth_layout = QHBoxLayout()
        api_auth_layout.setSpacing(8)
        
        # Секция API с красивым оформлением
        api_group = QGroupBox("🔑 Настройки API")
        api_group.setStyleSheet("""
            QGroupBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8f9fa);
                border: 2px solid #e0e7ff;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                color: #4338ca;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        api_layout = QVBoxLayout(api_group)
        api_layout.setSpacing(6)  # Еще больше уменьшили расстояние между элементами
        
        api_id_layout = QHBoxLayout()
        api_id_label = QLabel("API ID:")
        api_id_label.setStyleSheet("color: #374151; font-weight: 600; min-width: 70px;")
        api_id_layout.addWidget(api_id_label)
        self.api_id_input = QLineEdit()
        self.api_id_input.setPlaceholderText("Получите на my.telegram.org")
        api_id_layout.addWidget(self.api_id_input)
        api_layout.addLayout(api_id_layout)
        
        api_hash_layout = QHBoxLayout()
        api_hash_label = QLabel("API Hash:")
        api_hash_label.setStyleSheet("color: #374151; font-weight: 600; min-width: 70px;")
        api_hash_layout.addWidget(api_hash_label)
        self.api_hash_input = QLineEdit()
        self.api_hash_input.setPlaceholderText("Получите на my.telegram.org")
        api_hash_layout.addWidget(self.api_hash_input)
        api_layout.addLayout(api_hash_layout)
        
        api_auth_layout.addWidget(api_group)
        
        # Секция авторизации с красивым оформлением
        auth_group = QGroupBox("🔐 Авторизация в Telegram")
        auth_group.setStyleSheet("""
            QGroupBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8f9fa);
                border: 2px solid #dcfce7;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                color: #16a34a;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        auth_layout = QVBoxLayout(auth_group)
        auth_layout.setSpacing(6)  # Еще больше уменьшили расстояние между элементами
        
        # Номер телефона
        phone_layout = QHBoxLayout()
        phone_label = QLabel("Телефон:")
        phone_label.setStyleSheet("color: #374151; font-weight: 600; min-width: 70px;")
        phone_layout.addWidget(phone_label)
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("+7XXXXXXXXXX")
        phone_layout.addWidget(self.phone_input)
        auth_layout.addLayout(phone_layout)
        
        # Кнопки авторизации с цветовой схемой
        auth_buttons_layout = QHBoxLayout()
        
        self.check_auth_button = QPushButton("🔍 Проверить")
        self.check_auth_button.clicked.connect(self.check_authorization)
        self.check_auth_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #a855f7, stop:1 #9333ea);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #c084fc, stop:1 #a855f7);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #9333ea, stop:1 #7c3aed);
            }
        """)
        auth_buttons_layout.addWidget(self.check_auth_button)
        
        self.reset_auth_button = QPushButton("🔄 Сброс")
        self.reset_auth_button.clicked.connect(self.reset_authorization)
        self.reset_auth_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ef4444, stop:1 #dc2626);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f87171, stop:1 #ef4444);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #dc2626, stop:1 #b91c1c);
            }
        """)
        auth_buttons_layout.addWidget(self.reset_auth_button)
        
        auth_layout.addLayout(auth_buttons_layout)
        
        # Получение кода и ввод кода в одной строке
        code_layout = QHBoxLayout()
        self.get_code_button = QPushButton("📱 Код")
        self.get_code_button.clicked.connect(self.request_code)
        self.get_code_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3b82f6, stop:1 #2563eb);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: bold;
                font-size: 10px;
                min-width: 50px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #60a5fa, stop:1 #3b82f6);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2563eb, stop:1 #1d4ed8);
            }
            QPushButton:disabled {
                background: #d1d5db;
                color: #9ca3af;
            }
        """)
        self.get_code_button.setEnabled(False)
        code_layout.addWidget(self.get_code_button)
        
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Код")
        self.code_input.setMaxLength(5)
        self.code_input.setEnabled(False)
        self.code_input.setMaximumWidth(60)
        # Добавляем обработчик Enter для быстрого подтверждения
        self.code_input.returnPressed.connect(self.confirm_code)
        code_layout.addWidget(self.code_input)
        
        self.confirm_code_button = QPushButton("✅ OK")
        self.confirm_code_button.clicked.connect(self.confirm_code)
        self.confirm_code_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #10b981, stop:1 #059669);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: bold;
                font-size: 10px;
                min-width: 40px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #34d399, stop:1 #10b981);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #059669, stop:1 #047857);
            }
            QPushButton:disabled {
                background: #d1d5db;
                color: #9ca3af;
            }
        """)
        self.confirm_code_button.setEnabled(False)
        code_layout.addWidget(self.confirm_code_button)
        auth_layout.addLayout(code_layout)
        
        # Пароль 2FA
        password_layout = QHBoxLayout()
        password_label = QLabel("2FA:")
        password_label.setStyleSheet("color: #374151; font-weight: 600; min-width: 70px;")
        password_layout.addWidget(password_label)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Пароль (если включена 2FA)")
        password_layout.addWidget(self.password_input)
        auth_layout.addLayout(password_layout)
        
        api_auth_layout.addWidget(auth_group)
        
        left_layout.addLayout(api_auth_layout)
        
        # Статус авторизации с красивым оформлением
        self.auth_status_label = QLabel("📋 Статус: Не проверено")
        self.auth_status_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-weight: bold;
                padding: 8px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f9fafb, stop:1 #f3f4f6);
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                margin: 5px 0px;
            }
        """)
        left_layout.addWidget(self.auth_status_label)
        
        api_auth_layout.addWidget(auth_group)
        
        left_layout.addLayout(api_auth_layout)
        
        # Секция загрузки с красивым оформлением
        upload_group = QGroupBox("🚀 Загрузка видео")
        upload_group.setStyleSheet("""
            QGroupBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8f9fa);
                border: 2px solid #fef3c7;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                color: #d97706;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        upload_layout = QVBoxLayout(upload_group)
        upload_layout.setSpacing(6)  # Еще больше уменьшили расстояние между элементами
        
        # Выбор папки
        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setReadOnly(True)
        self.folder_input.setPlaceholderText("Выберите папку с видео")
        folder_layout.addWidget(self.folder_input)
        
        self.browse_button = QPushButton("📁 Обзор")
        self.browse_button.clicked.connect(self.browse_folder)
        self.browse_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f59e0b, stop:1 #d97706);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: bold;
                font-size: 11px;
                min-width: 100px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fbbf24, stop:1 #f59e0b);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #d97706, stop:1 #b45309);
            }
        """)
        folder_layout.addWidget(self.browse_button)
        upload_layout.addLayout(folder_layout)
        
        # Поле для префикса текста
        prefix_layout = QHBoxLayout()
        prefix_label = QLabel("📝 Префикс:")
        prefix_label.setStyleSheet("color: #374151; font-weight: 600; min-width: 80px;")
        prefix_layout.addWidget(prefix_label)
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("Текст перед названием файла (необязательно)")
        self.prefix_input.setToolTip("Этот текст будет добавлен перед названием файла при отправке")
        self.prefix_input.textChanged.connect(self.on_prefix_changed)
        prefix_layout.addWidget(self.prefix_input)
        upload_layout.addLayout(prefix_layout)
        
        # Настройки в две колонки
        settings_layout = QHBoxLayout()
        
        # Задержка
        delay_layout = QVBoxLayout()
        delay_label = QLabel("⏱️ Задержка (сек):")
        delay_label.setStyleSheet("color: #374151; font-weight: 600;")
        delay_layout.addWidget(delay_label)
        self.delay_input = QLineEdit()
        self.delay_input.setText("2")
        self.delay_input.setMaximumWidth(80)
        delay_layout.addWidget(self.delay_input)
        settings_layout.addLayout(delay_layout)
        
        settings_layout.addStretch()
        
        # Настройки скорости
        speed_layout = QVBoxLayout()
        speed_label = QLabel("🚀 Скорость:")
        speed_label.setStyleSheet("color: #374151; font-weight: 600;")
        speed_layout.addWidget(speed_label)
        self.speed_combo = QComboBox()
        self.speed_combo.addItems([
            "Обычная (1 поток)",
            "Быстрая (4 потока)", 
            "Максимальная (8 потоков)"
        ])
        self.speed_combo.setCurrentIndex(1)  # По умолчанию быстрая
        self.speed_combo.setToolTip("Для файлов до 3 ГБ рекомендуется максимальная скорость")
        speed_layout.addWidget(self.speed_combo)
        settings_layout.addLayout(speed_layout)
        
        upload_layout.addLayout(settings_layout)
        
        # Красивые кнопки загрузки
        upload_buttons_layout = QHBoxLayout()
        upload_buttons_layout.setSpacing(8)
        
        self.start_button = QPushButton("🚀 Начать загрузку")
        self.start_button.clicked.connect(self.start_upload)
        self.start_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #10b981, stop:1 #059669);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 16px;
                font-weight: bold;
                font-size: 12px;
                min-height: 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #34d399, stop:1 #10b981);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #059669, stop:1 #047857);
            }
            QPushButton:disabled {
                background: #d1d5db;
                color: #9ca3af;
            }
        """)
        self.start_button.setEnabled(False)
        upload_buttons_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("⏹️ Остановить")
        self.stop_button.clicked.connect(self.stop_upload)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ef4444, stop:1 #dc2626);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 16px;
                font-weight: bold;
                font-size: 12px;
                min-height: 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f87171, stop:1 #ef4444);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #dc2626, stop:1 #b91c1c);
            }
            QPushButton:disabled {
                background: #d1d5db;
                color: #9ca3af;
            }
        """)
        self.stop_button.setEnabled(False)
        upload_buttons_layout.addWidget(self.stop_button)
        
        upload_layout.addLayout(upload_buttons_layout)
        
        # Стильные прогресс-бары
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #e5e7eb;
                border-radius: 8px;
                text-align: center;
                background: white;
                height: 18px;
                font-weight: bold;
                color: #374151;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:0.5 #3b82f6, stop:1 #8b5cf6);
                border-radius: 6px;
                margin: 2px;
            }
        """)
        upload_layout.addWidget(self.progress_bar)
        
        # Прогресс текущего файла с красивым оформлением
        file_progress_group = QGroupBox("📊 Прогресс текущего файла")
        file_progress_group.setStyleSheet("""
            QGroupBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8f9fa);
                border: 2px solid #e0f2fe;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 5px;
            }
            QGroupBox::title {
                color: #0891b2;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        file_progress_layout = QVBoxLayout(file_progress_group)
        
        self.current_file_label = QLabel("📄 Файл не выбран")
        self.current_file_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                color: #0891b2;
                padding: 8px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f0f9ff, stop:1 #e0f7fa);
                border-radius: 6px;
                border: 1px solid #cffafe;
            }
        """)
        file_progress_layout.addWidget(self.current_file_label)
        
        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setVisible(False)
        self.file_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #e5e7eb;
                border-radius: 8px;
                text-align: center;
                background: white;
                height: 18px;
                font-weight: bold;
                color: #374151;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #06b6d4, stop:1 #0891b2);
                border-radius: 6px;
                margin: 2px;
            }
        """)
        file_progress_layout.addWidget(self.file_progress_bar)
        
        self.upload_speed_label = QLabel("⚡ Скорость: -")
        self.upload_speed_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 10px;
                font-weight: 600;
                padding: 4px 8px;
                background: #f9fafb;
                border-radius: 4px;
                border: 1px solid #e5e7eb;
            }
        """)
        file_progress_layout.addWidget(self.upload_speed_label)
        
        upload_layout.addWidget(file_progress_group)
        
        left_layout.addWidget(upload_group)
        
        # Секция логов с красивым оформлением
        log_group = QGroupBox("📋 Логи и статус")
        log_group.setStyleSheet("""
            QGroupBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8f9fa);
                border: 2px solid #f3e8ff;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                color: #7c3aed;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        log_layout = QVBoxLayout(log_group)
        log_layout.setSpacing(6)
        
        self.status_label = QLabel("✅ Готов к работе")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #059669;
                font-weight: bold;
                padding: 12px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ecfdf5, stop:1 #d1fae5);
                border: 1px solid #a7f3d0;
                border-radius: 8px;
                margin: 2px 0px;
            }
        """)
        log_layout.addWidget(self.status_label)
        
        self.log_output = QTextEdit()
        self.log_output.setMaximumHeight(80)  # Еще больше уменьшили высоту логов
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("""
            QTextEdit {
                border: 2px solid #e5e7eb;
                border-radius: 8px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #fafafa);
                padding: 10px;
                font-family: "Consolas", "Courier New", monospace;
                font-size: 10px;
                color: #374151;
            }
        """)
        log_layout.addWidget(self.log_output)
        
        left_layout.addWidget(log_group)
        
        # ПРАВАЯ ПАНЕЛЬ - Выбор чатов с красивым оформлением
        # Заголовок правой панели
        chat_title_widget = QWidget()
        chat_title_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6366f1, stop:1 #4f46e5);
                border-radius: 12px;
                margin: 0px 0px 10px 0px;
            }
        """)
        chat_title_layout = QVBoxLayout(chat_title_widget)
        chat_title_layout.setContentsMargins(15, 6, 15, 6)  # Еще больше уменьшили вертикальные отступы
        
        chat_title = QLabel("💬 Чаты и группы")
        chat_title.setAlignment(Qt.AlignCenter)
        chat_title.setFont(QFont("Segoe UI", 11, QFont.Bold))  # Еще больше уменьшили размер шрифта
        chat_title.setStyleSheet("color: white; background: transparent; margin: 0px;")
        chat_title_layout.addWidget(chat_title)
        
        filter_info = QLabel("(Исключены каналы и боты)")
        filter_info.setAlignment(Qt.AlignCenter)
        filter_info.setStyleSheet("color: rgba(255, 255, 255, 0.8); background: transparent; font-size: 10px; margin: 0px;")
        chat_title_layout.addWidget(filter_info)
        
        right_layout.addWidget(chat_title_widget)
        
        # Кнопка загрузки чатов
        self.load_chats_button = QPushButton("🔄 Обновить список чатов")
        self.load_chats_button.clicked.connect(self.load_chats)
        self.load_chats_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #6366f1, stop:1 #4f46e5);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 16px;
                font-weight: bold;
                font-size: 12px;
                min-height: 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #818cf8, stop:1 #6366f1);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4f46e5, stop:1 #3730a3);
            }
            QPushButton:disabled {
                background: #d1d5db;
                color: #9ca3af;
            }
        """)
        self.load_chats_button.setEnabled(False)
        right_layout.addWidget(self.load_chats_button)
        
        # Статус загрузки чатов
        self.chat_load_status = QLabel("Сначала авторизуйтесь")
        self.chat_load_status.setStyleSheet("""
            QLabel {
                color: #6b7280;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f9fafb, stop:1 #f3f4f6);
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 12px;
                margin: 5px 0px;
                font-size: 11px;
            }
        """)
        self.chat_load_status.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.chat_load_status)
        
        # Поиск по чатам с красивым дизайном
        search_layout = QHBoxLayout()
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 14px;
                padding: 8px 0px;
                margin-right: 8px;
            }
        """)
        search_layout.addWidget(search_icon)
        
        self.chat_search_input = QLineEdit()
        self.chat_search_input.setPlaceholderText("Введите название чата для поиска...")
        self.chat_search_input.textChanged.connect(self.filter_chats)
        self.chat_search_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #e5e7eb;
                border-radius: 10px;
                padding: 12px 16px;
                font-size: 12px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f9fafb);
                color: #374151;
            }
            QLineEdit:focus {
                border-color: #10b981;
                background: white;
            }
            QLineEdit:hover {
                border-color: #d1d5db;
            }
        """)
        search_layout.addWidget(self.chat_search_input)
        right_layout.addLayout(search_layout)
        
        # Список чатов с красивым дизайном  
        self.chat_list_widget = QListWidget()
        self.chat_list_widget.setMaximumHeight(200)  # Еще больше уменьшили высоту списка чатов
        self.chat_list_widget.setStyleSheet("""
            QListWidget {
                border: 2px solid #e5e7eb;
                border-radius: 12px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #fafafa);
                padding: 8px;
            }
            QListWidget::item {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 12px;
                margin: 3px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f9fafb);
                font-size: 12px;
                color: #374151;
            }
            QListWidget::item:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ecfdf5, stop:1 #d1fae5);
                border-color: #10b981;
                color: #047857;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #10b981, stop:1 #059669);
                color: white;
                border-color: #047857;
                font-weight: bold;
            }
        """)
        self.chat_list_widget.itemClicked.connect(self.on_chat_selected)
        right_layout.addWidget(self.chat_list_widget)
        
        # Выбранный чат с красивым дизайном
        selected_group = QGroupBox("✅ Выбранный чат")
        selected_group.setStyleSheet("""
            QGroupBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f0f9ff, stop:1 #e0f2fe);
                border: 2px solid #38bdf8;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                color: #0284c7;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        selected_layout = QVBoxLayout(selected_group)
        selected_layout.setSpacing(6)
        
        self.selected_chat_label = QLabel("💬 Чат не выбран")
        self.selected_chat_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8fafc);
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 12px;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        self.selected_chat_label.setWordWrap(True)
        selected_layout.addWidget(self.selected_chat_label)
        
        # Скрытое поле для ID чата (для совместимости)
        self.chat_input = QLineEdit()
        self.chat_input.setVisible(False)
        
        right_layout.addWidget(selected_group)
        right_layout.addStretch()
        
    def load_settings(self):
        """Загружает сохраненные настройки"""
        self.api_id_input.setText(str(self.settings.get("api_id", "")))
        self.api_hash_input.setText(self.settings.get("api_hash", ""))
        self.phone_input.setText(self.settings.get("phone", ""))
        self.folder_input.setText(self.settings.get("folder", ""))
        self.prefix_input.setText(self.settings.get("prefix_text", ""))  # ДОБАВЛЕНО: загрузка префикса
        
        # ИСПРАВЛЕНО: Не восстанавливаем выбранный чат при запуске
        # Пользователь должен заново выбрать чат каждый раз
        self.selected_chat_label.setText("Чат не выбран")
        self.selected_chat_label.setStyleSheet("color: #666; font-weight: bold; padding: 10px;")
        
        # Автоматически проверяем авторизацию
        if all([self.api_id_input.text(), self.api_hash_input.text(), self.phone_input.text()]):
            QTimer.singleShot(1000, self.check_authorization)
    
    def save_settings(self):
        """Сохраняет настройки"""
        try:
            api_id = int(self.api_id_input.text()) if self.api_id_input.text() else 0
        except ValueError:
            api_id = 0
            
        self.settings.set("api_id", api_id)
        self.settings.set("api_hash", self.api_hash_input.text())
        self.settings.set("phone", self.phone_input.text())
        self.settings.set("folder", self.folder_input.text())
        self.settings.set("prefix_text", self.prefix_input.text())  # ДОБАВЛЕНО: сохранение префикса
        
        # Сохраняем выбранный чат
        if hasattr(self, 'selected_chat_id') and self.selected_chat_id:
            self.settings.set("selected_chat_id", self.selected_chat_id)
            self.settings.set("selected_chat_name", getattr(self, 'selected_chat_name', ''))
    
    def log_message(self, message):
        """Добавляет сообщение в лог (снизу вверх)"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        # Вставляем новые сообщения в начало (снизу вверх)
        cursor = self.log_output.textCursor()
        cursor.movePosition(cursor.Start)
        cursor.insertText(log_entry + "\n")
        
        # Возвращаем курсор в начало, чтобы новые сообщения были видны
        cursor.movePosition(cursor.Start)
        self.log_output.setTextCursor(cursor)
        
        self.status_label.setText(message)
    
    def check_authorization(self):
        """Проверяет статус авторизации"""
        if not self.validate_api_settings():
            return
            
        self.log_message("Проверка авторизации...")
        self.check_auth_button.setEnabled(False)
        self.check_auth_button.setText("Проверяем...")
        
        # Останавливаем предыдущий поток если он существует
        if self.auth_thread and self.auth_thread.isRunning():
            self.auth_thread.quit()
            self.auth_thread.wait()
        
        # Используем отдельный класс для проверки
        self.auth_thread = TelegramAuthChecker(
            int(self.api_id_input.text()),
            self.api_hash_input.text(),
            self.phone_input.text()
        )
        self.auth_thread.step_completed.connect(self.on_auth_step)
        self.auth_thread.error_occurred.connect(self.on_auth_error)
        self.auth_thread.finished.connect(self.on_auth_thread_finished)
        self.auth_thread.start()
    
    def request_code(self):
        """Запрашивает код подтверждения и начинает полный цикл авторизации"""
        if not self.validate_api_settings():
            return
            
        self.log_message("Начинаем авторизацию...")
        self.get_code_button.setEnabled(False)
        self.get_code_button.setText("Авторизация...")
        
        # Останавливаем предыдущий поток если он существует
        if self.auth_thread and self.auth_thread.isRunning():
            self.auth_thread.quit()
            self.auth_thread.wait()
        
        # Создаем поток для полной авторизации
        self.auth_thread = TelegramAuth(
            int(self.api_id_input.text()),
            self.api_hash_input.text(),
            self.phone_input.text()
        )
        self.auth_thread.step_completed.connect(self.on_auth_step)
        self.auth_thread.error_occurred.connect(self.on_auth_error)
        self.auth_thread.finished.connect(self.on_auth_thread_finished)
        self.auth_thread.start()
    
    def confirm_code(self):
        """Отправляет введенный код в поток авторизации"""
        if not self.code_input.text():
            QMessageBox.warning(self, "Ошибка", "Введите код подтверждения!")
            return
            
        if not self.auth_thread or not self.auth_thread.isRunning():
            QMessageBox.warning(self, "Ошибка", "Нет активного процесса авторизации!")
            return
        
        self.log_message("Отправляем код для подтверждения...")
        self.confirm_code_button.setEnabled(False)
        self.confirm_code_button.setText("Подтверждаем...")
        
        # ИСПРАВЛЕНО: Всегда устанавливаем пароль 2FA, даже если поле пустое
        # Это позволяет обработать случай, когда пользователь вводит пароль после получения кода
        password_2fa = self.password_input.text().strip() if self.password_input.text() else None
        if password_2fa:
            self.auth_thread.set_password(password_2fa)
            self.log_message("Пароль 2FA установлен для авторизации")
        
        # Отправляем код в поток
        self.auth_thread.set_code(self.code_input.text())
    
    def reset_authorization(self):
        """Сбрасывает авторизацию"""
        # ИСПРАВЛЕНО: Безопасное удаление файла сессии с повторными попытками
        session_file = "uploader_session.session"
        
        # Сначала останавливаем все активные потоки
        if self.auth_thread and self.auth_thread.isRunning():
            self.log_message("Останавливаем процесс авторизации...")
            self.auth_thread.quit()
            self.auth_thread.wait(2000)  # Ждем до 2 секунд
        
        if self.upload_thread and self.upload_thread.isRunning():
            self.log_message("Останавливаем загрузку...")
            self.upload_thread.stop_upload()
            self.upload_thread.wait(3000)  # Ждем до 3 секунд
        
        if self.chat_loader_thread and self.chat_loader_thread.isRunning():
            self.log_message("Останавливаем загрузку чатов...")
            self.chat_loader_thread.quit()
            self.chat_loader_thread.wait(2000)  # Ждем до 2 секунд
        
        # Пытаемся удалить файл сессии несколько раз
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                if os.path.exists(session_file):
                    os.remove(session_file)
                    self.log_message("✅ Файл сессии удален")
                    break
            except PermissionError as e:
                if attempt < max_attempts - 1:
                    self.log_message(f"⏳ Попытка {attempt + 1}: файл занят, ждем...")
                    import time
                    time.sleep(1)  # Ждем 1 секунду между попытками
                else:
                    self.log_message("⚠️ Не удалось удалить файл сессии - возможно он используется")
                    QMessageBox.warning(self, "Предупреждение", 
                        f"Не удалось удалить файл сессии:\n{session_file}\n\n"
                        f"Файл может быть занят другим процессом.\n"
                        f"Попробуйте закрыть программу полностью и запустить заново.")
                    break
            except Exception as e:
                self.log_message(f"❌ Ошибка при удалении файла сессии: {e}")
                break
        
        # Сбрасываем состояние UI
        self.phone_code_hash = None
        self.update_auth_ui("not_authorized")
        
        # Очищаем список чатов
        self.chat_list_widget.clear()
        self.selected_chat_label.setText("Чат не выбран")
        self.selected_chat_label.setStyleSheet("color: #666; font-weight: bold; padding: 10px;")
        self.chat_load_status.setText("Сначала авторизуйтесь")
        
        self.log_message("🔄 Авторизация сброшена")
        QMessageBox.information(self, "Сброс", "Авторизация сброшена!\n\nЕсли остались проблемы, перезапустите программу.")
    
    def on_auth_step(self, step, status, data):
        """Обработка шагов авторизации"""
        print(f"[UI] Auth step: {step}, status: {status}, data: {data}")
        
        if step == "code_sent":
            self.phone_code_hash = data
            self.log_message("✅ Код отправлен! Введите код в течение 2 минут!")
            self.update_auth_ui("code_sent")
            
            # Запускаем таймер для напоминания о времени истечения кода
            QTimer.singleShot(90000, lambda: self.log_message("⏰ Осталось 30 секунд для ввода кода!"))
            QTimer.singleShot(110000, lambda: self.log_message("⚠️ Код скоро истечет! Введите быстрее!"))
            
        elif step == "auth_success":
            self.log_message(f"✅ Авторизация успешна: {data}")
            self.update_auth_ui("authorized", data)
            self.save_settings()
            
            # ИСПРАВЛЕНО: Автоматически загружаем список чатов после успешной авторизации
            self.log_message("📋 Автоматически загружаем список чатов...")
            QTimer.singleShot(1000, self.load_chats)  # Запускаем через 1 секунду
            
        elif step == "need_password":
            self.log_message("🔐 Требуется пароль двухфакторной аутентификации")
            QMessageBox.information(self, "2FA", 
                "Требуется пароль двухфакторной аутентификации.\n\n"
                "Введите пароль 2FA в соответствующее поле и нажмите 'Подтвердить' снова.")
            self.confirm_code_button.setEnabled(True)
            self.confirm_code_button.setText("Подтвердить")
            self.password_input.setFocus()  # Фокус на поле пароля
            
        elif step == "already_authorized":
            self.log_message(f"✅ Уже авторизован: {data}")
            self.update_auth_ui("authorized", data)
            
            # ИСПРАВЛЕНО: Автоматически загружаем список чатов, если уже авторизован
            self.log_message("📋 Автоматически загружаем список чатов...")
            QTimer.singleShot(1000, self.load_chats)  # Запускаем через 1 секунду
            
        elif step == "not_authorized":
            self.log_message("❌ Требуется авторизация")
            self.update_auth_ui("not_authorized")
    
    def on_auth_error(self, error):
        """Обработка ошибок авторизации"""
        error_msg = str(error)
        
        if "PHONE_CODE_EXPIRED" in error_msg:
            self.log_message("❌ Код истек! Получите новый код.")
            QMessageBox.warning(self, "Код истек", 
                "Код подтверждения истек!\n\n"
                "Коды действуют только 2 минуты.\n"
                "Нажмите 'Получить код' для получения нового кода.")
            # Сбрасываем состояние для получения нового кода
            self.phone_code_hash = None
            self.update_auth_ui("not_authorized")
        elif "PHONE_CODE_INVALID" in error_msg:
            self.log_message("❌ Неверный код! Проверьте правильность ввода.")
            QMessageBox.warning(self, "Неверный код", 
                "Введен неверный код!\n\n"
                "Проверьте:\n"
                "• Правильность введенного кода\n"
                "• Что код не истек\n"
                "• Что вы используете последний полученный код")
            # Возвращаем возможность ввести код заново
            self.confirm_code_button.setEnabled(True)
            self.confirm_code_button.setText("Подтвердить")
            self.code_input.clear()
            self.code_input.setFocus()
        elif "FLOOD_WAIT" in error_msg:
            import re
            wait_time = re.search(r'(\d+)', error_msg)
            if wait_time:
                seconds = int(wait_time.group(1))
                minutes = seconds // 60
                self.log_message(f"❌ Слишком много попыток! Подождите {minutes} минут.")
                QMessageBox.warning(self, "Flood лимит", 
                    f"Слишком много попыток авторизации!\n\n"
                    f"Подождите {minutes} минут перед следующей попыткой.")
            else:
                self.log_message("❌ Слишком много попыток! Подождите некоторое время.")
                QMessageBox.warning(self, "Flood лимит", 
                    "Слишком много попыток!\n"
                    "Подождите некоторое время перед следующей попыткой.")
            self.phone_code_hash = None
            self.update_auth_ui("not_authorized")
        else:
            self.log_message(f"❌ Ошибка: {error}")
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка:\n\n{error}")
            self.phone_code_hash = None
            self.update_auth_ui("not_authorized")
        
        self.reset_auth_buttons()
    
    def on_auth_thread_finished(self):
        """Обработчик завершения потока авторизации"""
        print("[UI] Auth thread finished")
        # Поток завершился, можно освободить ресурсы
        if self.auth_thread:
            self.auth_thread.deleteLater()
            self.auth_thread = None
    
    def update_auth_ui(self, state, user_info=""):
        """Обновляет UI в зависимости от состояния авторизации"""
        if state == "not_authorized":
            self.auth_status_label.setText("Статус: ❌ Не авторизован")
            self.auth_status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            self.get_code_button.setEnabled(True)
            self.get_code_button.setText("Получить код")
            self.code_input.setEnabled(False)
            self.confirm_code_button.setEnabled(False)
            self.start_button.setEnabled(False)
            self.load_chats_button.setEnabled(False)
            self.chat_load_status.setText("Сначала авторизуйтесь")
            
        elif state == "code_sent":
            self.auth_status_label.setText("Статус: 📱 Код отправлен")
            self.auth_status_label.setStyleSheet("color: #FF9800; font-weight: bold;")
            self.get_code_button.setEnabled(False)
            self.get_code_button.setText("Код отправлен ✓")
            self.code_input.setEnabled(True)
            self.code_input.setFocus()
            self.confirm_code_button.setEnabled(True)
            
        elif state == "authorized":
            self.auth_status_label.setText(f"Статус: ✅ Авторизован как {user_info}")
            self.auth_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.get_code_button.setEnabled(False)
            self.get_code_button.setText("Не требуется")
            self.code_input.setEnabled(False)
            self.confirm_code_button.setEnabled(False)
            self.start_button.setEnabled(True)
            self.load_chats_button.setEnabled(True)
            self.chat_load_status.setText("Готов к загрузке чатов")
        
        self.reset_auth_buttons()
    
    def reset_auth_buttons(self):
        """Сбрасывает состояние кнопок авторизации"""
        self.check_auth_button.setEnabled(True)
        self.check_auth_button.setText("Проверить авторизацию")
        
        if self.confirm_code_button.isEnabled():
            self.confirm_code_button.setText("Подтвердить")
        
        if self.get_code_button.isEnabled():
            self.get_code_button.setText("Получить код")
    
    def validate_api_settings(self):
        """Проверяет настройки API"""
        if not self.api_id_input.text():
            QMessageBox.warning(self, "Ошибка", "Введите API ID!")
            return False
        if not self.api_hash_input.text():
            QMessageBox.warning(self, "Ошибка", "Введите API Hash!")
            return False
        if not self.phone_input.text():
            QMessageBox.warning(self, "Ошибка", "Введите номер телефона!")
            return False
        try:
            int(self.api_id_input.text())
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "API ID должен быть числом!")
            return False
        return True
    
    def browse_folder(self):
        """Выбор папки с видео"""
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку с видео")
        if folder:
            self.folder_input.setText(folder)
            self.save_settings()
    
    def on_prefix_changed(self):
        """Автосохранение префикса при изменении"""
        self.save_settings()
    
    def load_chats(self):
        """Загружает список чатов"""
        if not self.validate_api_settings():
            return
            
        self.log_message("📋 Загружаем список чатов...")
        self.load_chats_button.setEnabled(False)
        self.load_chats_button.setText("🔄 Загружаем...")
        self.chat_load_status.setText("Загружаем чаты...")
        
        # Останавливаем предыдущий поток если он существует
        if self.chat_loader_thread and self.chat_loader_thread.isRunning():
            self.chat_loader_thread.quit()
            self.chat_loader_thread.wait()
        
        self.chat_loader_thread = ChatLoader(
            int(self.api_id_input.text()),
            self.api_hash_input.text()
        )
        self.chat_loader_thread.chats_loaded.connect(self.on_chats_loaded)
        self.chat_loader_thread.error_occurred.connect(self.on_chat_load_error)
        self.chat_loader_thread.progress_updated.connect(self.on_chat_load_progress)
        self.chat_loader_thread.finished.connect(self.on_chat_load_finished)
        self.chat_loader_thread.start()
    
    def on_chats_loaded(self, chats):
        """Обработка загруженных чатов"""
        self.chats_list = chats
        self.update_chat_list()  # ИСПРАВЛЕНО: используем update_chat_list вместо populate_chat_list
        self.log_message(f"✅ Загружено {len(chats)} чатов")
        self.chat_load_status.setText(f"Загружено {len(chats)} чатов")
    
    def on_chat_load_error(self, error):
        """Обработка ошибки загрузки чатов"""
        self.log_message(f"❌ Ошибка загрузки чатов: {error}")
        self.chat_load_status.setText("Ошибка загрузки")
        QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить чаты:\n\n{error}")
    
    def on_chat_load_progress(self, status):
        """Обновление прогресса загрузки чатов"""
        self.chat_load_status.setText(status)
    
    def on_chat_load_finished(self):
        """Завершение загрузки чатов"""
        self.load_chats_button.setEnabled(True)
        self.load_chats_button.setText("🔄 Обновить список чатов")  # ИСПРАВЛЕНО: правильный текст кнопки
        if self.chat_loader_thread:
            self.chat_loader_thread.deleteLater()
            self.chat_loader_thread = None
    
    def update_chat_list(self):
        """Обновляет список чатов с учетом поискового фильтра"""
        if not hasattr(self, 'chats_list'):
            return
            
        self.chat_list_widget.clear()
        search_text = self.chat_search_input.text().lower()
        
        for chat in self.chats_list:
            if search_text and search_text not in chat['name'].lower():
                continue
                
            item = QListWidgetItem(chat['name'])
            item.setData(Qt.UserRole, chat)
            
            # Цветовая индикация для чатов с ограничениями
            if not chat['can_send']:
                item.setBackground(Qt.lightGray)
                
            self.chat_list_widget.addItem(item)
    
    def populate_chat_list(self, chats):
        """Заполняет список чатов"""
        self.chat_list_widget.clear()
        for chat in chats:
            item = QListWidgetItem(chat['name'])
            item.setData(Qt.UserRole, chat)  # Сохраняем данные чата
            
            # Цветовая кодировка
            if not chat['can_send']:
                item.setBackground(Qt.lightGray)
                item.setToolTip("В этот чат нельзя отправлять сообщения")
            
            self.chat_list_widget.addItem(item)
    
    def filter_chats(self):
        """Фильтрует чаты по поисковому запросу"""
        # ИСПРАВЛЕНО: используем update_chat_list для более простой фильтрации
        self.update_chat_list()
    
    def on_chat_selected(self, item):
        """Обработка выбора чата"""
        chat_data = item.data(Qt.UserRole)
        
        if not chat_data['can_send']:
            QMessageBox.warning(self, "Нельзя отправить", 
                "В выбранный чат нельзя отправлять сообщения!\n\n"
                "Выберите другой чат.")
            return
        
        chat_id = chat_data['id']
        chat_name = chat_data['name']
        
        # Сохраняем выбранный чат
        self.selected_chat_id = chat_id
        self.selected_chat_name = chat_name
        self.chat_input.setText(str(chat_id))
        
        # Дополнительное логирование для отладки
        print(f"[CHAT_SELECT] Выбран чат: {chat_name}")
        print(f"[CHAT_SELECT] ID чата: {chat_id} (тип: {type(chat_id)})")
        print(f"[CHAT_SELECT] Установлен в поле: {self.chat_input.text()}")
        
        # Обновляем UI
        self.selected_chat_label.setText(f"✅ {chat_name}")
        self.selected_chat_label.setStyleSheet("color: #4CAF50; font-weight: bold; padding: 10px;")
        
        self.log_message(f"📋 Выбран чат: {chat_name} (ID: {chat_id})")
        self.save_settings()
    
    def on_file_progress(self, filename, percentage, speed):
        """Обработка прогресса загрузки отдельного файла"""
        self.current_file_label.setText(f"Загружается: {filename}")
        self.file_progress_bar.setValue(percentage)
        self.upload_speed_label.setText(f"Скорость: {speed} | {percentage}%")
        
        if not self.file_progress_bar.isVisible():
            self.file_progress_bar.setVisible(True)
    
    def start_upload(self):
        """Начинает загрузку видео"""
        if not self.folder_input.text():
            QMessageBox.warning(self, "Ошибка", "Выберите папку с видео!")
            return
        if not self.chat_input.text():
            QMessageBox.warning(self, "Ошибка", "Выберите чат для отправки!\n\nНажмите 'Загрузить список чатов' и выберите чат из списка.")
            return
        
        try:
            delay = int(self.delay_input.text()) if self.delay_input.text() else 2
        except ValueError:
            delay = 2
        
        # Определяем количество параллельных потоков
        speed_setting = self.speed_combo.currentIndex()
        if speed_setting == 0:  # Обычная
            max_concurrent = 1
        elif speed_setting == 1:  # Быстрая
            max_concurrent = 4
        else:  # Максимальная
            max_concurrent = 8
        
        self.log_message(f"Начинаем загрузку видео (режим: {self.speed_combo.currentText()})...")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Показываем и сбрасываем прогресс файла
        self.file_progress_bar.setVisible(True)
        self.file_progress_bar.setValue(0)
        self.current_file_label.setText("Подготовка к загрузке...")
        self.upload_speed_label.setText("Скорость: -")
        
        self.upload_thread = VideoUploader(
            int(self.api_id_input.text()),
            self.api_hash_input.text(),
            self.chat_input.text(),
            self.folder_input.text(),
            delay,
            max_concurrent,  # Передаем настройки производительности
            self.prefix_input.text()  # ДОБАВЛЕНО: передаем префикс текста
        )
        
        self.upload_thread.progress_updated.connect(self.progress_bar.setValue)
        self.upload_thread.status_updated.connect(self.log_message)
        self.upload_thread.file_uploaded.connect(self.log_message)
        self.upload_thread.file_progress.connect(self.on_file_progress)
        self.upload_thread.finished.connect(self.on_upload_finished)
        self.upload_thread.start()
    
    def stop_upload(self):
        """Останавливает загрузку"""
        if self.upload_thread and self.upload_thread.isRunning():
            self.log_message("🛑 Останавливаем загрузку...")
            self.stop_button.setEnabled(False)  # Временно отключаем кнопку
            self.stop_button.setText("Останавливаем...")
            
            # ИСПРАВЛЕНО: Остановка без блокировки интерфейса
            try:
                # Устанавливаем флаг остановки в потоке
                self.upload_thread.stop_upload()
                
                # Ждем завершения потока в неблокирующем режиме
                def check_thread_finished():
                    if not self.upload_thread.isRunning():
                        self.log_message("✅ Загрузка остановлена")
                        self.reset_ui_after_stop()
                        return
                    
                    # Проверяем снова через 100ms
                    QTimer.singleShot(100, check_thread_finished)
                
                # Начинаем проверку
                check_thread_finished()
                
                # Таймаут для принудительной остановки (10 секунд)
                def force_stop():
                    if self.upload_thread and self.upload_thread.isRunning():
                        self.log_message("⚠️ Принудительная остановка потока")
                        self.upload_thread.terminate()
                        self.upload_thread.wait(1000)  # Ждем до 1 секунды
                        self.reset_ui_after_stop()
                
                QTimer.singleShot(10000, force_stop)  # Принудительная остановка через 10 сек
                
            except Exception as e:
                self.log_message(f"❌ Ошибка при остановке: {e}")
                self.reset_ui_after_stop()
        else:
            self.log_message("⚠️ Загрузка не активна")
    
    def reset_ui_after_stop(self):
        """Сбрасывает UI после остановки загрузки"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.stop_button.setText("Остановить")
        self.progress_bar.setVisible(False)
        self.file_progress_bar.setVisible(False)
        self.current_file_label.setText("Файл не выбран")
        self.upload_speed_label.setText("Скорость: -")
        self.status_label.setText("Готов к работе")
    
    def on_upload_finished(self, success, message):
        """Обработка завершения загрузки"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        # Скрываем прогресс файла
        self.file_progress_bar.setVisible(False)
        self.current_file_label.setText("Загрузка завершена")
        self.upload_speed_label.setText("Скорость: -")
        
        if success:
            self.log_message(f"✅ {message}")
            QMessageBox.information(self, "Готово", message)
        else:
            self.log_message(f"❌ {message}")
            QMessageBox.critical(self, "Ошибка", message)
    
    def closeEvent(self, event):
        """Обработка закрытия приложения"""
        print("[UI] Closing application...")
        
        # Останавливаем все активные потоки с принудительным завершением
        threads_stopped = True
        
        if self.auth_thread and self.auth_thread.isRunning():
            print("[UI] Stopping auth thread...")
            try:
                self.auth_thread.quit()
                if not self.auth_thread.wait(2000):  # Ждем 2 секунды
                    print("[UI] Force terminating auth thread...")
                    self.auth_thread.terminate()
                    self.auth_thread.wait(1000)
            except Exception as e:
                print(f"[UI] Error stopping auth thread: {e}")
                threads_stopped = False
            
        if self.upload_thread and self.upload_thread.isRunning():
            print("[UI] Stopping upload thread...")
            try:
                self.upload_thread.stop_upload()
                self.upload_thread.quit()
                if not self.upload_thread.wait(3000):  # Ждем 3 секунды
                    print("[UI] Force terminating upload thread...")
                    self.upload_thread.terminate()
                    self.upload_thread.wait(1000)
            except Exception as e:
                print(f"[UI] Error stopping upload thread: {e}")
                threads_stopped = False
        
        if self.chat_loader_thread and self.chat_loader_thread.isRunning():
            print("[UI] Stopping chat loader thread...")
            try:
                self.chat_loader_thread.quit()
                if not self.chat_loader_thread.wait(2000):  # Ждем 2 секунды
                    print("[UI] Force terminating chat loader thread...")
                    self.chat_loader_thread.terminate()
                    self.chat_loader_thread.wait(1000)
            except Exception as e:
                print(f"[UI] Error stopping chat loader thread: {e}")
                threads_stopped = False
        
        # Сохраняем настройки
        try:
            self.save_settings()
        except Exception as e:
            print(f"[UI] Error saving settings: {e}")
        
        if threads_stopped:
            print("[UI] All threads stopped successfully")
        else:
            print("[UI] Some threads may not have stopped properly")
        
        print("[UI] Application closed")
        event.accept()


def main():
    app = None
    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        
        # Добавляем обработчик исключений
        def exception_handler(exc_type, exc_value, exc_traceback):
            print(f"Необработанное исключение: {exc_type.__name__}: {exc_value}")
            print(f"Traceback: {''.join(traceback.format_tb(exc_traceback))}")
            
            # Показываем пользователю сообщение об ошибке
            try:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Critical)
                msg.setWindowTitle("Ошибка приложения")
                msg.setText(f"Произошла ошибка:\n\n{exc_type.__name__}: {exc_value}\n\nПриложение будет закрыто.")
                msg.exec_()
            except:
                pass
        
        sys.excepthook = exception_handler
        
        window = MainWindow()
        window.show()
        
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"Критическая ошибка при запуске: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        try:
            # Проверяем, есть ли уже экземпляр приложения
            if not app and not QApplication.instance():
                app = QApplication(sys.argv)
            
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Критическая ошибка")
            msg.setText(f"Не удалось запустить приложение:\n\n{e}")
            msg.exec_()
        except:
            pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
