"""
Утилиты для работы с видео файлами
"""
import os
from typing import Dict, Optional


def get_video_metadata(video_path: str) -> Dict[str, Optional[int]]:
    """
    Извлекает метаданные видео (длительность, разрешение) с помощью moviepy
    
    Args:
        video_path: Путь к видео файлу
        
    Returns:
        Словарь с метаданными: duration, width, height
    """
    try:
        # Используем moviepy для извлечения метаданных
        try:
            from moviepy.editor import VideoFileClip
            print(f"[VIDEO_META] Анализируем видео: {os.path.basename(video_path)}")
            
            with VideoFileClip(video_path) as clip:
                duration = int(clip.duration) if clip.duration else None
                width = clip.w if hasattr(clip, 'w') else None
                height = clip.h if hasattr(clip, 'h') else None
                
                print(f"[VIDEO_META] Получены данные: {duration}с, {width}x{height}")
                return {
                    'duration': duration,
                    'width': width,
                    'height': height
                }
                
        except ImportError as ie:
            print(f"[VIDEO_META] MoviePy не найден: {ie}")
        except Exception as e:
            print(f"[VIDEO_META] Ошибка MoviePy: {e}")
        
        # Fallback: Оценка по размеру файла и расширению
        print("[VIDEO_META] Используем оценку по размеру файла...")
        file_size = os.path.getsize(video_path)
        file_ext = os.path.splitext(video_path)[1].lower()
        
        # Разные оценки битрейта в зависимости от формата
        if file_ext in ['.mp4', '.mkv', '.mov']:
            # Средний битрейт для современного HD видео
            estimated_bitrate = 3_000_000  # 3 Мбит/с
        elif file_ext in ['.avi', '.wmv']:
            # Более старые форматы обычно менее эффективны
            estimated_bitrate = 2_000_000  # 2 Мбит/с
        elif file_ext in ['.webm']:
            # WebM обычно более эффективен
            estimated_bitrate = 1_500_000  # 1.5 Мбит/с
        else:
            # Для неизвестных форматов используем среднее значение
            estimated_bitrate = 2_500_000  # 2.5 Мбит/с
        
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