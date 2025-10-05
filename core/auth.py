"""
Модуль для авторизации в Telegram
"""
import asyncio
import threading
from typing import Optional
from PyQt5.QtCore import QThread, pyqtSignal
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid


class TelegramAuth(QThread):
    """Поток для авторизации в Telegram"""
    
    step_completed = pyqtSignal(str, str, str)  # step, status, data
    error_occurred = pyqtSignal(str)
    code_requested = pyqtSignal()  # Сигнал для запроса кода от пользователя
    
    def __init__(self, api_id: int, api_hash: str, phone: str):
        """
        Инициализация авторизации
        
        Args:
            api_id: API ID Telegram
            api_hash: API Hash Telegram  
            phone: Номер телефона
        """
        super().__init__()
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.user_code: Optional[str] = None
        self.user_password: Optional[str] = None
        self.code_event: Optional[threading.Event] = None
        self.client: Optional[Client] = None
        self.phone_code_hash: Optional[str] = None
        
    def set_code(self, code: str) -> None:
        """
        Устанавливает код и сигнализирует потоку продолжить
        
        Args:
            code: Код подтверждения
        """
        self.user_code = code
        if self.code_event:
            self.code_event.set()
    
    def set_password(self, password: str) -> None:
        """
        Устанавливает пароль 2FA
        
        Args:
            password: Пароль двухфакторной аутентификации
        """
        self.user_password = password
        
    def run(self) -> None:
        """Запуск потока авторизации"""
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.full_authorization_flow())
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            loop.close()
    
    async def full_authorization_flow(self) -> None:
        """Полный цикл авторизации в одном потоке"""
        try:
            print(f"[AUTH] Начинаем авторизацию для {self.phone}")
            
            self.client = Client(
                "uploader_session",
                api_id=self.api_id,
                api_hash=self.api_hash,
                phone_number=self.phone
            )
            
            await self.client.connect()
            
            # Проверяем, авторизованы ли мы уже
            if await self.client.get_me():
                print("[AUTH] Уже авторизованы!")
                user = await self.client.get_me()
                self.step_completed.emit("already_authorized", "success", 
                                       f"{user.first_name} {user.last_name or ''}")
                return
                
        except Exception as e:
            print(f"[AUTH] Ошибка проверки авторизации: {e}")
            
        try:
            # Отправляем код
            sent_code = await self.client.send_code(self.phone)
            self.phone_code_hash = sent_code.phone_code_hash
            print(f"[AUTH] Код отправлен на {self.phone}")
            
            self.step_completed.emit("code_sent", "success", "Код отправлен")
            
            # Ждем код от пользователя
            await self.wait_for_user_code()
            
            # Подтверждаем код
            await self.confirm_code_in_same_session()
            
        except Exception as e:
            print(f"[AUTH] Ошибка авторизации: {e}")
            self.error_occurred.emit(str(e))
        finally:
            if self.client:
                await self.client.disconnect()
    
    async def wait_for_user_code(self) -> None:
        """Ждем ввода кода от пользователя"""
        print("[AUTH] Ждем ввод кода от пользователя...")
        self.code_requested.emit()
        
        self.code_event = threading.Event()
        
        # Ждем пока пользователь не введет код (с таймаутом 120 секунд)
        loop = asyncio.get_event_loop()
        
        def wait_for_code():
            return self.code_event.wait(timeout=120)
        
        # Запускаем ожидание в отдельном потоке, чтобы не блокировать event loop
        code_received = await loop.run_in_executor(None, wait_for_code)
        
        if not code_received:
            raise Exception("Время ожидания кода истекло")
            
        print(f"[AUTH] Получен код от пользователя: {self.user_code}")
    
    async def confirm_code_in_same_session(self) -> None:
        """Подтверждаем код в той же сессии"""
        try:
            user = await self.client.sign_in(
                phone_number=self.phone,
                phone_code_hash=self.phone_code_hash,
                phone_code=self.user_code
            )
            
            print(f"[AUTH] Успешная авторизация для {user.first_name}")
            self.step_completed.emit("auth_success", "success", 
                                   f"{user.first_name} {user.last_name or ''}")
            
        except SessionPasswordNeeded:
            print("[AUTH] Требуется пароль 2FA")
            self.step_completed.emit("need_password", "info", "Требуется пароль 2FA")
            
            if self.user_password:
                try:
                    user = await self.client.check_password(self.user_password)
                    print(f"[AUTH] Успешная авторизация с 2FA для {user.first_name}")
                    self.step_completed.emit("auth_success", "success", 
                                           f"{user.first_name} {user.last_name or ''}")
                except Exception as e:
                    raise Exception(f"Неверный пароль 2FA: {e}")
            else:
                raise Exception("Требуется пароль 2FA")
                
        except PhoneCodeInvalid:
            raise Exception("PHONE_CODE_INVALID: Неверный код")
        except Exception as e:
            raise Exception(f"Ошибка подтверждения кода: {e}")


class TelegramAuthChecker(QThread):
    """Отдельный поток только для проверки авторизации"""
    
    step_completed = pyqtSignal(str, str, str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, api_id: int, api_hash: str, phone: str):
        """
        Инициализация проверки авторизации
        
        Args:
            api_id: API ID Telegram
            api_hash: API Hash Telegram
            phone: Номер телефона
        """
        super().__init__()
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
    
    def run(self) -> None:
        """Запуск потока проверки"""
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.check_authorization())
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            loop.close()
    
    async def check_authorization(self) -> None:
        """Проверяет авторизацию"""
        client = None
        try:
            client = Client(
                "uploader_session",
                api_id=self.api_id,
                api_hash=self.api_hash,
                phone_number=self.phone
            )
            
            await client.connect()
            user = await client.get_me()
            
            if user:
                print(f"[CHECK_AUTH] Авторизован как: {user.first_name} {user.last_name or ''}")
                self.step_completed.emit("already_authorized", "success", 
                                       f"{user.first_name} {user.last_name or ''}")
            else:
                self.step_completed.emit("not_authorized", "info", "Не авторизован")
                
        except Exception as e:
            print(f"[CHECK_AUTH] Не авторизован: {e}")
            self.step_completed.emit("not_authorized", "info", "Не авторизован")
        finally:
            if client:
                await client.disconnect()