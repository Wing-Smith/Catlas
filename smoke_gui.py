import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, ".")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

app = QApplication(sys.argv)
from app.ui.main_window import MainWindow
from app.ui.theme import apply_fluent_theme
apply_fluent_theme()
w = MainWindow()
w.show()
app.processEvents()
w.grab().save("gui_smoke.png")
print("SMOKE OK, size:", w.size())
QTimer.singleShot(100, app.quit)
app.exec()
