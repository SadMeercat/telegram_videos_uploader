"""
Модуль для загрузки видео в Telegram
"""
import os
import asyncio
import time
from typing import Optional, List
from PyQt5.QtCore import QThread, pyqtSignal
from pyrogram import Client
from utils.video_utils import get_video_metadata


class VideoUploader(QThread):
    """Поток для загрузки видео"""
    
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    file_uploaded = pyqtSignal(str)
    file_progress = pyqtSignal(str, int, str)  # filename, percentage, speed
    finished = pyqtSignal(bool, str)
    
    def __init__(self, api_id: int, api_hash: str, chat_id: int, video_folder: str, 
                 delay_seconds: int = 1, max_concurrent: int = 4, prefix_text: str = ""):
        """
        Инициализация загрузчика видео
        
        Args:
            api_id: API ID Telegram
            api_hash: API Hash Telegram
            chat_id: ID чата для загрузки
            video_folder: Папка с видео файлами
            delay_seconds: Задержка между загрузками
            max_concurrent: Максимальное количество параллельных загрузок
            prefix_text: Префикс для названий файлов
        """
        super().__init__()
        self.api_id = api_id
        self.api_hash = api_hash
        self.chat_id = chat_id
        self.video_folder = video_folder
        self.delay_seconds = delay_seconds
        self.max_concurrent = max_concurrent
        self.prefix_text = prefix_text
        self.should_stop = False
        self.current_file = ""
        self.start_time: Optional[float] = None
    
    def progress_callback(self, current: int, total: int) -> None:
        """
        Callback для отслеживания прогресса загрузки файла
        
        Args:
            current: Текущее количество переданных байт
            total: Общее количество байт
        """
        if self.should_stop:
            raise Exception("Upload cancelled by user")
            
        percentage = int((current / total) * 100) if total > 0 else 0
        
        # Расширенная статистика скорости
        if self.start_time:
            elapsed_time = time.time() - self.start_time
            if elapsed_time > 0:
                speed_bps = current / elapsed_time  # байт в секунду
                
                # Форматируем скорость
                if speed_bps >= 1024 * 1024:  # МБ/с
                    speed_str = f"{speed_bps / (1024 * 1024):.1f} МБ/с"
                elif speed_bps >= 1024:  # КБ/с
                    speed_str = f"{speed_bps / 1024:.1f} КБ/с"
                else:  # Б/с
                    speed_str = f"{speed_bps:.0f} Б/с"
                
                # Оценка времени до завершения
                if speed_bps > 0:
                    remaining_bytes = total - current
                    eta_seconds = remaining_bytes / speed_bps
                    eta_minutes = int(eta_seconds // 60)
                    eta_seconds = int(eta_seconds % 60)
                    
                    if eta_minutes > 0:
                        speed_str += f" (осталось: {eta_minutes}:{eta_seconds:02d})"
                    else:
                        speed_str += f" (осталось: {eta_seconds}с)"
            else:
                speed_str = "Вычисляем..."
        else:
            speed_str = "Начинаем..."
        
        # Отправляем сигнал с прогрессом
        self.file_progress.emit(self.current_file, percentage, speed_str)
    
    def stop_upload(self) -> None:
        """Останавливает загрузку видео"""
        self.should_stop = True
        print(f"[UPLOAD] Флаг остановки установлен: should_stop = {self.should_stop}")
        
        # Прерываем текущую операцию если возможно
        if hasattr(self, '_current_upload_task'):
            self._current_upload_task.cancel()
    
    def run(self) -> None:
        """Запуск потока загрузки"""
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.upload_videos())
        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            loop.close()
    
    async def upload_videos(self) -> None:
        """Основная функция загрузки видео"""
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
                    
                # Принудительно устанавливаем информацию о пользователе в клиенте
                # Это исправляет ошибку 'NoneType' object has no attribute 'is_premium'
                client.me = me
                print(f"[UPLOAD] Установлена информация о пользователе в клиенте")
                
                # Проверяем премиум статус для больших файлов
                is_premium = getattr(me, 'is_premium', False)
                print(f"[UPLOAD] Авторизован как: {me.first_name} (ID: {me.id})")
                if is_premium:
                    print(f"[UPLOAD] ✅ Премиум аккаунт - поддержка файлов до 4 ГБ")
                else:
                    print(f"[UPLOAD] ⚠️ Обычный аккаунт - лимит файлов 2 ГБ")
                
            except Exception as e:
                raise Exception(f"Ошибка авторизации: {e}")
            
            # Обновляем кэш пиров для корректной работы с чатами
            await self._update_peers_cache(client)
            
            # Получаем список видео файлов
            video_files = self._get_video_files()
            
            if not video_files:
                raise Exception("В папке нет видео файлов")
            
            total_files = len(video_files)
            uploaded_count = 0
            failed_count = 0
            
            self.status_updated.emit(f"Найдено {total_files} видео файлов")
            
            # Загружаем файлы
            for i, video_file in enumerate(video_files):
                if self.should_stop:
                    break
                
                try:
                    self.current_file = os.path.basename(video_file)
                    self.start_time = time.time()
                    
                    self.status_updated.emit(f"Загружаем {i+1}/{total_files}: {self.current_file}")
                    
                    # Получаем метаданные видео
                    metadata = get_video_metadata(video_file)
                    
                    # Формируем название файла с префиксом
                    filename = self.current_file
                    if self.prefix_text:
                        filename = f"{self.prefix_text} {filename}"
                    
                    # Загружаем видео
                    await self._upload_single_video(client, video_file, filename, metadata)
                    
                    uploaded_count += 1
                    self.file_uploaded.emit(self.current_file)
                    
                    # Обновляем общий прогресс
                    overall_progress = int((i + 1) / total_files * 100)
                    self.progress_updated.emit(overall_progress)
                    
                    # Задержка между загрузками
                    if i < total_files - 1 and self.delay_seconds > 0:
                        await asyncio.sleep(self.delay_seconds)
                    
                except Exception as e:
                    print(f"[UPLOAD] Ошибка загрузки {self.current_file}: {e}")
                    failed_count += 1
                    
            # Итоговый результат
            if self.should_stop:
                message = f"Загрузка остановлена. Загружено: {uploaded_count}, Ошибок: {failed_count}"
                self.finished.emit(False, message)
            else:
                message = f"Загрузка завершена. Успешно: {uploaded_count}, Ошибок: {failed_count}"
                success = failed_count == 0
                self.finished.emit(success, message)
                
        except Exception as e:
            print(f"[UPLOAD] Критическая ошибка: {e}")
            self.finished.emit(False, str(e))
        finally:
            if client:
                await client.disconnect()
    
    def _get_video_files(self) -> List[str]:
        """
        Получает список видео файлов из папки
        
        Returns:
            Список путей к видео файлам
        """
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        video_files = []
        
        try:
            for file in os.listdir(self.video_folder):
                file_path = os.path.join(self.video_folder, file)
                if (os.path.isfile(file_path) and 
                    os.path.splitext(file)[1].lower() in video_extensions):
                    video_files.append(file_path)
        except Exception as e:
            print(f"[UPLOAD] Ошибка чтения папки: {e}")
            
        return sorted(video_files)
    
    async def _upload_single_video(self, client: Client, video_path: str, 
                                  filename: str, metadata: dict) -> None:
        """
        Загружает один видео файл
        
        Args:
            client: Клиент Telegram
            video_path: Путь к видео файлу
            filename: Имя файла для отправки
            metadata: Метаданные видео
        """
        try:
            # Определяем параметры видео
            duration = metadata.get('duration')
            width = metadata.get('width')
            height = metadata.get('height')
            
            # Создаем задачу загрузки
            self._current_upload_task = asyncio.create_task(
                client.send_video(
                    chat_id=self.chat_id,
                    video=video_path,
                    caption=filename,
                    duration=duration,
                    width=width,
                    height=height,
                    progress=self.progress_callback,
                    supports_streaming=True
                )
            )
            
            # Ждем завершения загрузки
            await self._current_upload_task
            
            print(f"[UPLOAD] Успешно загружен: {filename}")
            
        except asyncio.CancelledError:
            print(f"[UPLOAD] Загрузка отменена: {filename}")
            raise
        except Exception as e:
            print(f"[UPLOAD] Ошибка загрузки {filename}: {e}")
            raise
    
    async def _update_peers_cache(self, client) -> None:
        """Обновляет кэш пиров для корректной работы с чатами"""
        try:
            print(f"[UPLOAD] Обновляем кэш пиров...")
            
            # Ищем целевой чат в диалогах для обновления кэша
            dialogs_count = 0
            target_chat_found = False
            
            async for dialog in client.get_dialogs(limit=100):
                dialogs_count += 1
                if dialog.chat.id == int(self.chat_id):
                    print(f"[UPLOAD] Найден целевой чат: {dialog.chat.title or dialog.chat.first_name} (ID: {dialog.chat.id})")
                    target_chat_found = True
            
            print(f"[UPLOAD] Загружено {dialogs_count} диалогов, кэш пиров обновлен")
            
            if not target_chat_found:
                print(f"[UPLOAD] ⚠️ Целевой чат с ID {self.chat_id} не найден в диалогах")
                
        except Exception as e:
            print(f"[UPLOAD] Ошибка обновления кэша пиров: {e}")
            # Не прерываем загрузку из-за этой ошибки