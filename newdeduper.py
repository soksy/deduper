import os
import hashlib
import sys
from typing import Dict, List, Set, Tuple, Optional
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QFileDialog, QLabel, QProgressBar
from PyQt5.QtCore import QThread, pyqtSignal, QObject

class ScanWorker(QThread):
    progress = pyqtSignal(str)
    finished_scan = pyqtSignal(list, dict)
    error = pyqtSignal(str)
    
    def __init__(self, directories: List[str]) -> None:
        super().__init__()
        self.directories = directories
    
    def run(self) -> None:
        try:
            self.progress.emit("Starting scan...")
            dirs_with_dupes, files_dict = self.scan_function(self.directories)
            self.finished_scan.emit(dirs_with_dupes, files_dict)
        except Exception as e:
            self.error.emit(f"Scan error: {str(e)}")
    
    def scan_function(self, directories: List[str]) -> Tuple[List[str], Dict[str, List[str]]]:
        cksum_to_names = {}
        dirs_to_prioritise_set = set()
        
        total_files = 0
        processed_files = 0
        
        # Count total files first
        for directory in directories:
            for root, dirs, files in os.walk(directory):
                total_files += len(files)
        
        for directory in directories:
            self.progress.emit(f"Scanning directory: {directory}")
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = root.replace('\\','/') + '/' + file
                    processed_files += 1
                    
                    if processed_files % 10 == 0:  # Update progress every 10 files
                        self.progress.emit(f"Processed {processed_files}/{total_files} files")
                    
                    if os.path.getsize(file_path) == 0:
                        continue
                    
                    try:
                        each_file = File(file_path)
                        if each_file.cksum in cksum_to_names:
                            cksum_to_names[each_file.cksum].append(file_path)
                        else:
                            cksum_to_names[each_file.cksum] = [file_path]
                    except Exception as e:
                        self.progress.emit(f"Error processing {file_path}: {str(e)}")
                        continue
        
        for cksum in cksum_to_names:
            if len(cksum_to_names[cksum]) > 1:
                for file in cksum_to_names[cksum]:
                    dir_path = os.path.dirname(file)
                    dirs_to_prioritise_set.add(dir_path)
        
        return (list(dirs_to_prioritise_set), cksum_to_names)


class DedupeWorker(QThread):
    progress = pyqtSignal(str)
    finished_dedupe = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, dir_priority_list: List[str], files_dict: Dict[str, List[str]]) -> None:
        super().__init__()
        self.dir_priority_list = dir_priority_list
        self.files_dict = files_dict
    
    def run(self) -> None:
        try:
            self.progress.emit("Starting deduplication...")
            self.dedupe_function(self.dir_priority_list, self.files_dict)
            self.finished_dedupe.emit()
        except Exception as e:
            self.error.emit(f"Deduplication error: {str(e)}")
    
    def dedupe_function(self, dir_priority_list: List[str], cksum_to_names: Dict[str, List[str]]) -> None:
        dir_priorities = {}
        for dir_path in dir_priority_list:
            dir_priorities[dir_path] = dir_priority_list.index(dir_path)
        
        total_groups = len([cksum for cksum in cksum_to_names if len(cksum_to_names[cksum]) > 1])
        processed_groups = 0
        
        for cksum in cksum_to_names:
            if len(cksum_to_names[cksum]) > 1:
                processed_groups += 1
                self.progress.emit(f"Processing duplicate group {processed_groups}/{total_groups}")
                
                index_of_preferred = 0
                for path in cksum_to_names[cksum]:
                    if dir_priorities[os.path.dirname(path)] > dir_priorities[os.path.dirname(cksum_to_names[cksum][index_of_preferred])]:
                        index_of_preferred = cksum_to_names[cksum].index(path)
                
                for path in cksum_to_names[cksum]:
                    if path != cksum_to_names[cksum][index_of_preferred]:
                        try:
                            os.remove(path)
                            self.progress.emit(f"Deleted: {path}")
                        except Exception as e:
                            self.progress.emit(f"Could not delete {path}: {str(e)}")
                    else:
                        self.progress.emit(f"Kept: {cksum_to_names[cksum][index_of_preferred]}")


