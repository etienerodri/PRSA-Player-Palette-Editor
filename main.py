import sys
from PyQt6.QtWidgets import QApplication
from gui.gui import PlayerSpriteEditor

def main():
    app = QApplication(sys.argv)
    window = PlayerSpriteEditor()
    window.show()
    sys.exit(app.exec())
if __name__ == '__main__':
    main()
