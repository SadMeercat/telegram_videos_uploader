"""
Стили для пользовательского интерфейса
"""


def get_main_stylesheet() -> str:
    """Возвращает основную таблицу стилей для приложения"""
    return """
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
    """


def get_button_style(color_scheme: str) -> str:
    """
    Возвращает стиль для кнопки с определенной цветовой схемой
    
    Args:
        color_scheme: Цветовая схема ('green', 'blue', 'red', 'purple', 'orange')
    """
    schemes = {
        'green': {
            'normal': '#4CAF50, #45a049',
            'hover': '#5CBF60, #4CAF50',
            'pressed': '#45a049, #3e8e41'
        },
        'blue': {
            'normal': '#3b82f6, #2563eb',
            'hover': '#60a5fa, #3b82f6',
            'pressed': '#2563eb, #1d4ed8'
        },
        'red': {
            'normal': '#ef4444, #dc2626',
            'hover': '#f87171, #ef4444',
            'pressed': '#dc2626, #b91c1c'
        },
        'purple': {
            'normal': '#a855f7, #9333ea',
            'hover': '#c084fc, #a855f7',
            'pressed': '#9333ea, #7c3aed'
        },
        'orange': {
            'normal': '#f59e0b, #d97706',
            'hover': '#fbbf24, #f59e0b',
            'pressed': '#d97706, #b45309'
        }
    }
    
    scheme = schemes.get(color_scheme, schemes['green'])
    
    return f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {scheme['normal'].split(', ')[0]}, stop:1 {scheme['normal'].split(', ')[1]});
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px 16px;
            font-weight: bold;
            font-size: 11px;
            min-height: 16px;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {scheme['hover'].split(', ')[0]}, stop:1 {scheme['hover'].split(', ')[1]});
        }}
        QPushButton:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {scheme['pressed'].split(', ')[0]}, stop:1 {scheme['pressed'].split(', ')[1]});
        }}
        QPushButton:disabled {{
            background: #d1d5db;
            color: #9ca3af;
        }}
    """