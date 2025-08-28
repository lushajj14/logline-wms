# app/ui/toast.py
from PyQt5.QtCore    import Qt, QPropertyAnimation, QEasingCurve, QPoint, QRectF, QTimer
from PyQt5.QtGui     import QPainter, QPainterPath, QColor, QFont
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication

DEFAULT_SECS = 3          # MainWindow içinden güncellenebilir

class Toast(QWidget):
    def __init__(self, title: str, msg: str | None = None, *, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # ---------- Görünüm ----------
        self._bg    = QColor(50, 50, 50, 220)
        self._text  = QColor("#ECECEC")
        lay = QVBoxLayout(self); lay.setContentsMargins(15, 12, 15, 12)
        lbl1 = QLabel(title); lbl1.setStyleSheet("font-weight:bold")
        lay.addWidget(lbl1)
        if msg:
            lbl2 = QLabel(msg); lbl2.setWordWrap(True)
            lay.addWidget(lbl2)

        # ---------- Animasyon ----------
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(400)
        self._anim.setEasingCurve(QEasingCurve.OutQuad)

    # ----- Yuvarlak kenarlı arka-plan -----
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 10.0, 10.0)   # QRectF şart!
        p.fillPath(path, self._bg)

    # ----- Dışarıdan çağrılan metod -----
    def popup(self, secs: int | None = None):
        """Göster + kendini yok et."""
        secs = secs or DEFAULT_SECS
        self.adjustSize()

        # Ekranın sağ-alt köşesine hizala
        scr = QApplication.primaryScreen().geometry()
        x = scr.right()  - self.width()  - 25
        y = scr.bottom() - self.height() - 50
        self.move(QPoint(x, y))

        # Fade-in animasyonu (alttan yukarı doğru)
        self.setWindowOpacity(0.0); self.show()
        self._anim.setStartValue(QPoint(x, y+20))
        self._anim.setEndValue(QPoint(x, y))
        self._anim.start()
        self._fade(0.0, 1.0, 250)

        # Otomatik kapanma
        QTimer.singleShot(secs * 1000, lambda: self._fade(1.0, 0.0, 300))

    # ----- Fade yardımcı -----
    def _fade(self, start, end, ms):
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setStartValue(start); anim.setEndValue(end); anim.setDuration(ms)
        anim.finished.connect(self.close)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
