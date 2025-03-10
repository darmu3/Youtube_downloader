import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit,
    QPushButton, QProgressBar, QLabel, QComboBox
)
from PySide6.QtCore import QThread, Signal, QTimer, QPropertyAnimation, QRect
from yt_dlp import YoutubeDL


# Поток для скачивания видео
class DownloadThread(QThread):
    progress = Signal(int)
    finished = Signal()
    error = Signal(str)
    canceled = Signal()
    file_exists = Signal()

    def __init__(self, url, format_option, quality_option, parent=None):
        super().__init__(parent)
        self.url = url
        self.format_option = format_option
        self.quality_option = quality_option
        self.is_canceled = False

    def run(self):
        try:
            # Исправленный путь для скачивания
            desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
            downloads_path = os.path.join(desktop_path, 'downloads')
            os.makedirs(downloads_path, exist_ok=True)

            if self.format_option == 'm4a':
                filename = '%(title)s.%(ext)s'
            elif self.format_option == 'mp4':
                filename = f'[{self.quality_option}p] %(title)s.%(ext)s'

            outtmpl_path = os.path.join(downloads_path, filename)

            # Примечание: Проверка существования файла здесь некорректна из-за шаблона имени,
            # требуется доработка для корректной проверки существующих файлов
            if os.path.exists(outtmpl_path):
                self.file_exists.emit()
                return

            if self.format_option == 'm4a':
                ydl_opts = {
                    'outtmpl': os.path.join(downloads_path, '%(title)s.%(ext)s'),
                    'format': 'bestaudio[ext=m4a]/best[ext=mp3]',
                    'ffmpeg_location': r'C:\ffmpeg\bin',
                    'progress_hooks': [self.on_progress],
                }
            elif self.format_option == 'mp4':
                ydl_opts = {
                    'outtmpl': os.path.join(downloads_path, f'[{self.quality_option}p] %(title)s.%(ext)s'),
                    'format': f'bestvideo[height={self.quality_option}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
                    'ffmpeg_location': r'C:\ffmpeg\bin',
                    'progress_hooks': [self.on_progress],
                }

            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])

            if self.is_canceled:
                self.canceled.emit()
            else:
                self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

    def on_progress(self, d):
        if d['status'] == 'downloading':
            progress_percentage = d.get('_percent_str', '0.00%').strip('%')
            self.progress.emit(int(float(progress_percentage)))
        elif d['status'] == 'finished':
            self.progress.emit(100)

    def cancel(self):
        self.is_canceled = True


class YouTubeDownloader(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("YouTube Downloader")
        self.setGeometry(100, 100, 400, 300)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        # Установка стилей
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2e3b4e;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #3f4858;
                border-radius: 5px;
                padding: 5px;
                font-size: 14px;
            }
            QPushButton {
                background-color: #4caf50;
                color: white;
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
            }
            QPushButton:disabled {
                background-color: #8c8c8c;
            }
            QProgressBar {
                background-color: #e0e0e0;
                border: 1px solid #3f4858;
                border-radius: 5px;
                text-align: center;
                color: black;
            }
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #3f4858;
                border-radius: 5px;
                padding: 5px;
                font-size: 14px;
            }
            QComboBox::drop-down {
                border: none;
                background: transparent;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: url(arrow-icon.png);
                width: 20px;
                height: 20px;
            }
            QLabel {
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
        """)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Введите ссылку на видео YouTube")
        self.layout.addWidget(self.url_input)

        self.format_combo = QComboBox()
        self.format_combo.addItem("m4a (аналог mp3)")
        self.format_combo.addItem("mp4")
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        self.layout.addWidget(self.format_combo)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["144p", "240p", "360p", "480p", "720p", "1080p"])
        self.layout.addWidget(self.quality_combo)
        self.quality_combo.setVisible(False)

        self.download_button = QPushButton("Скачать")
        self.download_button.clicked.connect(self.start_download)
        self.layout.addWidget(self.download_button)

        self.cancel_button = QPushButton("Отменить")
        self.cancel_button.clicked.connect(self.cancel_download)
        self.cancel_button.setEnabled(False)
        self.layout.addWidget(self.cancel_button)

        self.progress_bar = QProgressBar()
        self.layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.layout.addWidget(self.status_label)

        self.download_thread = None

        # Анимация появления сообщений
        self.message_animation = QPropertyAnimation(self.status_label, b"geometry")
        self.message_animation.setDuration(500)
        self.message_animation.finished.connect(self.clear_status)

    def on_format_changed(self, format_option):
        if format_option.startswith("m4a"):
            self.quality_combo.setVisible(False)
        else:
            self.quality_combo.setVisible(True)

    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            self.show_status("Введите ссылку на видео!", error=True)
            return

        format_option = self.format_combo.currentText().split(" ")[0]
        quality_option = self.quality_combo.currentText().replace("p", "")

        self.download_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setValue(0)

        self.download_thread = DownloadThread(url, format_option, quality_option)
        self.download_thread.progress.connect(self.progress_bar.setValue)
        self.download_thread.finished.connect(self.handle_finished)
        self.download_thread.error.connect(self.handle_error)
        self.download_thread.canceled.connect(self.handle_canceled)
        self.download_thread.file_exists.connect(self.handle_file_exists)

        self.download_thread.start()

    def cancel_download(self):
        if self.download_thread:
            self.download_thread.cancel()

    def handle_finished(self):
        self.show_status("Видео успешно скачано!")
        self.cleanup()

    def handle_error(self, error):
        self.show_status(f"Ошибка: {error}", error=True)
        self.cleanup()

    def handle_canceled(self):
        self.show_status("Скачивание отменено.", error=True)
        self.cleanup()

    def handle_file_exists(self):
        self.show_status("Файл уже существует!", error=True)
        self.cleanup()

    def show_status(self, message, error=False):
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: red;" if error else "color: green;")
        self.message_animation.setStartValue(QRect(10, 300, 0, 0))
        self.message_animation.setEndValue(QRect(10, 250, 400, 50))
        self.message_animation.start()

    def clear_status(self):
        self.status_label.setText("")

    def cleanup(self):
        self.reset_ui()
        self.download_thread = None

    def reset_ui(self):
        self.download_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setValue(0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubeDownloader()
    window.show()
    sys.exit(app.exec())
