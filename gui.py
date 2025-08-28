from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QTableWidget, QTableWidgetItem, QHBoxLayout
import sys

class DepoUygulamasi(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Depo Yönetim Sistemi")
        self.setGeometry(100, 100, 600, 400)

        self.initUI()

    def initUI(self):
        # Üst kısım: Ürün ekleme
        self.urunAdiInput = QLineEdit(self)
        self.urunAdiInput.setPlaceholderText("Ürün Adı")

        self.urunKoduInput = QLineEdit(self)
        self.urunKoduInput.setPlaceholderText("Ürün Kodu")

        self.ekleButton = QPushButton("Ürün Ekle", self)
        self.ekleButton.clicked.connect(self.urunEkle)

        # Orta kısım: Tablo
        self.tablo = QTableWidget(self)
        self.tablo.setColumnCount(2)
        self.tablo.setHorizontalHeaderLabels(["Ürün Kodu", "Ürün Adı"])

        # Layout
        layout = QVBoxLayout()
        formLayout = QHBoxLayout()
        formLayout.addWidget(self.urunKoduInput)
        formLayout.addWidget(self.urunAdiInput)
        formLayout.addWidget(self.ekleButton)

        layout.addLayout(formLayout)
        layout.addWidget(self.tablo)

        self.setLayout(layout)

    def urunEkle(self):
        kod = self.urunKoduInput.text()
        ad = self.urunAdiInput.text()

        if kod and ad:
            satir = self.tablo.rowCount()
            self.tablo.insertRow(satir)
            self.tablo.setItem(satir, 0, QTableWidgetItem(kod))
            self.tablo.setItem(satir, 1, QTableWidgetItem(ad))
            self.urunKoduInput.clear()
            self.urunAdiInput.clear()

# Program başlatma
app = QApplication(sys.argv)
pencere = DepoUygulamasi()
pencere.show()
sys.exit(app.exec_())
