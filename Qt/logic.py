from Qt.gui import Ui_MainWindow
from PyQt5.QtWidgets import QMainWindow, QHeaderView, QTableWidgetItem, QShortcut, QListWidget
from PyQt5.QtCore import  QAbstractItemModel, Qt, QModelIndex, QVariant, QThread, QEvent, pyqtSignal
from PyQt5.QtGui import QKeySequence, QIcon
from shutil import copyfile
import core
import subprocess
import psutil
import fileinput

profile_manager = core.ProfileManager()
games = []

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow,self).__init__()
        self.main_window = Ui_MainWindow()
        self.main_window.setupUi(self)
        self.setup()
        self.connect_components()
        self.search_thread = SearchThread("")
    
    def setup(self):
        self.setWindowIcon(QIcon("icon.ico"))

        # Hidde Other Windows
        self.main_window.profile_create_window.setHidden(True)
        self.main_window.searching_frame.setHidden(True)
        self.main_window.set_steam_path_window.setHidden(True)
        self.main_window.closing_steam.setHidden(True)
        self.main_window.generic_popup.setHidden(True)
        self.main_window.settings_window.setHidden(True)
        #-------

        self.main_window.version_label.setText("v{0}".format(core.CURRENT_VERSION))
        self.main_window.no_hook_checkbox.setChecked(core.config.no_hook)
        self.main_window.compatibility_mode_checkbox.setChecked(core.config.compatibility_mode)
        self.populate_list(self.main_window.games_list, games)
        self.main_window.games_list.dropEvent = self.drop_event_handler
        self.populate_table(self.main_window.search_result, games)
        self.show_profile_names()
        self.show_profile_games(profile_manager.profiles[self.main_window.profile_selector.currentText()])
        self.setup_steam_path()
        self.setup_search_table()
        self.main_window.main_panel.raise_()

        # Settings Window Setup
        self.main_window.update_checkbox.setChecked(core.config.check_update)

        # Shortcuts
        del_game = QShortcut(QKeySequence(Qt.Key_Delete), self.main_window.games_list)
        del_game.activated.connect(self.remove_selected)

    def connect_components(self):
        # Profile
        self.main_window.create_profile.clicked.connect(lambda : self.toggle_widget(self.main_window.profile_create_window))
        self.main_window.create_profile_btn.clicked.connect(self.create_profile)
        self.main_window.cancel_profile_btn.clicked.connect(lambda : self.toggle_widget(self.main_window.profile_create_window))
        self.main_window.profile_selector.currentTextChanged.connect(self.select_profile)
        self.main_window.remove_game.clicked.connect(self.remove_selected)
        self.main_window.delete_profile.clicked.connect(self.delete_profile)

        # Steam Path
        self.main_window.save_steam_path.clicked.connect(self.set_steam_path)
        self.main_window.cancel_steam_path_btn.clicked.connect(lambda : self.toggle_widget(self.main_window.set_steam_path_window))

        # Search Area
        self.main_window.search_btn.clicked.connect(self.search_games)
        self.main_window.game_search_text.returnPressed.connect(self.search_games)
        self.main_window.add_to_profile.clicked.connect(self.add_selected)

        # Main Buttons
        self.main_window.generate_btn.clicked.connect(self.generate_app_list)
        self.main_window.run_GLR_btn.clicked.connect(lambda : self.show_popup("This will restart Steam if it's open do you want to continue?", self.run_GLR))
        
        # Settings Window
        self.main_window.settings_btn.clicked.connect(lambda : self.toggle_widget(self.main_window.settings_window))
        self.main_window.settings_save_btn.clicked.connect(self.save_settings)
        self.main_window.settings_cancel_btn.clicked.connect(lambda : self.toggle_widget(self.main_window.settings_window))
        
        # Popup Window
        self.main_window.popup_btn2.clicked.connect(lambda : self.toggle_widget(self.main_window.generic_popup, True))
    
    # Profile Functions
    def create_profile(self):
        name = self.main_window.profile_name.text()
        if name != "":
            profile_manager.create_profile(name)
            self.main_window.profile_selector.addItem(name)
            self.main_window.profile_name.clear()

            self.main_window.profile_selector.setCurrentIndex(self.main_window.profile_selector.count() - 1)
        
        self.toggle_widget(self.main_window.profile_create_window)

    def delete_profile(self):
        name = self.main_window.profile_selector.currentText()
        if name == "default":
            return
        
        profile_manager.remove_profile(name)

        index = self.main_window.profile_selector.currentIndex()
        self.main_window.profile_selector.removeItem(index)

    def select_profile(self, name):
        core.config.set_attributes({"last_profile": name})

        self.show_profile_games(profile_manager.profiles[name])

    def show_profile_games(self, profile):
        list_ = self.main_window.games_list

        self.populate_list(list_, profile.games)

    def show_profile_names(self):
        data = profile_manager.profiles.values()

        if core.config.last_profile in profile_manager.profiles.keys():
            self.main_window.profile_selector.addItem(core.config.last_profile)

        for item in data:
            if item.name != core.config.last_profile:
                self.main_window.profile_selector.addItem(item.name)

    # Search Functions
    def search_games(self):
        query = self.main_window.game_search_text.text()
        if query == "":
            return
        
        self.toggle_hidden(self.main_window.searching_frame)

        self.search_thread = SearchThread(query)
        self.search_thread.signal.connect(self.search_games_done)
        self.search_thread.start()

    def search_games_done(self, result):
        if type(result) is list:
            self.toggle_hidden(self.main_window.searching_frame)
            self.populate_table(self.main_window.search_result, result)
        else:
            self.toggle_hidden(self.main_window.searching_frame)
            self.show_popup("Can't connect to Steamdb. Check if you have internet connection.", lambda : self.toggle_widget(self.main_window.generic_popup, True))

    def setup_search_table(self):
        self.main_window.search_result.setColumnCount(3)

        header = self.main_window.search_result.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setMaximumSectionSize(580)
        header.sectionClicked.connect(lambda index : self.main_window.search_result.horizontalHeader().setSortIndicator(index, Qt.AscendingOrder))

        self.main_window.search_result.setHorizontalHeaderItem(0, QTableWidgetItem("Id"))
        self.main_window.search_result.setHorizontalHeaderItem(1, QTableWidgetItem("Name"))
        self.main_window.search_result.setHorizontalHeaderItem(2, QTableWidgetItem("Type"))
    
    def populate_list(self, list_, data):
        list_.clear()
        for item in data:
            list_.addItem(item.name)

    def populate_table(self, table, data):
        # Reset
        table.setSortingEnabled(False)
        table.clearSelection()
        table.setRowCount(0)
        #----
        table.setRowCount(len(data))

        for i, item in enumerate(data):
            for j, value in enumerate(item.to_list()):
                table_item = QTableWidgetItem(value)
                if j == 1:
                    table_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
                else:
                    table_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

                table.setItem(i, j, table_item)

        table.setSortingEnabled(True)

    # Search Table and Profile Interaction Functions
    def add_selected(self):
        items = self.main_window.search_result.selectedItems()
        if len(items) == 0:
            return
        
        profile = profile_manager.profiles[self.main_window.profile_selector.currentText()]

        for game in core.Game.from_table_list(items):
            if game not in profile.games:
                profile.add_game(game)

        self.show_profile_games(profile)
        profile.export_profile()

    def remove_selected(self):
        items = self.main_window.games_list.selectedItems()
        if len(items) == 0:
            return
        
        profile = profile_manager.profiles[self.main_window.profile_selector.currentText()]

        for item in items:
            profile.remove_game(item.text())

        self.show_profile_games(profile)
        profile.export_profile()

    # Settings Functions
    def save_settings(self):
        core.config.set_attributes({
            "steam_path": self.main_window.settings_steam_path.text(),
            "check_update": self.main_window.update_checkbox.isChecked()
        })

        self.toggle_widget(self.main_window.settings_window)

    # Generation Functions
    def run_GLR(self):
        self.toggle_widget(self.main_window.generic_popup,True)

        if not self.generate_app_list(False):
            return

        args = ["DLLInjector.exe", "-DisablePreferSystem32Images", "-CreateFile1", "NoQuestion.bin"]
        core.config.set_attributes({
            "no_hook": self.main_window.no_hook_checkbox.isChecked(),
            "compatibility_mode": self.main_window.compatibility_mode_checkbox.isChecked()
        })

        if core.config.compatibility_mode:
            self.replaceConfig("EnableMitigationsOnChildProcess"," 0")
        else:
            self.replaceConfig("EnableMitigationsOnChildProcess"," 1")

        if core.config.no_hook:
            args.append("-CreateFile2")
            args.append("NoHook.bin")
            self.replaceConfig("Exe"," Steam.exe")
        else:
            self.replaceConfig("Exe"," Steam.exe -inhibitbootstrap")


        core.os.chdir(core.config.steam_path)
        if self.is_steam_running():
            self.toggle_widget(self.main_window.closing_steam)
            subprocess.run(["Steam.exe", "-shutdown"]) #Shutdown Steam
            while self.is_steam_running():
                core.time.sleep(1)
            core.time.sleep(1)
        
        subprocess.Popen(args)
        self.close()

    def generate_app_list(self, popup = True):
        selected_profile = profile_manager.profiles[self.main_window.profile_selector.currentText()]

        if len(selected_profile.games) == 0:
            self.show_popup("No games to generate.", lambda : self.toggle_widget(self.main_window.generic_popup,True))
            return False
        
        core.createFiles(selected_profile.games)
        if(popup):
            self.show_popup("AppList Folder Generated", lambda : self.toggle_widget(self.main_window.generic_popup, True))

        return True

    # Util Functions
    def toggle_hidden(self, widget):
        widget.setHidden(not widget.isHidden())
        self.repaint()

    def toggle_enable(self, widget):
        widget.setEnabled(not widget.isEnabled())

    def toggle_widget(self, widget, force_close = False):
        if force_close:
            widget.lower()
            widget.setHidden(True)
            widget.setEnabled(False)
            return

        if widget.isHidden():
            widget.raise_()
        else:
            widget.lower()
        
        self.toggle_hidden(widget)
        self.toggle_enable(widget)

    def set_steam_path(self):
        path = self.main_window.steam_path.text()
        if not path == "":
            core.config.set_attributes({"steam_path": path})
        
        self.toggle_widget(self.main_window.set_steam_path_window)

    def setup_steam_path(self):
        if core.config.steam_path != "":
            self.main_window.settings_steam_path.setText(core.config.steam_path)
            return
        
        self.toggle_widget(self.main_window.set_steam_path_window)

    def drop_event_handler(self, event):
        self.add_selected()

    def show_popup(self, message, callback):
        self.main_window.popup_text.setText(message)
        self.main_window.popup_btn1.clicked.connect(callback)

        self.toggle_widget(self.main_window.generic_popup)

    def is_steam_running(self):
        for process in psutil.process_iter():
            if process.name() == "Steam.exe" or process.name() == "SteamService.exe" or process.name() == "steamwebhelper.exe":
                return True
        
        return False

    def replaceConfig(self, name, new_value):
        with fileinput.input(core.config.steam_path + "/DllInjector.ini", inplace=True) as fp:
            for line in fp:
                if not line.startswith("#"):
                    tokens = line.split("=")
                    if tokens[0].strip() == name:
                        tokens[1] = new_value
                        line = "=".join(tokens) + "\n"
                print(line, end = "")

class SearchThread(QThread):
    signal = pyqtSignal('PyQt_PyObject')

    def __init__(self, query):
        super(SearchThread, self).__init__()
        self.query = query

    def run(self):
        result = core.queryGames(self.query)
        self.signal.emit(result)