class MainApp(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.initUI()

    def initUI(self) -> None:
        self.setWindowTitle('File De-duper')
        self.setGeometry(100, 100, 1200, 400)

        mainLayout = QHBoxLayout()

        # Left Pane
        leftPane = QVBoxLayout()
        leftLabel = QLabel("Select Directories to Scan")
        self.dirListWidget = QListWidget()
        leftPane.addWidget(leftLabel)
        leftPane.addWidget(self.dirListWidget)

        leftButtonLayout = QHBoxLayout()
        self.addDirButton = QPushButton('Add Dir')
        self.delDirButton = QPushButton('Del Dir')
        self.delDirButton.setEnabled(False)
        self.scanButton = QPushButton('Scan')
        self.scanButton.setEnabled(False)
        self.dryRunButton = QPushButton('Dry Run')
        self.dryRunButton.setEnabled(False)
        self.dedupeButton = QPushButton('De-dupe')
        self.dedupeButton.setEnabled(False)
        self.exitButton = QPushButton('Exit')

        self.addDirButton.clicked.connect(self.addDirectory)
        self.delDirButton.clicked.connect(self.delDirectory)
        self.scanButton.clicked.connect(self.scan)
        self.dryRunButton.clicked.connect(self.dryRun)
        self.dedupeButton.clicked.connect(self.dedupe)
        self.exitButton.clicked.connect(self.exitApp)

        leftButtonLayout.addWidget(self.addDirButton)
        leftButtonLayout.addWidget(self.delDirButton)
        leftButtonLayout.addWidget(self.scanButton)
        leftButtonLayout.addWidget(self.dryRunButton)
        leftButtonLayout.addWidget(self.dedupeButton)
        leftButtonLayout.addWidget(self.exitButton)

        leftPane.addLayout(leftButtonLayout)
        
        # Add progress bar
        self.progressBar = QProgressBar()
        self.progressBar.setVisible(False)
        leftPane.addWidget(self.progressBar)
        
        # Add status label
        self.statusLabel = QLabel("Ready")
        leftPane.addWidget(self.statusLabel)

        # Middle Pane
        middlePane = QVBoxLayout()
        middleLabel = QLabel("Prioritise Directories (Lower in list preferred)")
        self.resultListWidget = QListWidget()
        middlePane.addWidget(middleLabel)
        self.resultListWidget.setDragDropMode(QListWidget.InternalMove)
        middlePane.addWidget(self.resultListWidget)

        middleButtonLayout = QHBoxLayout()
        self.upButton = QPushButton('Up')
        self.upButton.setEnabled(False)
        self.downButton = QPushButton('Down')
        self.downButton.setEnabled(False)
        self.setButton = QPushButton('Set')
        self.setButton.setEnabled(False)

        self.upButton.clicked.connect(self.moveUp)
        self.downButton.clicked.connect(self.moveDown)
        self.setButton.clicked.connect(self.setOrder)

        middleButtonLayout.addWidget(self.upButton)
        middleButtonLayout.addWidget(self.downButton)
        middleButtonLayout.addWidget(self.setButton)

        middlePane.addLayout(middleButtonLayout)
        
        # Add spacer to align with left pane
        middlePane.addWidget(QLabel(""))
        middlePane.addWidget(QLabel(""))

        # Right Pane (Files to Delete)
        rightPane = QVBoxLayout()
        rightLabel = QLabel("Files to Delete (Dry Run)")
        self.filesToDeleteListWidget = QListWidget()
        rightPane.addWidget(rightLabel)
        rightPane.addWidget(self.filesToDeleteListWidget)
        
        # Add spacer to align with left and middle panes
        rightPane.addWidget(QLabel(""))
        rightPane.addWidget(QLabel(""))
        rightPane.addWidget(QLabel(""))

        # Set equal stretch for all panes
        leftPaneWidget = QWidget()
        leftPaneWidget.setLayout(leftPane)
        middlePaneWidget = QWidget()
        middlePaneWidget.setLayout(middlePane)
        rightPaneWidget = QWidget()
        rightPaneWidget.setLayout(rightPane)
        
        mainLayout.addWidget(leftPaneWidget, 1)
        mainLayout.addWidget(middlePaneWidget, 1)
        mainLayout.addWidget(rightPaneWidget, 1)

        self.setLayout(mainLayout)
        
        # Initialize worker threads
        self.scan_worker: Optional[ScanWorker] = None
        self.dedupe_worker: Optional[DedupeWorker] = None

    def addDirectory(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if dir_path:
            QListWidgetItem(dir_path, self.dirListWidget)
            self.scanButton.setEnabled(True)
            self.delDirButton.setEnabled(True)

    def delDirectory(self) -> None:
        current_row = self.dirListWidget.currentRow()
        if current_row >= 0:
            self.dirListWidget.takeItem(current_row)
            if self.dirListWidget.count() == 0:
                self.scanButton.setEnabled(False)
                self.delDirButton.setEnabled(False)

    def scan(self) -> None:
        directories = [self.dirListWidget.item(i).text() for i in range(self.dirListWidget.count())]
        
        # Disable buttons during scan
        self.addDirButton.setEnabled(False)
        self.scanButton.setEnabled(False)
        self.progressBar.setVisible(True)
        self.progressBar.setRange(0, 0)  # Indeterminate progress
        
        # Start scan worker
        self.scan_worker = ScanWorker(directories)
        self.scan_worker.progress.connect(self.update_status)
        self.scan_worker.finished_scan.connect(self.on_scan_finished)
        self.scan_worker.error.connect(self.on_scan_error)
        self.scan_worker.start()

    def on_scan_finished(self, dirs_with_dupes: List[str], files_dict: Dict[str, List[str]]) -> None:
        self.filesDict = files_dict
        self.populateRightPane(dirs_with_dupes)
        
        # Re-enable buttons
        self.addDirButton.setEnabled(True)
        self.scanButton.setEnabled(True)
        self.upButton.setEnabled(True)
        self.downButton.setEnabled(True)
        self.setButton.setEnabled(True)
        
        self.progressBar.setVisible(False)
        self.update_status("Scan completed")
    
    def on_scan_error(self, error_msg: str) -> None:
        self.addDirButton.setEnabled(True)
        self.scanButton.setEnabled(True)
        self.progressBar.setVisible(False)
        self.update_status(f"Scan failed: {error_msg}")

    def populateRightPane(self, items: List[str]) -> None:
        self.resultListWidget.clear()
        for item in items:
            QListWidgetItem(item, self.resultListWidget)

    def dedupe(self) -> None:
        # Disable buttons during deduplication
        self.dedupeButton.setEnabled(False)
        self.upButton.setEnabled(False)
        self.downButton.setEnabled(False)
        self.setButton.setEnabled(False)
        self.progressBar.setVisible(True)
        self.progressBar.setRange(0, 0)  # Indeterminate progress
        
        # Start dedupe worker
        self.dedupe_worker = DedupeWorker(self.dirPriorityList, self.filesDict)
        self.dedupe_worker.progress.connect(self.update_status)
        self.dedupe_worker.finished_dedupe.connect(self.on_dedupe_finished)
        self.dedupe_worker.error.connect(self.on_dedupe_error)
        self.dedupe_worker.start()

    def on_dedupe_finished(self) -> None:
        # Re-enable buttons
        self.addDirButton.setEnabled(True)
        self.scanButton.setEnabled(True)
        
        self.progressBar.setVisible(False)
        self.update_status("Deduplication completed")
    
    def on_dedupe_error(self, error_msg: str) -> None:
        self.dedupeButton.setEnabled(True)
        self.upButton.setEnabled(True)
        self.downButton.setEnabled(True)
        self.setButton.setEnabled(True)
        self.progressBar.setVisible(False)
        self.update_status(f"Deduplication failed: {error_msg}")
    
    def update_status(self, message: str) -> None:
        self.statusLabel.setText(message)

    def moveUp(self) -> None:
        currentRow = self.resultListWidget.currentRow()
        if currentRow > 0:
            currentItem = self.resultListWidget.takeItem(currentRow)
            self.resultListWidget.insertItem(currentRow - 1, currentItem)
            self.resultListWidget.setCurrentRow(currentRow - 1)

    def moveDown(self) -> None:
        currentRow = self.resultListWidget.currentRow()
        if currentRow < self.resultListWidget.count() - 1:
            currentItem = self.resultListWidget.takeItem(currentRow)
            self.resultListWidget.insertItem(currentRow + 1, currentItem)
            self.resultListWidget.setCurrentRow(currentRow + 1)

    def setOrder(self) -> None:
        self.dirPriorityList = [self.resultListWidget.item(i).text() for i in range(self.resultListWidget.count())]
        self.dedupeButton.setEnabled(True)
        self.dryRunButton.setEnabled(True)
        self.update_status(f"Priority order set for {len(self.dirPriorityList)} directories")

    def dryRun(self) -> None:
        if not hasattr(self, 'dirPriorityList') or not hasattr(self, 'filesDict'):
            self.update_status("Please scan and set priority order first")
            return
        
        self.filesToDeleteListWidget.clear()
        files_to_delete = self.generateFilesToDelete(self.dirPriorityList, self.filesDict)
        
        for file_path in files_to_delete:
            QListWidgetItem(file_path, self.filesToDeleteListWidget)
        
        self.update_status(f"Dry run completed - {len(files_to_delete)} files would be deleted")

    def generateFilesToDelete(self, dir_priority_list: List[str], cksum_to_names: Dict[str, List[str]]) -> List[str]:
        dir_priorities = {}
        for dir_path in dir_priority_list:
            dir_priorities[dir_path] = dir_priority_list.index(dir_path)
        
        files_to_delete = []
        
        for cksum in cksum_to_names:
            if len(cksum_to_names[cksum]) > 1:
                index_of_preferred = 0
                for path in cksum_to_names[cksum]:
                    if dir_priorities[os.path.dirname(path)] > dir_priorities[os.path.dirname(cksum_to_names[cksum][index_of_preferred])]:
                        index_of_preferred = cksum_to_names[cksum].index(path)
                
                for path in cksum_to_names[cksum]:
                    if path != cksum_to_names[cksum][index_of_preferred]:
                        files_to_delete.append(path)
        
        return sorted(files_to_delete)

    def exitApp(self) -> None:
        self.close()

class File:
    def __init__(self, filename: str) -> None:
        self.fullFilename = filename
        self.basename = os.path.basename(filename)
        self.dirname = os.path.dirname(filename)
        self.cksum = self.generate_checksum()

    def generate_checksum(self) -> str:
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