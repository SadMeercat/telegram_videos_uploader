"""
Главный файл приложения Telegram Video Uploader
"""
import sys
import os
import traceback
from PyQt5.QtWidgets import QApplication, QMessageBox

# Добавляем текущую директорию в путь для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.main_window import MainWindow
from ui.controller import MainWindowController


def setup_exception_handler():
    """Настраивает обработчик исключений"""
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(f"Необработанное исключение:\n{error_msg}")
        
        # Показываем сообщение пользователю
        try:
            QMessageBox.critical(None, "Критическая ошибка", 
                               f"Произошла критическая ошибка:\n\n{str(exc_value)}\n\n"
                               f"Приложение будет закрыто.")
        except:
            pass
    
    sys.excepthook = handle_exception


def main():
    """Главная функция приложения"""
    app = None
    try:
        # Настраиваем обработчик исключений
        setup_exception_handler()
        
        # Создаем приложение Qt
        app = QApplication(sys.argv)
        app.setApplicationName("Telegram Video Uploader")
        app.setApplicationVersion("3.1")
        app.setOrganizationName("TelegramUploader")
        
        # Устанавливаем кодировку для консоли (Windows)
        if sys.platform.startswith('win'):
            try:
                import locale
                locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')
            except:
                pass
        
        print("🚀 Запуск Telegram Video Uploader v3.1")
        print("📁 Рабочая директория:", os.getcwd())
        
        # Создаем главное окно
        window = MainWindow()
        
        # Создаем контроллер
        controller = MainWindowController(window)
        
        # Показываем окно
        window.show()
        
        print("✅ Приложение готово к работе")
        
        # Запускаем цикл событий
        return app.exec_()
        
    except Exception as e:
        error_msg = f"Критическая ошибка при запуске:\n{str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        
        try:
            if app:
                QMessageBox.critical(None, "Ошибка запуска", 
                                   f"Не удалось запустить приложение:\n\n{str(e)}")
            else:
                print("Не удалось создать приложение Qt")
        except:
            pass
        
        return 1
    
    finally:
        if app:
            try:
                app.quit()
            except:
                pass


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)