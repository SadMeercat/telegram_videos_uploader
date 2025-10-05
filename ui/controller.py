"""
Контроллер основного окна - связывает UI с бизнес-логикой
"""
import os
import time
from typing import Optional
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QListWidgetItem
from PyQt5.QtCore import QTimer, Qt

from ui.main_window import MainWindow
from core.auth import TelegramAuth, TelegramAuthChecker
from core.chat_loader import ChatLoader
from core.uploader import VideoUploader


class MainWindowController:
    """Контроллер для основного окна"""
    
    def __init__(self, window: MainWindow):
        """
        Инициализация контроллера
        
        Args:
            window: Экземпляр главного окна
        """
        self.window = window
        self._connect_signals()
        self._auto_check_auth()
        
    def _connect_signals(self) -> None:
        """Подключает сигналы к слотам"""
        # Подключаем сигналы кнопок к методам контроллера
        self.window.check_auth_button.clicked.connect(self.check_authorization)
        self.window.get_code_button.clicked.connect(self.request_code)
        self.window.confirm_code_button.clicked.connect(self.confirm_code)
        self.window.reset_auth_button.clicked.connect(self.reset_authorization)
        self.window.browse_button.clicked.connect(self.browse_files)
        self.window.clear_button.clicked.connect(self.clear_files)
        self.window.file_mode_combo.currentTextChanged.connect(self.on_file_mode_changed)
        self.window.files_list_combo.currentTextChanged.connect(self.on_file_selected_from_list)
        self.window.prefix_input.textChanged.connect(self.on_prefix_changed)
        self.window.load_chats_button.clicked.connect(self.load_chats)
        self.window.chat_search_input.textChanged.connect(self.filter_chats)
        self.window.chat_list_widget.itemClicked.connect(self.on_chat_selected)
        self.window.start_button.clicked.connect(self.start_upload)
        self.window.stop_button.clicked.connect(self.stop_upload)
        
        # Подключаем Enter для подтверждения кода
        self.window.code_input.returnPressed.connect(self.confirm_code)
    
    def _auto_check_auth(self) -> None:
        """Автоматически проверяет авторизацию при запуске"""
        # Автоматически проверяем авторизацию, если все поля заполнены
        if all([self.window.api_id_input.text(), 
                self.window.api_hash_input.text(), 
                self.window.phone_input.text()]):
            self.check_authorization()
    
    # Методы авторизации
    def check_authorization(self) -> None:
        """Проверяет статус авторизации"""
        if not self._validate_api_settings():
            return
            
        self.window.log_message("Проверка авторизации...")
        self.window.check_auth_button.setEnabled(False)
        self.window.check_auth_button.setText("Проверяем...")
        
        # Останавливаем предыдущий поток если он существует
        if self.window.auth_thread and self.window.auth_thread.isRunning():
            self.window.auth_thread.terminate()
            self.window.auth_thread.wait()
        
        # Используем отдельный класс для проверки
        self.window.auth_thread = TelegramAuthChecker(
            int(self.window.api_id_input.text()),
            self.window.api_hash_input.text(),
            self.window.phone_input.text()
        )
        self.window.auth_thread.step_completed.connect(self._on_auth_step)
        self.window.auth_thread.error_occurred.connect(self._on_auth_error)
        self.window.auth_thread.finished.connect(self._on_auth_thread_finished)
        self.window.auth_thread.start()
    
    def request_code(self) -> None:
        """Запрашивает код подтверждения и начинает полный цикл авторизации"""
        if not self._validate_api_settings():
            return
            
        self.window.log_message("Начинаем авторизацию...")
        self.window.get_code_button.setEnabled(False)
        self.window.get_code_button.setText("Авторизация...")
        
        # Останавливаем предыдущий поток если он существует
        if self.window.auth_thread and self.window.auth_thread.isRunning():
            self.window.auth_thread.terminate()
            self.window.auth_thread.wait()
        
        # Создаем поток для полной авторизации
        self.window.auth_thread = TelegramAuth(
            int(self.window.api_id_input.text()),
            self.window.api_hash_input.text(),
            self.window.phone_input.text()
        )
        self.window.auth_thread.step_completed.connect(self._on_auth_step)
        self.window.auth_thread.error_occurred.connect(self._on_auth_error)
        self.window.auth_thread.finished.connect(self._on_auth_thread_finished)
        self.window.auth_thread.start()
    
    def confirm_code(self) -> None:
        """Отправляет введенный код в поток авторизации"""
        if not self.window.code_input.text():
            QMessageBox.warning(self.window, "Ошибка", "Введите код подтверждения")
            return
            
        if not self.window.auth_thread or not self.window.auth_thread.isRunning():
            QMessageBox.warning(self.window, "Ошибка", "Процесс авторизации не запущен")
            return
        
        self.window.log_message("Отправляем код для подтверждения...")
        self.window.confirm_code_button.setEnabled(False)
        self.window.confirm_code_button.setText("Подтверждаем...")
        
        # Устанавливаем пароль 2FA если есть
        password_2fa = self.window.password_input.text().strip() if self.window.password_input.text() else None
        if password_2fa:
            self.window.auth_thread.set_password(password_2fa)
        
        # Отправляем код в поток
        self.window.auth_thread.set_code(self.window.code_input.text())
    
    def reset_authorization(self) -> None:
        """Сбрасывает авторизацию"""
        # Останавливаем все активные потоки
        if self.window.auth_thread and self.window.auth_thread.isRunning():
            self.window.auth_thread.terminate()
            self.window.auth_thread.wait()
        
        if self.window.upload_thread and self.window.upload_thread.isRunning():
            self.window.upload_thread.stop_upload()
            self.window.upload_thread.wait()
        
        if self.window.chat_loader_thread and self.window.chat_loader_thread.isRunning():
            self.window.chat_loader_thread.terminate()
            self.window.chat_loader_thread.wait()
        
        # Удаляем файл сессии
        session_file = "uploader_session.session"
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                if os.path.exists(session_file):
                    os.remove(session_file)
                    print(f"[RESET] Файл сессии удален (попытка {attempt + 1})")
                    break
                else:
                    print(f"[RESET] Файл сессии не найден")
                    break
            except PermissionError:
                print(f"[RESET] Файл заблокирован, попытка {attempt + 1}/{max_attempts}")
                if attempt < max_attempts - 1:
                    time.sleep(1)
                else:
                    QMessageBox.warning(self.window, "Предупреждение", 
                                      "Не удалось удалить файл сессии. Перезапустите программу.")
            except Exception as e:
                print(f"[RESET] Ошибка удаления файла сессии: {e}")
                break
        
        # Сбрасываем состояние UI
        self.window.phone_code_hash = None
        self._update_auth_ui("not_authorized")
        
        # Очищаем список чатов
        self.window.chat_list_widget.clear()
        self.window.selected_chat_label.setText("Чат не выбран")
        self.window.chat_load_status.setText("Сначала авторизуйтесь")
        
        self.window.log_message("🔄 Авторизация сброшена")
        QMessageBox.information(self.window, "Сброс", "Авторизация сброшена!")
    
    # Методы работы с папками и файлами
    def browse_files(self) -> None:
        """Выбор файлов в зависимости от режима"""
        mode = self.window.file_mode_combo.currentText()
        
        if "Папка" in mode:
            self._browse_folder()
        elif "Один файл" in mode:
            self._browse_single_file()
        elif "Несколько файлов" in mode:
            self._browse_multiple_files()
    
    def _browse_folder(self) -> None:
        """Выбор папки с файлами"""
        folder = QFileDialog.getExistingDirectory(self.window, "Выберите папку с файлами")
        if folder:
            self.window.selected_files = [folder]
            self.window.folder_input.setText(folder)
            self.window.clear_button.setEnabled(True)
            self._update_files_list()  # Обновляем список файлов
            self.window.save_settings()
            self._check_upload_readiness()
    
    def _browse_single_file(self) -> None:
        """Выбор одного файла"""
        file_filter = "Все поддерживаемые файлы (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v *.3gp *.mp3 *.wav *.aac *.flac *.ogg *.m4a *.jpg *.jpeg *.png *.gif *.bmp *.webp *.pdf *.doc *.docx *.txt *.zip *.rar *.7z);;Видео файлы (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v *.3gp);;Аудио файлы (*.mp3 *.wav *.aac *.flac *.ogg *.m4a);;Изображения (*.jpg *.jpeg *.png *.gif *.bmp *.webp);;Документы (*.pdf *.doc *.docx *.txt);;Архивы (*.zip *.rar *.7z);;Все файлы (*.*)"
        
        file_path, _ = QFileDialog.getOpenFileName(
            self.window, 
            "Выберите файл для загрузки", 
            "", 
            file_filter
        )
        
        if file_path:
            self.window.selected_files = [file_path]
            filename = os.path.basename(file_path)
            self.window.folder_input.setText(f"📄 {filename}")
            self.window.clear_button.setEnabled(True)
            self._update_files_list()  # Обновляем список файлов
            self.window.save_settings()
            self._check_upload_readiness()
    
    def _browse_multiple_files(self) -> None:
        """Выбор нескольких файлов"""
        file_filter = "Все поддерживаемые файлы (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v *.3gp *.mp3 *.wav *.aac *.flac *.ogg *.m4a *.jpg *.jpeg *.png *.gif *.bmp *.webp *.pdf *.doc *.docx *.txt *.zip *.rar *.7z);;Видео файлы (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v *.3gp);;Аудио файлы (*.mp3 *.wav *.aac *.flac *.ogg *.m4a);;Изображения (*.jpg *.jpeg *.png *.gif *.bmp *.webp);;Документы (*.pdf *.doc *.docx *.txt);;Архивы (*.zip *.rar *.7z);;Все файлы (*.*)"
        
        file_paths, _ = QFileDialog.getOpenFileNames(
            self.window, 
            "Выберите файлы для загрузки", 
            "", 
            file_filter
        )
        
        if file_paths:
            self.window.selected_files = file_paths
            count = len(file_paths)
            self.window.folder_input.setText(f"📄 Выбрано файлов: {count}")
            self.window.clear_button.setEnabled(True)
            self._update_files_list()  # Обновляем список файлов
            self.window.save_settings()
            self._check_upload_readiness()
    
    def _update_files_list(self) -> None:
        """Обновляет выпадающий список файлов"""
        self.window.files_list_combo.clear()
        
        if len(self.window.selected_files) > 1:
            # Показываем список только если выбрано несколько файлов
            self.window.files_list_combo.setVisible(True)
            
            for i, file_path in enumerate(self.window.selected_files):
                filename = os.path.basename(file_path)
                # Ограничиваем длину имени файла для отображения
                if len(filename) > 50:
                    display_name = filename[:47] + "..."
                else:
                    display_name = filename
                    
                self.window.files_list_combo.addItem(f"📄 {display_name}", file_path)
                
                # Устанавливаем tooltip с полным путем для каждого элемента
                self.window.files_list_combo.setItemData(i, file_path, Qt.ToolTipRole)
                
            # Устанавливаем общий tooltip для комбобокса
            self.window.files_list_combo.setToolTip("Выберите файл для просмотра информации")
        else:
            # Скрываем список если файл один или файлов нет
            self.window.files_list_combo.setVisible(False)
    
    def clear_files(self) -> None:
        """Очистка выбранных файлов"""
        self.window.selected_files = []
        self.window.folder_input.clear()
        self._update_files_list()  # Обновляем список файлов
        
        mode = self.window.file_mode_combo.currentText()
        
        if "Папка" in mode:
            self.window.folder_input.setPlaceholderText("Выберите папку с файлами")
        elif "Один файл" in mode:
            self.window.folder_input.setPlaceholderText("Выберите файл для загрузки")
        elif "Несколько файлов" in mode:
            self.window.folder_input.setPlaceholderText("Выберите файлы для загрузки")
            
        self.window.clear_button.setEnabled(False)
        self._check_upload_readiness()
    
    def on_file_mode_changed(self) -> None:
        """Обработчик изменения режима выбора файлов"""
        self.clear_files()  # Очищаем при смене режима
        mode = self.window.file_mode_combo.currentText()
        
        if "Папка" in mode:
            self.window.browse_button.setText("📁 Выбрать папку")
        elif "Один файл" in mode:
            self.window.browse_button.setText("📄 Выбрать файл")
        elif "Несколько файлов" in mode:
            self.window.browse_button.setText("📄 Выбрать файлы")
    
    def on_file_selected_from_list(self) -> None:
        """Обработчик выбора файла из выпадающего списка"""
        current_index = self.window.files_list_combo.currentIndex()
        if current_index >= 0 and current_index < len(self.window.selected_files):
            file_path = self.window.selected_files[current_index]
            # Показываем полный путь во всплывающей подсказке
            self.window.files_list_combo.setToolTip(f"Полный путь: {file_path}")
            
            # Можно также показать информацию о файле в статусной строке
            try:
                file_size = os.path.getsize(file_path)
                size_mb = file_size / (1024 * 1024)
                if size_mb < 1:
                    size_str = f"{file_size / 1024:.1f} КБ"
                else:
                    size_str = f"{size_mb:.1f} МБ"
                
                filename = os.path.basename(file_path)
                self.window.log_message(f"📄 {filename} ({size_str})")
            except OSError:
                pass
    
    def on_prefix_changed(self) -> None:
        """Автосохранение префикса при изменении"""
        self.window.save_settings()
    
    # Методы работы с чатами
    def load_chats(self) -> None:
        """Загружает список чатов"""
        if not self._validate_api_settings():
            return
            
        self.window.log_message("📋 Загружаем список чатов...")
        self.window.load_chats_button.setEnabled(False)
        self.window.load_chats_button.setText("Загружаем...")
        
        if self.window.chat_loader_thread and self.window.chat_loader_thread.isRunning():
            self.window.chat_loader_thread.terminate()
            self.window.chat_loader_thread.wait()
        
        self.window.chat_loader_thread = ChatLoader(
            int(self.window.api_id_input.text()),
            self.window.api_hash_input.text()
        )
        self.window.chat_loader_thread.chats_loaded.connect(self._on_chats_loaded)
        self.window.chat_loader_thread.error_occurred.connect(self._on_chat_load_error)
        self.window.chat_loader_thread.progress_updated.connect(self._on_chat_load_progress)
        self.window.chat_loader_thread.finished.connect(self._on_chat_load_finished)
        self.window.chat_loader_thread.start()
    
    def filter_chats(self) -> None:
        """Фильтрует список чатов по поиску"""
        search_text = self.window.chat_search_input.text().lower()
        self._update_chat_list(search_text)
    
    def on_chat_selected(self, item: QListWidgetItem) -> None:
        """Обработчик выбора чата"""
        if not item:
            return
            
        # Извлекаем ID чата из данных элемента
        chat_data = item.data(32)  # UserRole
        if chat_data:
            chat_id = chat_data['id']
            chat_title = chat_data['title']
            chat_type = chat_data['type']
            
            self.window.selected_chat_id = chat_id
            self.window.selected_chat_name = chat_title  # Добавляем сохранение названия
            self.window.chat_input.setText(str(chat_id))
            
            # Обновляем отображение выбранного чата
            self.window.selected_chat_label.setText(f"💬 {chat_title}\n🏷️ {chat_type}\n🆔 ID: {chat_id}")
            
            # Проверяем возможность загрузки
            self._check_upload_readiness()
            
            # Сохраняем настройки
            self.window.save_settings()
            
            self.window.log_message(f"Выбран чат: {chat_title}")
    
    # Методы загрузки
    def start_upload(self) -> None:
        """Начинает загрузку видео"""
        # Валидация
        if not self._validate_upload_settings():
            return
        
        # Получаем настройки
        chat_id = self.window.selected_chat_id
        video_folder = self.window.folder_input.text()
        prefix_text = self.window.prefix_input.text().strip()
        
        try:
            delay_seconds = int(self.window.delay_input.text())
        except ValueError:
            delay_seconds = 2
        
        # Определяем количество потоков
        speed_index = self.window.speed_combo.currentIndex()
        max_concurrent = [1, 4, 8][speed_index]
        
        self.window.log_message("🚀 Начинаем загрузку видео...")
        
        # Обновляем UI
        self.window.start_button.setEnabled(False)
        self.window.stop_button.setEnabled(True)
        self.window.progress_bar.setVisible(True)
        self.window.file_progress_bar.setVisible(True)
        self.window.progress_bar.setValue(0)
        self.window.file_progress_bar.setValue(0)
        
        # Создаем и запускаем поток загрузки
        self.window.upload_thread = VideoUploader(
            int(self.window.api_id_input.text()),
            self.window.api_hash_input.text(),
            chat_id,
            video_folder,
            delay_seconds,
            max_concurrent,
            prefix_text
        )
        
        # Подключаем сигналы
        self.window.upload_thread.progress_updated.connect(self.window.progress_bar.setValue)
        self.window.upload_thread.status_updated.connect(self.window.log_message)
        self.window.upload_thread.file_uploaded.connect(self._on_file_uploaded)
        self.window.upload_thread.file_progress.connect(self._on_file_progress)
        self.window.upload_thread.finished.connect(self._on_upload_finished)
        
        self.window.upload_thread.start()
    
    def stop_upload(self) -> None:
        """Останавливает загрузку видео"""
        if self.window.upload_thread and self.window.upload_thread.isRunning():
            self.window.log_message("⏹️ Останавливаем загрузку...")
            self.window.stop_button.setEnabled(False)
            self.window.stop_button.setText("Останавливаем...")
            
            # Останавливаем поток
            self.window.upload_thread.stop_upload()
            
            # Ждем завершения с таймаутом
            if not self.window.upload_thread.wait(5000):  # 5 секунд
                self.window.log_message("⚠️ Принудительное завершение потока загрузки")
                self.window.upload_thread.terminate()
                self.window.upload_thread.wait()
            
            self._reset_ui_after_stop()
    
    # Приватные методы
    def _validate_api_settings(self) -> bool:
        """Проверяет настройки API"""
        valid, error_msg = self.window.settings.validate_api_settings(
            self.window.api_id_input.text(),
            self.window.api_hash_input.text(),
            self.window.phone_input.text()
        )
        
        if not valid:
            QMessageBox.warning(self.window, "Ошибка", error_msg)
            return False
            
        return True
    
    def _validate_upload_settings(self) -> bool:
        """Проверяет настройки загрузки"""
        if not hasattr(self.window, 'selected_chat_id') or not self.window.selected_chat_id:
            QMessageBox.warning(self.window, "Ошибка", "Выберите чат для загрузки")
            return False
            
        if not self.window.folder_input.text():
            QMessageBox.warning(self.window, "Ошибка", "Выберите папку с видео")
            return False
            
        if not os.path.exists(self.window.folder_input.text()):
            QMessageBox.warning(self.window, "Ошибка", "Папка с видео не найдена")
            return False
            
        return True
    
    def _update_auth_ui(self, state: str, user_info: str = "") -> None:
        """Обновляет UI в зависимости от состояния авторизации"""
        if state == "not_authorized":
            self.window.auth_status_label.setText("📋 Статус: Не авторизован")
            self.window.get_code_button.setEnabled(True)
            self.window.code_input.setEnabled(False)
            self.window.confirm_code_button.setEnabled(False)
            self.window.load_chats_button.setEnabled(False)
            self.window.chat_load_status.setText("Сначала авторизуйтесь")
            
        elif state == "code_sent":
            self.window.auth_status_label.setText("📋 Статус: Код отправлен")
            self.window.code_input.setEnabled(True)
            self.window.confirm_code_button.setEnabled(True)
            self.window.code_input.setFocus()
            
        elif state == "authorized":
            self.window.auth_status_label.setText(f"📋 Статус: Авторизован как {user_info}")
            self.window.get_code_button.setEnabled(False)
            self.window.code_input.setEnabled(False)
            self.window.confirm_code_button.setEnabled(False)
            self.window.load_chats_button.setEnabled(True)
            self.window.chat_load_status.setText("Нажмите 'Обновить список чатов'")
        
        self._reset_auth_buttons()
    
    def _reset_auth_buttons(self) -> None:
        """Сбрасывает состояние кнопок авторизации"""
        self.window.check_auth_button.setEnabled(True)
        self.window.check_auth_button.setText("🔍 Проверить")
        
        if self.window.get_code_button.isEnabled():
            self.window.get_code_button.setText("📱 Код")
        
        if self.window.confirm_code_button.isEnabled():
            self.window.confirm_code_button.setText("✅ OK")
    
    def _check_upload_readiness(self) -> None:
        """Проверяет готовность к загрузке"""
        has_chat = hasattr(self.window, 'selected_chat_id') and bool(self.window.selected_chat_id)
        has_files = bool(self.window.selected_files)
        
        # Проверяем что выбранные файлы/папки существуют
        files_exist = False
        if has_files:
            if len(self.window.selected_files) == 1 and os.path.isdir(self.window.selected_files[0]):
                # Проверяем папку
                files_exist = os.path.exists(self.window.selected_files[0])
            else:
                # Проверяем файлы
                files_exist = all(os.path.exists(f) for f in self.window.selected_files)
        
        can_upload = has_chat and has_files and files_exist
        
        # Убеждаемся что can_upload это bool
        can_upload = bool(can_upload)
        
        self.window.start_button.setEnabled(can_upload)
    
    def _update_chat_list(self, search_text: str = "") -> None:
        """Обновляет отображение списка чатов"""
        self.window.chat_list_widget.clear()
        
        for chat in self.window.chats_list:
            if search_text and search_text not in chat['title'].lower():
                continue
                
            item = QListWidgetItem(f"{chat['title']}\n{chat['type']}")
            item.setData(32, chat)  # UserRole
            self.window.chat_list_widget.addItem(item)
    
    def _reset_ui_after_stop(self) -> None:
        """Сбрасывает UI после остановки загрузки"""
        self.window.start_button.setEnabled(True)
        self.window.stop_button.setEnabled(False)
        self.window.stop_button.setText("⏹️ Остановить")
        self.window.progress_bar.setVisible(False)
        self.window.file_progress_bar.setVisible(False)
        self.window.current_file_label.setText("📄 Файл не выбран")
        self.window.upload_speed_label.setText("⚡ Скорость: -")
    
    # Слоты для сигналов
    def _on_auth_step(self, step: str, status: str, data: str) -> None:
        """Обработка шагов авторизации"""
        print(f"[UI] Auth step: {step}, status: {status}, data: {data}")
        
        if step == "code_sent":
            self._update_auth_ui("code_sent")
            self.window.log_message("📱 Код отправлен на ваш телефон")
            
        elif step == "auth_success":
            self._update_auth_ui("authorized", data)
            self.window.log_message(f"✅ Успешная авторизация: {data}")
            self.window.save_settings()
            # Автоматически загружаем чаты после успешной авторизации
            self._auto_load_chats()
            
        elif step == "need_password":
            self.window.log_message("🔐 Требуется пароль 2FA")
            QMessageBox.information(self.window, "2FA", "Введите пароль двухфакторной аутентификации в поле '2FA' и нажмите 'OK'")
            
        elif step == "already_authorized":
            self._update_auth_ui("authorized", data)
            self.window.log_message(f"✅ Уже авторизован: {data}")
            # Автоматически загружаем чаты если уже авторизованы
            self._auto_load_chats()
            
        elif step == "not_authorized":
            self._update_auth_ui("not_authorized")
    
    def _on_auth_error(self, error: str) -> None:
        """Обработка ошибок авторизации"""
        error_msg = str(error)
        
        if "PHONE_CODE_EXPIRED" in error_msg:
            QMessageBox.warning(self.window, "Ошибка", 
                              "Время действия кода истекло.\nЗапросите новый код.")
            self.window.code_input.clear()
            self.window.code_input.setEnabled(False)
            self.window.confirm_code_button.setEnabled(False)
        elif "PHONE_CODE_INVALID" in error_msg:
            QMessageBox.warning(self.window, "Ошибка", 
                              "Неверный код подтверждения.\nПроверьте код и попробуйте снова.")
            self.window.code_input.clear()
            self.window.code_input.setFocus()
        elif "FLOOD_WAIT" in error_msg:
            import re
            wait_time = re.search(r'(\d+)', error_msg)
            if wait_time:
                wait_seconds = int(wait_time.group(1))
                wait_minutes = wait_seconds // 60
                QMessageBox.warning(self.window, "Ограничение", 
                                  f"Слишком много попыток.\nПовторите через {wait_minutes} минут {wait_seconds % 60} секунд.")
            else:
                QMessageBox.warning(self.window, "Ограничение", 
                                  "Слишком много попыток. Подождите немного.")
        else:
            QMessageBox.critical(self.window, "Ошибка авторизации", error_msg)
        
        self._reset_auth_buttons()
    
    def _on_auth_thread_finished(self) -> None:
        """Обработчик завершения потока авторизации"""
        print("[UI] Auth thread finished")
        if self.window.auth_thread:
            self.window.auth_thread.deleteLater()
            self.window.auth_thread = None
    
    def _on_chats_loaded(self, chats: list) -> None:
        """Обработчик загрузки чатов"""
        self.window.chats_list = chats
        self._update_chat_list()
        self.window.log_message(f"📋 Загружено {len(chats)} чатов")
    
    def _on_chat_load_error(self, error: str) -> None:
        """Обработчик ошибки загрузки чатов"""
        QMessageBox.critical(self.window, "Ошибка", f"Ошибка загрузки чатов:\n{error}")
        self.window.log_message(f"❌ Ошибка загрузки чатов: {error}")
    
    def _on_chat_load_progress(self, status: str) -> None:
        """Обработчик прогресса загрузки чатов"""
        self.window.chat_load_status.setText(status)
    
    def _on_chat_load_finished(self) -> None:
        """Обработчик завершения загрузки чатов"""
        self.window.load_chats_button.setEnabled(True)
        self.window.load_chats_button.setText("🔄 Обновить список чатов")
        self.window.chat_load_status.setText(f"Загружено {len(self.window.chats_list)} чатов")
        
        if self.window.chat_loader_thread:
            self.window.chat_loader_thread.deleteLater()
            self.window.chat_loader_thread = None
    
    def _on_file_uploaded(self, filename: str) -> None:
        """Обработчик успешной загрузки файла"""
        self.window.log_message(f"✅ Загружен: {filename}")
    
    def _on_file_progress(self, filename: str, percentage: int, speed: str) -> None:
        """Обработчик прогресса загрузки файла"""
        self.window.current_file_label.setText(f"📄 {filename}")
        self.window.file_progress_bar.setValue(percentage)
        self.window.upload_speed_label.setText(f"⚡ {speed}")
    
    def _on_upload_finished(self, success: bool, message: str) -> None:
        """Обработчик завершения загрузки"""
        self._reset_ui_after_stop()
        
        if success:
            self.window.log_message(f"✅ {message}")
            QMessageBox.information(self.window, "Завершено", message)
        else:
            self.window.log_message(f"❌ {message}")
            QMessageBox.warning(self.window, "Ошибка", message)
        
        if self.window.upload_thread:
            self.window.upload_thread.deleteLater()
            self.window.upload_thread = None
    
    def _auto_load_chats(self) -> None:
        """Автоматически загружает чаты и восстанавливает выбранный чат"""
        # Загружаем чаты
        self.load_chats()
        
        # Восстанавливаем выбранный чат из настроек
        saved_chat_id = self.window.settings.get("selected_chat_id")
        saved_chat_name = self.window.settings.get("selected_chat_name", "")
        
        if saved_chat_id:
            self.window.selected_chat_id = saved_chat_id
            self.window.chat_input.setText(str(saved_chat_id))
            
            # Обновляем отображение выбранного чата
            if saved_chat_name:
                self.window.selected_chat_label.setText(f"💬 {saved_chat_name}\n🆔 ID: {saved_chat_id}")
            else:
                self.window.selected_chat_label.setText(f"💬 Выбранный чат\n🆔 ID: {saved_chat_id}")
            
            # Проверяем готовность к загрузке
            self._check_upload_readiness()
            
            self.window.log_message(f"Восстановлен выбранный чат: ID {saved_chat_id}")