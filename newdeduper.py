import os
import hashlib
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QFileDialog, QLabel

class MainApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('File De-duper')
        self.setGeometry(100, 100, 800, 400)

        mainLayout = QHBoxLayout()

        # Left Pane
        leftPane = QVBoxLayout()
        leftLabel = QLabel("Select Directories to Scan")
        self.dirListWidget = QListWidget()
        leftPane.addWidget(leftLabel)
        leftPane.addWidget(self.dirListWidget)

        leftButtonLayout = QHBoxLayout()
        self.addDirButton = QPushButton('Add Dir')
        self.scanButton = QPushButton('Scan')
        self.scanButton.setEnabled(False)
        self.dedupeButton = QPushButton('De-dupe')
        self.dedupeButton.setEnabled(False)
        self.exitButton = QPushButton('Exit')

        self.addDirButton.clicked.connect(self.addDirectory)
        self.scanButton.clicked.connect(self.scan)
        self.dedupeButton.clicked.connect(self.dedupe)
        self.exitButton.clicked.connect(self.exitApp)

        leftButtonLayout.addWidget(self.addDirButton)
        leftButtonLayout.addWidget(self.scanButton)
        leftButtonLayout.addWidget(self.dedupeButton)
        leftButtonLayout.addWidget(self.exitButton)

        leftPane.addLayout(leftButtonLayout)

        # Right Pane
        rightPane = QVBoxLayout()
        rightLabel = QLabel("Prioritise Directories (Lower in list preferred)")
        self.resultListWidget = QListWidget()
        rightPane.addWidget(rightLabel)
        self.resultListWidget.setDragDropMode(QListWidget.InternalMove)
        rightPane.addWidget(self.resultListWidget)

        rightButtonLayout = QHBoxLayout()
        self.upButton = QPushButton('Up')
        self.upButton.setEnabled(False)
        self.downButton = QPushButton('Down')
        self.downButton.setEnabled(False)
        self.setButton = QPushButton('Set')
        self.setButton.setEnabled(False)

        self.upButton.clicked.connect(self.moveUp)
        self.downButton.clicked.connect(self.moveDown)
        self.setButton.clicked.connect(self.setOrder)

        rightButtonLayout.addWidget(self.upButton)
        rightButtonLayout.addWidget(self.downButton)
        rightButtonLayout.addWidget(self.setButton)

        rightPane.addLayout(rightButtonLayout)

        mainLayout.addLayout(leftPane)
        mainLayout.addLayout(rightPane)

        self.setLayout(mainLayout)

    def addDirectory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if dir_path:
            QListWidgetItem(dir_path, self.dirListWidget)
            self.scanButton.setEnabled(True)


    def scan(self):
        directories = [self.dirListWidget.item(i).text() for i in range(self.dirListWidget.count())]
        self.addDirButton.setEnabled(False)
        self.scanButton.setEnabled(False)
        self.upButton.setEnabled(True)
        self.downButton.setEnabled(True)
        self.setButton.setEnabled(True)
        print("Scanning directories:", directories)
        dirsWithDupes, self.filesDict = self.scanFunction(directories)
        self.populateRightPane(dirsWithDupes)

    def scanFunction(self, directories):
        cksumToNames = {}
        dirsToPrioritiseSet = set()

        for directory in directories:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    filePath = root.replace('\\','/') + '/' + file
                    if os.path.getsize(filePath) == 0:
                        continue
                    eachFile = File(filePath)
                    if eachFile.cksum in cksumToNames:
                        cksumToNames[eachFile.cksum].append(filePath)
                    else:
                        cksumToNames[eachFile.cksum] = [filePath]

        for cksum in cksumToNames:
            if len(cksumToNames[cksum]) > 1:
                for file in cksumToNames[cksum]:
                    dir = os.path.dirname(file)
                    dirsToPrioritiseSet.add(dir)

        return (list(dirsToPrioritiseSet), cksumToNames)

    def populateRightPane(self, items):
        self.resultListWidget.clear()
        for item in items:
            QListWidgetItem(item, self.resultListWidget)

    def dedupe(self):
        self.dedupeButton.setEnabled(False) 
        self.upButton.setEnabled(False)
        self.downButton.setEnabled(False)
        self.setButton.setEnabled(False)
        self.deDupeFunction(self.dirPriorityList, self.filesDict)

    def deDupeFunction(self, dirPriorityList, cksumToNames):
        dirPriorities = {}
        print("In DeDupeFunction", dirPriorityList)
        for dir in dirPriorityList:
            dirPriorities[dir] = dirPriorityList.index(dir)

        for cksum in cksumToNames:
            if len(cksumToNames[cksum]) > 1:
                indexOfPreferred = 0
                for path in cksumToNames[cksum]:
                    if dirPriorities[os.path.dirname(path)] > dirPriorities[os.path.dirname(cksumToNames[cksum][indexOfPreferred])]:
                        indexOfPreferred = cksumToNames[cksum].index(path)

                for path in cksumToNames[cksum]:
                    if path != cksumToNames[cksum][indexOfPreferred]:
                        try:
                            os.remove(path)
                            print("File {} deleted".format(path))
                        except Exception as e:
                            print("Could not delete file {}: {}".format(path,e))
                    else:
                        print('Keeping:', cksumToNames[cksum][indexOfPreferred])

    def moveUp(self):
        currentRow = self.resultListWidget.currentRow()
        if currentRow > 0:
            currentItem = self.resultListWidget.takeItem(currentRow)
            self.resultListWidget.insertItem(currentRow - 1, currentItem)
            self.resultListWidget.setCurrentRow(currentRow - 1)

    def moveDown(self):
        currentRow = self.resultListWidget.currentRow()
        if currentRow < self.resultListWidget.count() - 1:
            currentItem = self.resultListWidget.takeItem(currentRow)
            self.resultListWidget.insertItem(currentRow + 1, currentItem)
            self.resultListWidget.setCurrentRow(currentRow + 1)

    def setOrder(self):
        self.dirPriorityList = [self.resultListWidget.item(i).text() for i in range(self.resultListWidget.count())]
        self.dedupeButton.setEnabled(True)
        print("New order set:", self.dirPriorityList)

    def exitApp(self):
        self.close()

class File:
    def __init__(self, filename):
        self.fullFilename = filename
        self.basename = os.path.basename(filename)
        self.dirname = os.path.dirname(filename)
        self.cksum = self.generate_checksum()

    def generate_checksum(self):
        hash_func = hashlib.new('sha256')
        with open(self.fullFilename, 'rb') as f:
            while chunk := f.read(8192):
                hash_func.update(chunk)
        return hash_func.hexdigest()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    mainApp = MainApp()
    mainApp.show()
    sys.exit(app.exec_())