# app/ui/toast.py   (tek geçerli sürüm)

from PyQt5.QtCore    import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QRectF
from PyQt5.QtGui     import QPainter, QPainterPath, QColor
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication

DEFAULT_SECS = 3     # MainWindow _apply_global_settings içinde güncellenir

class Toast(QWidget):
    def __init__(self, title: str, msg: str | None = None, *, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        self._bg   = QColor(50, 50, 50, 220)
        self._text = QColor("#ECECEC")

        lay = QVBoxLayout(self); lay.setContentsMargins(15, 10, 15, 10)
        lbl1 = QLabel(title); lbl1.setStyleSheet("font-weight:bold")
        lay.addWidget(lbl1)
        if msg:
            lbl2 = QLabel(msg); lbl2.setWordWrap(True); lay.addWidget(lbl2)

        # ↑ aşağıdan yukarı hafif kayan animasyon
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(350)
        self._anim.setEasingCurve(QEasingCurve.OutQuad)

    # -------- yuvarlak arka plan --------
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 10.0, 10.0)  # QRectF önemli!
        p.fillPath(path, self._bg)

    # -------- dışarıdan çağrılır --------
    def popup(self, secs: int | None = None):
        secs = secs or DEFAULT_SECS
        self.adjustSize()

        scr = QApplication.primaryScreen().geometry()
        x = scr.right()  - self.width()  - 25
        y = scr.bottom() - self.height() - 50
        self.move(x, y + 20)          # başlangıç pozisyonu (biraz aşağıda)
        self.show()
        self.setWindowOpacity(0.0)

        # Konum + opaklık animasyonları
        self._anim.setStartValue(QPoint(x, y + 20))
        self._anim.setEndValue(QPoint(x, y))
        self._anim.start()

        fade_in = QPropertyAnimation(self, b"windowOpacity", self)
        fade_in.setStartValue(0.0); fade_in.setEndValue(1.0); fade_in.setDuration(250)
        fade_in.start(QPropertyAnimation.DeleteWhenStopped)

        # Otomatik kapan
        QTimer.singleShot(secs * 1000, self._fade_out)

    def _fade_out(self):
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setStartValue(1.0); fade.setEndValue(0.0); fade.setDuration(300)
        fade.finished.connect(self.close)
        fade.start(QPropertyAnimation.DeleteWhenStopped)
