"""
Основное окно приложения
"""
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from PyQt5.QtWidgets import (QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
                             QPushButton, QLabel, QLineEdit, QTextEdit, 
                             QFileDialog, QMessageBox, QProgressBar, QGroupBox,
                             QComboBox, QListWidget, QListWidgetItem, QSplitter)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from config.settings import Settings
from core.auth import TelegramAuth, TelegramAuthChecker  
from core.chat_loader import ChatLoader
from core.uploader import VideoUploader
from ui.styles import get_main_stylesheet, get_button_style


class MainWindow(QMainWindow):
    """Основное окно приложения"""
    
    def __init__(self):
        """Инициализация главного окна"""
        super().__init__()
        
        # Инициализация данных
        self.settings = Settings()
        self.phone_code_hash: Optional[str] = None
        self.auth_thread: Optional[TelegramAuth] = None
        self.upload_thread: Optional[VideoUploader] = None
        self.chat_loader_thread: Optional[ChatLoader] = None
        self.chats_list: List[Dict[str, Any]] = []
        self.code_timer: Optional[QTimer] = None
        self.time_left = 0
        self.selected_chat_id: Optional[int] = None
        self.selected_chat_name: Optional[str] = None
        
        # Инициализация UI
        self.init_ui()
        self.load_settings()
        
    def init_ui(self) -> None:
        """Инициализация пользовательского интерфейса"""
        self.setWindowTitle("Telegram Video Uploader v3.1")
        self.setGeometry(100, 100, 1100, 600)
        
        # Применяем стили
        self.setStyleSheet(get_main_stylesheet())
        
        # Создаем центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Создаем основной макет
        self._create_main_layout(central_widget)
        
        # Создаем элементы интерфейса
        self._create_header()
        self._create_left_panel()
        self._create_right_panel()
        
    def _create_main_layout(self, central_widget: QWidget) -> None:
        """Создает основную структуру макета"""
        # Создаем горизонтальный разделитель для двух колонок
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(8)
        
        central_widget_layout = QVBoxLayout(central_widget)
        central_widget_layout.setContentsMargins(8, 8, 8, 8)
        central_widget_layout.addWidget(self.main_splitter)
        
        # Левая и правая панели
        self.left_widget = QWidget()
        self.right_widget = QWidget()
        
        # Устанавливаем минимальные размеры
        self.left_widget.setMinimumWidth(500)
        self.right_widget.setMinimumWidth(350)
        
        self.left_layout = QVBoxLayout(self.left_widget)
        self.left_layout.setSpacing(6)
        self.left_layout.setContentsMargins(6, 6, 6, 6)
        
        self.right_layout = QVBoxLayout(self.right_widget)
        self.right_layout.setSpacing(6)
        self.right_layout.setContentsMargins(6, 6, 6, 6)
        
        self.main_splitter.addWidget(self.left_widget)
        self.main_splitter.addWidget(self.right_widget)
        
        # Устанавливаем пропорции (60% левая, 40% правая)
        self.main_splitter.setSizes([660, 440])
        
    def _create_header(self) -> None:
        """Создает заголовок приложения"""
        title_widget = QWidget()
        title_widget.setMinimumHeight(65)  # Устанавливаем минимальную высоту
        title_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 15px;
                margin: 0px 0px 10px 0px;
            }
        """)
        
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(15, 10, 15, 10)  # Увеличили вертикальные отступы
        title_layout.setSpacing(5)  # Добавили интервал между элементами
        
        title = QLabel("📹 Telegram Video Uploader")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color: white; background: transparent; margin: 0px; padding: 2px;")
        title_layout.addWidget(title)
        
        subtitle = QLabel("Быстрая загрузка видео в Telegram с метаданными")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setFont(QFont("Segoe UI", 9))  # Увеличили размер шрифта
        subtitle.setWordWrap(True)  # Добавили перенос строк
        subtitle.setMinimumHeight(20)  # Минимальная высота
        subtitle.setStyleSheet("color: rgba(255, 255, 255, 0.9); background: transparent; margin: 0px; padding: 2px;")
        title_layout.addWidget(subtitle)
        
        self.left_layout.addWidget(title_widget)
        
    def _create_left_panel(self) -> None:
        """Создает левую панель с настройками"""
        # API и авторизация
        self._create_api_auth_section()
        
        # Статус авторизации
        self._create_auth_status()
        
        # Загрузка видео
        self._create_upload_section()
        
        # Логи
        self._create_logs_section()
        
    def _create_api_auth_section(self) -> None:
        """Создает секцию API и авторизации"""
        api_auth_layout = QHBoxLayout()
        api_auth_layout.setSpacing(8)
        
        # API секция
        self._create_api_group(api_auth_layout)
        
        # Авторизация секция
        self._create_auth_group(api_auth_layout)
        
        self.left_layout.addLayout(api_auth_layout)
        
    def _create_api_group(self, parent_layout: QHBoxLayout) -> None:
        """Создает группу настроек API"""
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
        api_layout.setSpacing(6)
        
        # API ID
        api_id_layout = QHBoxLayout()
        api_id_label = QLabel("API ID:")
        api_id_label.setStyleSheet("color: #374151; font-weight: 600; min-width: 70px;")
        api_id_layout.addWidget(api_id_label)
        
        self.api_id_input = QLineEdit()
        self.api_id_input.setPlaceholderText("Получите на my.telegram.org")
        api_id_layout.addWidget(self.api_id_input)
        api_layout.addLayout(api_id_layout)
        
        # API Hash
        api_hash_layout = QHBoxLayout()
        api_hash_label = QLabel("API Hash:")
        api_hash_label.setStyleSheet("color: #374151; font-weight: 600; min-width: 70px;")
        api_hash_layout.addWidget(api_hash_label)
        
        self.api_hash_input = QLineEdit()
        self.api_hash_input.setPlaceholderText("Получите на my.telegram.org")
        api_hash_layout.addWidget(self.api_hash_input)
        api_layout.addLayout(api_hash_layout)
        
        parent_layout.addWidget(api_group)
        
    def _create_auth_group(self, parent_layout: QHBoxLayout) -> None:
        """Создает группу авторизации"""
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
        auth_layout.setSpacing(6)
        
        # Номер телефона
        phone_layout = QHBoxLayout()
        phone_label = QLabel("Телефон:")
        phone_label.setStyleSheet("color: #374151; font-weight: 600; min-width: 70px;")
        phone_layout.addWidget(phone_label)
        
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("+7XXXXXXXXXX")
        phone_layout.addWidget(self.phone_input)
        auth_layout.addLayout(phone_layout)
        
        # Кнопки авторизации
        self._create_auth_buttons(auth_layout)
        
        # Код и пароль
        self._create_code_password_inputs(auth_layout)
        
        parent_layout.addWidget(auth_group)
        
    def _create_auth_buttons(self, auth_layout: QVBoxLayout) -> None:
        """Создает кнопки авторизации"""
        auth_buttons_layout = QHBoxLayout()
        
        self.check_auth_button = QPushButton("🔍 Проверить")
        self.check_auth_button.setStyleSheet(get_button_style('purple'))
        auth_buttons_layout.addWidget(self.check_auth_button)
        
        self.reset_auth_button = QPushButton("🔄 Сброс")
        self.reset_auth_button.setStyleSheet(get_button_style('red'))
        auth_buttons_layout.addWidget(self.reset_auth_button)
        
        auth_layout.addLayout(auth_buttons_layout)
        
    def _create_code_password_inputs(self, auth_layout: QVBoxLayout) -> None:
        """Создает поля для ввода кода и пароля"""
        # Получение кода и ввод кода
        code_layout = QHBoxLayout()
        
        self.get_code_button = QPushButton("📱 Код")
        self.get_code_button.setStyleSheet(get_button_style('blue'))
        self.get_code_button.setEnabled(False)
        code_layout.addWidget(self.get_code_button)
        
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Код")
        self.code_input.setMaxLength(5)
        self.code_input.setEnabled(False)
        self.code_input.setMaximumWidth(60)
        code_layout.addWidget(self.code_input)
        
        self.confirm_code_button = QPushButton("✅ OK")
        self.confirm_code_button.setStyleSheet(get_button_style('green'))
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
        
    def _create_auth_status(self) -> None:
        """Создает статус авторизации"""
        self.auth_status_label = QLabel("📋 Статус: Не проверено")
        self.auth_status_label.setWordWrap(True)
        self.auth_status_label.setMinimumHeight(40)
        self.auth_status_label.setMaximumHeight(60)
        self.auth_status_label.setAlignment(Qt.AlignTop)
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
        self.left_layout.addWidget(self.auth_status_label)
        
    def _create_upload_section(self) -> None:
        """Создает секцию загрузки"""
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
        upload_layout.setSpacing(6)
        
        # Выбор папки
        self._create_folder_selection(upload_layout)
        
        # Префикс
        self._create_prefix_input(upload_layout)
        
        # Настройки
        self._create_upload_settings(upload_layout)
        
        # Кнопки загрузки
        self._create_upload_buttons(upload_layout)
        
        # Прогресс-бары
        self._create_progress_bars(upload_layout)
        
        self.left_layout.addWidget(upload_group)
        
    def _create_folder_selection(self, upload_layout: QVBoxLayout) -> None:
        """Создает выбор папки"""
        folder_layout = QHBoxLayout()
        
        self.folder_input = QLineEdit()
        self.folder_input.setReadOnly(True)
        self.folder_input.setPlaceholderText("Выберите папку с видео")
        folder_layout.addWidget(self.folder_input)
        
        self.browse_button = QPushButton("📁 Обзор")
        self.browse_button.setStyleSheet(get_button_style('orange'))
        folder_layout.addWidget(self.browse_button)
        
        upload_layout.addLayout(folder_layout)
        
    def _create_prefix_input(self, upload_layout: QVBoxLayout) -> None:
        """Создает поле префикса"""
        prefix_layout = QHBoxLayout()
        prefix_label = QLabel("📝 Префикс:")
        prefix_label.setStyleSheet("color: #374151; font-weight: 600; min-width: 80px;")
        prefix_layout.addWidget(prefix_label)
        
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("Текст перед названием файла (необязательно)")
        self.prefix_input.setToolTip("Этот текст будет добавлен перед названием файла при отправке")
        prefix_layout.addWidget(self.prefix_input)
        
        upload_layout.addLayout(prefix_layout)
        
    def _create_upload_settings(self, upload_layout: QVBoxLayout) -> None:
        """Создает настройки загрузки"""
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
        
        # Скорость
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
        self.speed_combo.setCurrentIndex(1)
        self.speed_combo.setToolTip("Для файлов до 3 ГБ рекомендуется максимальная скорость")
        speed_layout.addWidget(self.speed_combo)
        settings_layout.addLayout(speed_layout)
        
        upload_layout.addLayout(settings_layout)
        
    def _create_upload_buttons(self, upload_layout: QVBoxLayout) -> None:
        """Создает кнопки загрузки"""
        upload_buttons_layout = QHBoxLayout()
        upload_buttons_layout.setSpacing(8)
        
        self.start_button = QPushButton("🚀 Начать загрузку")
        self.start_button.setStyleSheet(get_button_style('green'))
        self.start_button.setEnabled(False)
        upload_buttons_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("⏹️ Остановить")
        self.stop_button.setStyleSheet(get_button_style('red'))
        self.stop_button.setEnabled(False)
        upload_buttons_layout.addWidget(self.stop_button)
        
        upload_layout.addLayout(upload_buttons_layout)
        
    def _create_progress_bars(self, upload_layout: QVBoxLayout) -> None:
        """Создает прогресс-бары"""
        # Общий прогресс
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        upload_layout.addWidget(self.progress_bar)
        
        # Прогресс файла
        file_progress_group = QGroupBox("📊 Прогресс текущего файла")
        file_progress_layout = QVBoxLayout(file_progress_group)
        
        self.current_file_label = QLabel("📄 Файл не выбран")
        self.current_file_label.setWordWrap(True)
        self.current_file_label.setMinimumHeight(25)
        self.current_file_label.setMaximumHeight(50)
        self.current_file_label.setAlignment(Qt.AlignTop)
        self.current_file_label.setStyleSheet("""
            QLabel {
                color: #374151;
                background: #f8f9fa;
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 10px;
            }
        """)
        file_progress_layout.addWidget(self.current_file_label)
        
        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setVisible(False)
        file_progress_layout.addWidget(self.file_progress_bar)
        
        self.upload_speed_label = QLabel("⚡ Скорость: -")
        self.upload_speed_label.setMinimumHeight(25)
        self.upload_speed_label.setMaximumHeight(35)
        self.upload_speed_label.setAlignment(Qt.AlignTop)
        self.upload_speed_label.setStyleSheet("""
            QLabel {
                color: #374151;
                background: #f8f9fa;
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 10px;
            }
        """)
        file_progress_layout.addWidget(self.upload_speed_label)
        
        upload_layout.addWidget(file_progress_group)
        
    def _create_logs_section(self) -> None:
        """Создает секцию логов"""
        log_group = QGroupBox("📋 Логи и статус")
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
        self.log_output.setMaximumHeight(80)
        self.log_output.setReadOnly(True)
        log_layout.addWidget(self.log_output)
        
        self.left_layout.addWidget(log_group)
        
    def _create_right_panel(self) -> None:
        """Создает правую панель с чатами"""
        # Заголовок
        self._create_chat_header()
        
        # Кнопка загрузки чатов
        self._create_chat_load_button()
        
        # Статус загрузки
        self._create_chat_status()
        
        # Поиск
        self._create_chat_search()
        
        # Список чатов
        self._create_chat_list()
        
        # Выбранный чат
        self._create_selected_chat()
        
        self.right_layout.addStretch()
        
    def _create_chat_header(self) -> None:
        """Создает заголовок чатов"""
        chat_title_widget = QWidget()
        chat_title_widget.setMinimumHeight(65)  # Устанавливаем минимальную высоту
        chat_title_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6366f1, stop:1 #4f46e5);
                border-radius: 12px;
                margin: 0px 0px 10px 0px;
            }
        """)
        
        chat_title_layout = QVBoxLayout(chat_title_widget)
        chat_title_layout.setContentsMargins(15, 10, 15, 10)  # Увеличили вертикальные отступы
        chat_title_layout.setSpacing(5)  # Добавили интервал между элементами
        
        chat_title = QLabel("💬 Чаты и группы")
        chat_title.setAlignment(Qt.AlignCenter)
        chat_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        chat_title.setStyleSheet("color: white; background: transparent; margin: 0px; padding: 2px;")
        chat_title_layout.addWidget(chat_title)
        
        filter_info = QLabel("(Исключены каналы и боты)")
        filter_info.setAlignment(Qt.AlignCenter)
        filter_info.setFont(QFont("Segoe UI", 9))  # Добавили размер шрифта через QFont
        filter_info.setWordWrap(True)  # Добавили перенос строк
        filter_info.setMinimumHeight(20)  # Минимальная высота
        filter_info.setStyleSheet("color: rgba(255, 255, 255, 0.8); background: transparent; margin: 0px; padding: 2px;")
        chat_title_layout.addWidget(filter_info)
        
        self.right_layout.addWidget(chat_title_widget)
        
    def _create_chat_load_button(self) -> None:
        """Создает кнопку загрузки чатов"""
        self.load_chats_button = QPushButton("🔄 Обновить список чатов")
        self.load_chats_button.setStyleSheet(get_button_style('blue'))
        self.load_chats_button.setEnabled(False)
        self.right_layout.addWidget(self.load_chats_button)
        
    def _create_chat_status(self) -> None:
        """Создает статус загрузки чатов"""
        self.chat_load_status = QLabel("Сначала авторизуйтесь")
        self.chat_load_status.setWordWrap(True)
        self.chat_load_status.setMinimumHeight(40)
        self.chat_load_status.setMaximumHeight(80)
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
        self.right_layout.addWidget(self.chat_load_status)
        
    def _create_chat_search(self) -> None:
        """Создает поиск по чатам"""
        search_layout = QHBoxLayout()
        
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("color: #6b7280; font-size: 14px; padding: 8px 0px; margin-right: 8px;")
        search_layout.addWidget(search_icon)
        
        self.chat_search_input = QLineEdit()
        self.chat_search_input.setPlaceholderText("Введите название чата для поиска...")
        search_layout.addWidget(self.chat_search_input)
        
        self.right_layout.addLayout(search_layout)
        
    def _create_chat_list(self) -> None:
        """Создает список чатов"""
        self.chat_list_widget = QListWidget()
        self.chat_list_widget.setMaximumHeight(200)
        self.right_layout.addWidget(self.chat_list_widget)
        
    def _create_selected_chat(self) -> None:
        """Создает отображение выбранного чата"""
        selected_group = QGroupBox("✅ Выбранный чат")
        selected_layout = QVBoxLayout(selected_group)
        selected_layout.setSpacing(6)
        
        self.selected_chat_label = QLabel("💬 Чат не выбран")
        self.selected_chat_label.setWordWrap(True)
        self.selected_chat_label.setMinimumHeight(60)
        self.selected_chat_label.setMaximumHeight(120)
        self.selected_chat_label.setAlignment(Qt.AlignTop)
        self.selected_chat_label.setStyleSheet("""
            QLabel {
                color: #374151;
                background: #f8f9fa;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 8px;
                font-size: 11px;
            }
        """)
        selected_layout.addWidget(self.selected_chat_label)
        
        # Скрытое поле для совместимости
        self.chat_input = QLineEdit()
        self.chat_input.setVisible(False)
        
        self.right_layout.addWidget(selected_group)
    
    # Методы для работы с настройками
    def load_settings(self) -> None:
        """Загружает сохраненные настройки"""
        self.api_id_input.setText(str(self.settings.get("api_id", "")))
        self.api_hash_input.setText(self.settings.get("api_hash", ""))
        self.phone_input.setText(self.settings.get("phone", ""))
        self.folder_input.setText(self.settings.get("folder", ""))
        self.prefix_input.setText(self.settings.get("prefix_text", ""))
        
        # Не восстанавливаем выбранный чат при запуске
        self.selected_chat_label.setText("Чат не выбран")
        
        # Настройки загружены, контроллер может проверить авторизацию
    
    def save_settings(self) -> None:
        """Сохраняет настройки"""
        try:
            api_id = int(self.api_id_input.text()) if self.api_id_input.text() else 0
        except ValueError:
            api_id = 0
            
        self.settings.set("api_id", api_id)
        self.settings.set("api_hash", self.api_hash_input.text())
        self.settings.set("phone", self.phone_input.text())
        self.settings.set("folder", self.folder_input.text())
        self.settings.set("prefix_text", self.prefix_input.text())
        
        # Сохраняем выбранный чат
        if hasattr(self, 'selected_chat_id') and self.selected_chat_id:
            self.settings.set("selected_chat_id", self.selected_chat_id)
        if hasattr(self, 'selected_chat_name') and self.selected_chat_name:
            self.settings.set("selected_chat_name", self.selected_chat_name)
    
    # Методы для логирования
    def log_message(self, message: str) -> None:
        """Добавляет сообщение в лог"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        # Вставляем новые сообщения в начало
        cursor = self.log_output.textCursor()
        cursor.movePosition(cursor.Start)
        cursor.insertText(log_entry + "\n")
        
        cursor.movePosition(cursor.Start)
        self.log_output.setTextCursor(cursor)
        
        self.status_label.setText(message)