import sys
import pyodbc
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QInputDialog, QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton, QMessageBox, QLineEdit,
    QComboBox, QGroupBox, QCheckBox, QDialog, QDialogButtonBox, QListWidget, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QDesktopWidget  # Adicione essa linha para importar a classe QTableWidgetItem
)

class OSProfileManager(QDialog):
    def __init__(self, conn, current_user_id, company_code, selected_locations, parent=None):
        super(OSProfileManager, self).__init__(parent)
        self.conn = conn
        self.user_id = current_user_id
        self.company_code = company_code
        self.selected_locations = selected_locations
        self.init_ui()
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint & ~Qt.WindowContextHelpButtonHint)

    def init_ui(self):
        layout = QVBoxLayout()

        # Label de instrução
        instruction_label = QLabel("Deseja copiar o perfil de outro usuário ou procurar na lista?")
        layout.addWidget(instruction_label)

        # Botões de ação
        self.copy_from_user_btn = QPushButton("Copiar de outro usuário")
        self.copy_from_user_btn.clicked.connect(self.copy_from_user)
        layout.addWidget(self.copy_from_user_btn)

        self.search_from_list_btn = QPushButton("Procurar na lista")
        self.search_from_list_btn.clicked.connect(self.search_from_list)
        layout.addWidget(self.search_from_list_btn)

        self.setLayout(layout)
        self.setWindowTitle("Gerenciador de Perfis OS")
        self.setModal(True)

    def copy_from_user(self):
        self.user_search_dialog = QDialog(self)
        layout = QVBoxLayout()

        # Input para pesquisa de usuário
        self.search_label = QLabel('Digite o nome do usuário:')
        self.search_input = QLineEdit()
        self.search_input.textChanged.connect(self.perform_search)

        layout.addWidget(self.search_label)
        layout.addWidget(self.search_input)

        # Widget de lista para resultados de pesquisa
        self.user_list_widget = QListWidget()
        layout.addWidget(QLabel('Resultados da Pesquisa de Usuários:'))
        layout.addWidget(self.user_list_widget)

        self.copy_menus_button = QPushButton('Copiar Menus')
        self.copy_menus_button.clicked.connect(self.copy_menus_for_user)
        layout.addWidget(self.copy_menus_button)

        self.user_search_dialog.setLayout(layout)
        self.user_search_dialog.setWindowTitle("Pesquisar Usuário")
        self.user_search_dialog.setModal(True)
        self.user_search_dialog.show()

    def perform_search(self):
        search_name = self.search_input.text().strip().upper()
        if search_name:
            search_results = self.search_users_by_name(search_name)
            self.show_user_search_results(search_results)

    def show_user_search_results(self, search_results):
        self.user_list_widget.clear()
        if not search_results:
            QMessageBox.warning(self, 'Usuário não encontrado', 'Nenhum usuário encontrado para o critério de busca.')
            return

        for result in search_results:
            user_item = QListWidgetItem(f"Empresa: {result['Empresa']} - {result['Usuário']}")
            user_item.setData(Qt.UserRole, result['SEQUENCIA_USU'])
            self.user_list_widget.addItem(user_item)

    def search_users_by_name(self, search_name):
        search_results = []
        if not self.conn:
            return []

        try:
            cursor = self.conn.cursor()
            query = "SELECT codigoempresa as Empresa, usuario as Usuário, SEQUENCIA_USU FROM USUARIOS WHERE usuario LIKE ? and codigoempresa=?"
            cursor.execute(query, ('%' + search_name + '%', self.company_code))
            for row in cursor.fetchall():
                result = {
                    'Empresa': row[0],
                    'Usuário': row[1],
                    'SEQUENCIA_USU': row[2]
                }
                search_results.append(result)
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao buscar usuários: {str(e)}')

        return search_results

    def copy_menus_for_user(self):
        selected_user_item = self.user_list_widget.currentItem()
        if not selected_user_item:
            QMessageBox.warning(self, 'Seleção Inválida', 'Por favor, selecione um usuário da lista.')
            return

        selected_user_id = selected_user_item.data(Qt.UserRole)
        if not selected_user_id:
            QMessageBox.warning(self, 'Erro', 'Não foi possível obter o ID do usuário selecionado.')
            return

        if not self.has_registered_profile(selected_user_id, self.company_code):
            QMessageBox.warning(self, 'Aviso', 'Usuário selecionado não possui perfil cadastrado para essa empresa, selecione outro.')
            return

        # Verificar os perfis do usuário selecionado
        profiles = self.get_user_profiles(selected_user_id)
        if len(profiles) > 1:
            profile_dialog = self.show_profile_selection_dialog(profiles)
            if profile_dialog.exec_() == QDialog.Accepted:
                selected_profile = profile_dialog.selected_profile
            else:
                return
        else:
            selected_profile = profiles[0]['Id']

        try:
            cursor = self.conn.cursor()
            for location in self.selected_locations:
                insert_query = f"""INSERT INTO "DBA"."OS_Usuarios_Perfis" ("SEQUENCIA_USU","FK_Perfil","Empresa","Local")
                                  VALUES(?, ?, ?, ?)"""
                cursor.execute(insert_query, (self.user_id, selected_profile, self.company_code, location['cod_local']))
            self.conn.commit()
            QMessageBox.information(self, 'Sucesso', 'Perfil copiado com sucesso!')
            self.user_search_dialog.close()
            self.reject()
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao copiar perfil: {str(e)}')

    def get_user_profiles(self, user_id):
        profiles = []
        try:
            cursor = self.conn.cursor()
            query = f"""SELECT Id, Descricao 
                        FROM os_perfis 
                        WHERE empresa = ? 
                        AND id IN (SELECT DISTINCT(fk_perfil) 
                                   FROM OS_Usuarios_Perfis 
                                   WHERE sequencia_usu=? AND empresa=?)"""
            cursor.execute(query, (self.company_code, user_id, self.company_code))
            for row in cursor.fetchall():
                profiles.append({'Id': row[0], 'Descricao': row[1]})
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao buscar perfis do usuário: {str(e)}')
        return profiles

    def show_profile_selection_dialog(self, profiles):
        dialog = QDialog(self)
        layout = QVBoxLayout()
        combo_box = QComboBox()
        for profile in profiles:
            combo_box.addItem(profile['Descricao'], profile['Id'])
        layout.addWidget(QLabel("O usuário está cadastrado em mais de um perfil, qual você deseja escolher?"))
        layout.addWidget(combo_box)
        ok_button = QPushButton("Ok")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)
        dialog.setLayout(layout)
        dialog.setModal(True)

        # Atualizar o perfil selecionado sempre que o índice do combo box mudar
        def update_selected_profile(index):
            dialog.selected_profile = combo_box.itemData(index)

        combo_box.currentIndexChanged.connect(update_selected_profile)
        # Definir o perfil selecionado inicialmente
        dialog.selected_profile = combo_box.currentData()
        return dialog

    def search_from_list(self):
        self.profile_window = QDialog(self)
        layout = QVBoxLayout()

        # Lista de perfis
        self.profile_list = QComboBox()
        cursor = self.conn.cursor()
        profiles_query = f"SELECT Id, Descricao FROM os_perfis WHERE empresa=?"
        cursor.execute(profiles_query, (self.company_code,))
        profiles = cursor.fetchall()
        for profile in profiles:
            self.profile_list.addItem(profile[1], profile[0])
        layout.addWidget(self.profile_list)

        # Botão de seleção
        select_btn = QPushButton("Selecionar")
        select_btn.clicked.connect(self.select_profile)
        layout.addWidget(select_btn)

        self.profile_window.setLayout(layout)
        self.profile_window.setWindowTitle("Selecionar Perfil")
        self.profile_window.setModal(True)
        self.profile_window.setFixedWidth(250)
        self.profile_window.show()

    def select_profile(self):
        selected_profile_id = self.profile_list.currentData()
        try:
            cursor = self.conn.cursor()
            for location in self.selected_locations:
                insert_query = f"""INSERT INTO "DBA"."OS_Usuarios_Perfis" ("SEQUENCIA_USU","FK_Perfil","Empresa","Local")
                                  VALUES(?, ?, ?, ?)"""
                cursor.execute(insert_query,
                               (self.user_id, selected_profile_id, self.company_code, location['cod_local']))
            self.conn.commit()
            QMessageBox.information(self, 'Sucesso', 'Perfil selecionado com sucesso!')
            self.profile_window.close()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao selecionar perfil: {str(e)}')

    def has_registered_profile(self, user_id, company_code):
        try:
            cursor = self.conn.cursor()

            # Verificar se o usuário tem um perfil registrado para a empresa selecionada
            query = """SELECT COUNT(*) FROM "DBA"."OS_Usuarios_Perfis" 
                       WHERE "SEQUENCIA_USU"=? AND "Empresa"=?"""
            cursor.execute(query, (user_id, company_code))
            count = cursor.fetchone()[0]

            # Se o usuário não tiver um perfil registrado, retornar False
            if count == 0:
                return False
            return True
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao verificar perfil registrado: {str(e)}')
            return False

    @staticmethod
    def has_registered_profiles_for_company(conn, company_code):
        try:
            cursor = conn.cursor()
            query = f"SELECT COUNT(*) FROM os_perfis WHERE empresa=?"
            cursor.execute(query, (company_code,))
            count = cursor.fetchone()[0]
            return count > 0
        except Exception as e:
            QMessageBox.critical(None, 'Erro', f'Erro ao verificar perfis cadastrados: {str(e)}')
            return False

class LocationOptionsDialog(QDialog):
    def __init__(self, conn, company_code, main_window=None, parent=None):
        super(LocationOptionsDialog, self).__init__(parent)
        self.conn = conn
        self.company_code = company_code
        self.setWindowTitle("Opções de Locais")
        self.setGeometry(100, 100, 400, 300)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint & ~Qt.WindowContextHelpButtonHint)
        self.init_ui()
        self.centerOnScreen()

    def init_ui(self):
        self.location_checkboxes = {}
        locations = self.get_locations()
        for location in locations:
            checkbox = QCheckBox(f"{location['cod_local']} - {location['nome_local']}", self)
            self.location_checkboxes[location['cod_local']] = checkbox

        self.select_all_button = QPushButton("Selecionar Todos", self)
        self.select_all_button.clicked.connect(self.select_all_locations)

        self.deselect_all_button = QPushButton("Desmarcar Todos", self)
        self.deselect_all_button.clicked.connect(self.deselect_all_locations)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok, self)
        self.button_box.accepted.connect(self.accept)

        layout = QVBoxLayout(self)

        for checkbox in self.location_checkboxes.values():
            layout.addWidget(checkbox)

        layout.addWidget(self.select_all_button)
        layout.addWidget(self.deselect_all_button)
        layout.addWidget(self.button_box)

        # Ajuste automático da altura com base na quantidade de locais
        num_locations = len(self.location_checkboxes)
        base_height = 100  # altura base para a janela
        checkbox_height = 30  # altura estimada para cada checkbox
        max_height = 600  # altura máxima para a janela

        total_height = base_height + (num_locations * checkbox_height)
        self.setFixedHeight(min(total_height, max_height))

    def get_locations(self):
        locations = []
        if not self.conn:
            return locations

        try:
            cursor = self.conn.cursor()
            query = f"SELECT lcl001 as cod_local, lcl002 as nome_local FROM ges_008 WHERE empresa={self.company_code}"
            cursor.execute(query)
            for row in cursor.fetchall():
                location = {"cod_local": row.cod_local, "nome_local": row.nome_local}
                locations.append(location)

        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao obter locais: {str(e)}')

        return locations

    def select_all_locations(self):
        for checkbox in self.location_checkboxes.values():
            checkbox.setChecked(True)

    def deselect_all_locations(self):
        for checkbox in self.location_checkboxes.values():
            checkbox.setChecked(False)

    def get_selected_locations(self):
        selected_locations = []
        for cod_local, checkbox in self.location_checkboxes.items():
            if checkbox.isChecked():
                selected_locations.append({"cod_local": cod_local})

        return selected_locations

    def accept(self):
        selected_locations = self.get_selected_locations()
        if not selected_locations:
            QMessageBox.warning(self, 'Aviso', 'Selecione ao menos um local para cadastrar o usuário.')
        else:
            super().accept()

    def centerOnScreen(self):
        resolution = QDesktopWidget().screenGeometry()
        self.move(int((resolution.width() / 2) - (self.frameSize().width() / 2)),
                  int((resolution.height() / 2) - (self.frameSize().height() / 2)))

class UserSearchDialog(QDialog):
    def __init__(self, conn, current_user_id, parent=None):
        super(UserSearchDialog, self).__init__(parent)
        self.conn = conn
        self.current_user_id = current_user_id  # Adicionado aqui
        self.setWindowTitle('Pesquisar Usuário')
        self.setGeometry(200, 200, 400, 300)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint & ~Qt.WindowContextHelpButtonHint)
        layout = QVBoxLayout(self)

        # Input for user search
        self.search_label = QLabel('Digite o nome do usuário:', self)
        self.search_input = QLineEdit(self)
        self.search_input.textChanged.connect(self.perform_search)

        layout.addWidget(self.search_label)
        layout.addWidget(self.search_input)

        # List widget for search results
        self.user_list_widget = QListWidget(self)
        layout.addWidget(QLabel('Resultados da Pesquisa de Usuários:', self))
        layout.addWidget(self.user_list_widget)

        self.copy_menus_button = QPushButton('Copiar Menus', self)
        self.copy_menus_button.clicked.connect(self.copy_menus_for_user)
        layout.addWidget(self.copy_menus_button)

        self.user_list_widget.itemSelectionChanged.connect(self.enable_copy_menus_button)
        self.centerOnScreen()

    def perform_search(self):
        search_name = self.search_input.text().strip().upper()
        if search_name:
            search_results = self.search_users_by_name(search_name)
            self.show_user_search_results(search_results)

    def show_user_search_results(self, search_results):
        self.user_list_widget.clear()
        if not search_results:
            QMessageBox.warning(self, 'Usuário não encontrado', 'Nenhum usuário encontrado para o critério de busca.')
            return

        for result in search_results:
            user_item = QListWidgetItem(f"Empresa: {result['Codigo_Empresa']} - {result['Usuário']}")
            user_item.setData(Qt.UserRole, result['SEQUENCIA_USU'])
            self.user_list_widget.addItem(user_item)

    def has_custom_menus(self, user_id):
        try:
            cursor = self.conn.cursor()

            # Verificar SEGMENSISCREATE
            query1 = "SELECT COUNT(*) FROM SEGMENSISCREATE WHERE SEQUENCIA_USUS=?"
            cursor.execute(query1, (user_id,))
            count1 = cursor.fetchone()[0]

            # Verificar SEGTOOLCREATE
            query2 = "SELECT COUNT(*) FROM SEGTOOLCREATE WHERE SEQUENCIA_USUS=?"
            cursor.execute(query2, (user_id,))
            count2 = cursor.fetchone()[0]

            # Se não houver menus personalizados em uma ou ambas as tabelas, retornar False
            if count1 == 0 or count2 == 0:
                return False
            return True
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao verificar menus personalizados: {str(e)}')
            return False

    def copy_menus_for_user(self):
        selected_user_item = self.user_list_widget.currentItem()
        if not selected_user_item:
            QMessageBox.warning(self, 'Seleção Inválida', 'Por favor, selecione um usuário da lista.')
            return

        selected_user_id = selected_user_item.data(Qt.UserRole)
        if not selected_user_id:
            QMessageBox.warning(self, 'Erro', 'Não foi possível obter o ID do usuário selecionado.')
            return

        if not self.has_custom_menus(selected_user_id):
            reply = QMessageBox.question(self, 'Aviso',
                                         'Usuário selecionado não possui menus personalizados cadastrados, deseja continuar mesmo assim?',
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return

        try:
            cursor = self.conn.cursor()

            # Copiar menus da tabela SEGMENSISCREATE
            query = f"INSERT INTO SEGMENSISCREATE (SEQUENCIA_USUS, CODIGOSISTEMA, CODIGOMENU, TIPO, DESCRICAOMENU, PARENTCONTROL, NOMEPROCEDURE, KEYCODE, CODIGORELATORIO) SELECT {self.current_user_id}, CODIGOSISTEMA, CODIGOMENU, TIPO, DESCRICAOMENU, PARENTCONTROL, NOMEPROCEDURE, KEYCODE, CODIGORELATORIO FROM SEGMENSISCREATE WHERE SEQUENCIA_USUS = {selected_user_id}"
            cursor.execute(query)

            # Copiar menus da tabela SEGTOOLCREATE
            query = f"INSERT INTO SEGTOOLCREATE (SEQUENCIA_USUS, CODIGOSISTEMA, CODIGOBOTAO, ICONE, PARENTCONTROL, NOMEPROCEDURE, TIP, STD, KEYCODE) SELECT {self.current_user_id}, CODIGOSISTEMA, CODIGOBOTAO, ICONE, PARENTCONTROL, NOMEPROCEDURE, TIP, STD, KEYCODE FROM SEGTOOLCREATE WHERE SEQUENCIA_USUS = {selected_user_id}"
            cursor.execute(query)

            self.conn.commit()

            QMessageBox.information(self, 'Sucesso', 'Menus personalizados copiados com sucesso!')
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao copiar menus personalizados: {str(e)}')

    def enable_copy_menus_button(self):
        selected_user_item = self.user_list_widget.currentItem()
        if selected_user_item:
            self.copy_menus_button.setEnabled(True)
        else:
            self.copy_menus_button.setEnabled(False)

    def search_users_by_name(self, search_name):
        search_results = []
        if not self.conn:
            return False

        try:
            # Aqui, certifique-se de que está usando o cursor do banco de dados
            cursor = self.conn.cursor()
            query = "SELECT codigoempresa as Codigo_Empresa, usuario as Usuário, nivel as Nível, sequencia_usu as SEQUENCIA_USU FROM USUARIOS WHERE usuario LIKE ?"
            cursor.execute(query, ('%' + search_name + '%',))
            for row in cursor.fetchall():
                result = {
                    'Codigo_Empresa': row.Codigo_Empresa,
                    'Usuário': row.Usuário,
                    'Nível': row.Nível,
                    'SEQUENCIA_USU': row.SEQUENCIA_USU,
                }
                search_results.append(result)

        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao buscar usuários: {str(e)}')

        return search_results

    def closeEvent(self, event):
        # Ignora o evento de fechamento para evitar que a janela seja fechada
        event.ignore()

    def centerOnScreen(self):
        resolution = QDesktopWidget().screenGeometry()
        self.move(int((resolution.width() / 2) - (self.frameSize().width() / 2)),
                  int((resolution.height() / 2) - (self.frameSize().height() / 2)))

class CustomMessageBox(QMessageBox):
    def closeEvent(self, event):
        event.ignore()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cadastrador de Usuários")
        self.setGeometry(100, 100, 400, 350)
        self.conn = None  # Add the 'conn' attribute and initialize it as None
        self.new_sequence = None
        self.init_ui()

    def init_ui(self):
        self.odbc_combobox = QComboBox(self)
        self.update_dsn_list()
        self.odbc_combobox.currentIndexChanged.connect(self.update_connect_button_state)

        self.connect_button = QPushButton("Conectar", self)
        self.connect_button.clicked.connect(self.connect_to_database)

        self.info_label = QLabel("Selecione uma DSN para conectar ao banco de dados Sybase 12:", self)

        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.info_label)
        self.main_layout.addWidget(self.odbc_combobox)
        self.main_layout.addWidget(self.connect_button)

        self.central_widget = QWidget(self)
        self.central_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.central_widget)

        self.user_form_widget = QWidget(self)
        self.user_form_widget.setDisabled(True)
        self.user_form_layout = QVBoxLayout(self.user_form_widget)

        self.user_label = QLabel("Usuário:", self)
        self.user_input = QLineEdit(self)
        self.user_form_layout.addWidget(self.user_label)
        self.user_form_layout.addWidget(self.user_input)

        self.password_label = QLabel("Senha:", self)
        self.password_input = QLineEdit(self)
        self.user_form_layout.addWidget(self.password_label)
        self.user_form_layout.addWidget(self.password_input)

        self.company_code_label = QLabel("Código da Empresa:", self)
        self.company_code_input = QComboBox(self)
        self.user_form_layout.addWidget(self.company_code_label)
        self.user_form_layout.addWidget(self.company_code_input)

        self.user_level_label = QLabel("Nível do Usuário:", self)
        self.user_level_input = QComboBox(self)
        self.user_level_input.addItem("1", 1)  # Add item with data (value) 1
        self.user_level_input.addItem("2", 2)  # Add item with data (value) 2
        self.user_form_layout.addWidget(self.user_level_label)
        self.user_form_layout.addWidget(self.user_level_input)

        self.submit_button = QPushButton("Cadastrar Usuário", self)
        self.submit_button.clicked.connect(self.check_and_insert_new_user)
        self.user_form_layout.addWidget(self.submit_button)

        self.main_layout.addWidget(self.user_form_widget)

        self.location_options_dialog = None

    def update_dsn_list(self):
        self.odbc_combobox.clear()
        dsn_list = pyodbc.dataSources()
        for dsn in sorted(dsn_list):
            self.odbc_combobox.addItem(dsn)

    def update_connect_button_state(self):
        selected_odbc = self.odbc_combobox.currentText()
        self.connect_button.setDisabled(selected_odbc == "")

    def connect_to_database(self):
        selected_odbc = self.odbc_combobox.currentText()
        try:
            self.conn = pyodbc.connect('DSN=' + selected_odbc)
            QMessageBox.information(self, 'Conexão', 'Conexão estabelecida com sucesso!')
            self.connect_button.setDisabled(True)
            self.odbc_combobox.setDisabled(True)
            self.user_form_widget.setDisabled(False)
            self.update_company_codes()  # Call the method to populate the company codes dropdown
        except Exception as e:
            QMessageBox.critical(self, 'Erro de conexão', f'Erro ao conectar ao banco de dados: {str(e)}')
            self.conn = None

    def check_and_insert_new_user(self):
        username = self.user_input.text().strip().upper()
        password = self.password_input.text().strip()
        company_code = self.company_code_input.currentData()
        user_level = self.user_level_input.currentData()

        if not username or not password or not company_code or not user_level:
            QMessageBox.critical(self, 'Erro', 'Preencha todos os campos antes de cadastrar o usuário.')
            return

        try:
            if self.is_username_exists_for_company(username, company_code):
                QMessageBox.critical(self, 'Erro',
                                     'Usuário já cadastrado para a empresa informada. Insira um nome de usuário diferente.')
            elif self.is_username_exists_for_other_company(username, company_code):
                reply = QMessageBox.question(self, 'Usuário Existente',
                                             'Usuario já cadastrado em outra empresa, deseja continuar?',
                                             QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    reply2 = QMessageBox.information(self, 'Usuário Existente',
                                                 'Para evitar conflitos de senha, a senha será copiada do usuário existente para o novo usuário.',
                                                 QMessageBox.Ok)
                    if reply2 == QMessageBox.Ok:
                        self.insert_new_user(username, use_existing_password=True, company_code=company_code)
                else:
                    return
            else:
                self.insert_new_user(username, use_existing_password=False, company_code=company_code)
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao cadastrar novo usuário: {str(e)}')

    def is_username_exists_for_company(self, username, company_code):
        if not self.conn:
            return False

        try:
            cursor = self.conn.cursor()
            query = f"SELECT COUNT(*) FROM \"DBA\".\"USUARIOS\" WHERE \"USUARIO\" = '{username}' AND \"CODIGOEMPRESA\" = {company_code}"
            cursor.execute(query)
            count = cursor.fetchone()[0]
            return count > 0
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao verificar usuário existente: {str(e)}')
            return False

    def is_username_exists_for_other_company(self, username, company_code):
        if not self.conn:
            return False

        try:
            cursor = self.conn.cursor()
            query = f"SELECT COUNT(*) FROM \"DBA\".\"USUARIOS\" WHERE \"USUARIO\" = '{username}' AND \"CODIGOEMPRESA\" <> {company_code}"
            cursor.execute(query)
            count = cursor.fetchone()[0]
            return count > 0
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao verificar usuário existente: {str(e)}')
            return False

    def insert_new_user(self, username, use_existing_password, company_code):
        password = self.password_input.text().strip()

        if not self.conn:
            return

        try:
            cursor = self.conn.cursor()
            max_sequence_query = "SELECT MAX(SEQUENCIA_USU) FROM usuarios"
            cursor.execute(max_sequence_query)
            max_sequence = cursor.fetchone()[0]
            self.new_sequence = max_sequence + 1
            locations = self.get_locations()
            if use_existing_password:
                password_hash = self.get_password_hash_from_database(username)
            else:
                password_hash = self.hash_password(password)

            user_level = self.user_level_input.currentData()  # Retrieve the selected user level as data

            insert_query = f"INSERT INTO \"DBA\".\"USUARIOS\" (\"CODIGOEMPRESA\",\"USUARIO\",\"SENHA\",\"NIVEL\",\"SEQUENCIA_USU\",\"CODIGOUNICO\",\"STATUS\",\"SENHAWEB\",\"DATACAD\",\"Pw_Adic\") VALUES({company_code}, '{username}', '{password_hash}', {user_level}, {self.new_sequence}, 0, 'ATIVO', NULL, (select getdatanumerohoje()), 'NNNNNNNNNN')"
            cursor.execute(insert_query)
            self.conn.commit()

            reply = QMessageBox.question(self, 'Usuário X Local',
                                         'Deseja utilizar o relacionamento Usuário X Local (GES_094)?',
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.show_location_options()
            else:
                copy_menus_msgbox = CustomMessageBox(self)
                copy_menus_msgbox.setIcon(QMessageBox.Question)
                copy_menus_msgbox.setWindowTitle('Copiar Menus Personalizados')
                copy_menus_msgbox.setText(
                    'Deseja copiar menus personalizados de outro usuário ou liberar todos os acessos?')
                copy_menus_msgbox.addButton('Copiar menus', QMessageBox.YesRole)
                copy_menus_msgbox.addButton('Liberar todos os acessos', QMessageBox.NoRole)

                copy_menus_reply = copy_menus_msgbox.exec_()

                if copy_menus_reply == 0:  # Se o botão "Copiar menus" for pressionado
                    self.user_search_dialog = UserSearchDialog(self.conn, self.new_sequence)
                    self.user_search_dialog.exec_()

                # Pergunta ao usuário se ele utiliza o Gestor OS
                gestor_os_msgbox = CustomMessageBox(self)
                gestor_os_msgbox.setIcon(QMessageBox.Question)
                gestor_os_msgbox.setWindowTitle('Gestor OS')
                gestor_os_msgbox.setText('O usuário utiliza Gestor OS?')
                gestor_os_msgbox.addButton('Sim', QMessageBox.YesRole)
                gestor_os_msgbox.addButton('Não', QMessageBox.NoRole)

                gestor_os_reply = gestor_os_msgbox.exec_()

                if gestor_os_reply == 0:  # Se o botão "Sim" for pressionado
                    if OSProfileManager.has_registered_profiles_for_company(self.conn, company_code):
                        self.os_profile_manager = OSProfileManager(self.conn, self.new_sequence, company_code,
                                                                   locations)
                        self.os_profile_manager.exec_()
                    else:
                        QMessageBox.warning(self, 'Aviso',
                                            'A empresa destino não possui perfis cadastrados na os_perfis. Não é possível continuar com o relacionamento de perfis.')

            QMessageBox.information(self, 'Sucesso', 'Novo usuário cadastrado com sucesso!')
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao cadastrar novo usuário: {str(e)}')

    def get_password_hash_from_database(self, username):
        if not self.conn:
            return ""

        try:
            cursor = self.conn.cursor()
            query = f"SELECT \"SENHA\" FROM \"DBA\".\"USUARIOS\" WHERE \"USUARIO\" = '{username}'"
            cursor.execute(query)
            password_hash = cursor.fetchone()[0]
            return password_hash
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao obter a senha existente: {str(e)}')
            return ""

    def hash_password(self, password):
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()

    def show_location_options(self):
        selected_company_code = int(self.company_code_input.currentData())  # Retrieve selected company code as data
        self.location_options_dialog = LocationOptionsDialog(self.conn, selected_company_code)
        result = self.location_options_dialog.exec_()

        if result == QDialog.Accepted:
            selected_locations = self.location_options_dialog.get_selected_locations()
            if selected_locations:
                self.insert_user_in_specific_locations(selected_locations)
            else:
                QMessageBox.warning(self, 'Aviso', 'Selecione ao menos um local para cadastrar o usuário.')
                self.show_location_options()  # Show the dialog again if no locations are selected

        layout = QVBoxLayout(self)  # Move this line to correct the indentation

        self.location_checkboxes = {}
        locations = self.get_locations()
        for location in locations:
            checkbox = QCheckBox(f"{location['cod_local']} - {location['nome_local']}", self)
            self.location_checkboxes[location['cod_local']] = checkbox

    def insert_user_in_specific_locations(self, selected_locations):
        username = self.user_input.text().upper()
        company_code = self.company_code_input.currentData()  # Use currentData() to get the selected company code

        try:
            cursor = self.conn.cursor()
            for location in selected_locations:
                insert_query = f"INSERT INTO \"DBA\".\"GES_094\" (\"EMPRESA\",\"ULV001\",\"ULV002\",\"ULV003\",\"SEQUENCIA_USU\",\"ULV004\") VALUES({company_code},'{username}',{location['cod_local']},0,{self.new_sequence},NULL)"
                cursor.execute(insert_query)
            self.conn.commit()

            QMessageBox.information(self, 'Sucesso', 'Usuário cadastrado em locais específicos com sucesso!')

            copy_menus_msgbox = CustomMessageBox(self)
            copy_menus_msgbox.setIcon(QMessageBox.Question)
            copy_menus_msgbox.setWindowTitle('Copiar Menus Personalizados')
            copy_menus_msgbox.setText(
                'Deseja copiar menus personalizados de outro usuário ou liberar todos os acessos?')
            copy_menus_msgbox.addButton('Copiar menus', QMessageBox.YesRole)
            copy_menus_msgbox.addButton('Liberar todos os acessos', QMessageBox.NoRole)

            copy_menus_reply = copy_menus_msgbox.exec_()

            if copy_menus_reply == 0:  # Se o botão "Copiar menus" for pressionado
                self.user_search_dialog = UserSearchDialog(self.conn, self.new_sequence)
                self.user_search_dialog.exec_()

            # Pergunta ao usuário se ele utiliza o Gestor OS
            gestor_os_msgbox = CustomMessageBox(self)
            gestor_os_msgbox.setIcon(QMessageBox.Question)
            gestor_os_msgbox.setWindowTitle('Gestor OS')
            gestor_os_msgbox.setText('O usuário utiliza Gestor OS?')
            gestor_os_msgbox.addButton('Sim', QMessageBox.YesRole)
            gestor_os_msgbox.addButton('Não', QMessageBox.NoRole)

            gestor_os_reply = gestor_os_msgbox.exec_()

            if gestor_os_reply == 0:  # Se o botão "Sim" for pressionado
                if OSProfileManager.has_registered_profiles_for_company(self.conn, company_code):
                    self.os_profile_manager = OSProfileManager(self.conn, self.new_sequence, company_code,
                                                               selected_locations)
                    self.os_profile_manager.exec_()
                else:
                    QMessageBox.warning(self, 'Aviso',
                                        'A empresa destino não possui perfis cadastrados na os_perfis. Não é possível continuar com o relacionamento de perfis.')

        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao cadastrar usuário em locais específicos: {str(e)}')

    def update_company_codes(self):
        self.company_code_input.clear()
        if not self.conn:
            return

        try:
            cursor = self.conn.cursor()
            query = "SELECT codigoempresa, nomeempresa FROM empresas"
            cursor.execute(query)
            company_data = [(str(row.codigoempresa), row.nomeempresa) for row in cursor.fetchall()]

            self.company_code_input.clear()
            for company_code, company_name in company_data:
                self.company_code_input.addItem(f"{company_code} - {company_name}", int(company_code))

        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao obter códigos de empresa: {str(e)}')

    def get_locations(self):
        locations = []
        if not self.conn:
            return locations

        try:
            selected_company_code = int(self.company_code_input.currentData())  # Retrieve selected company code as data
            cursor = self.conn.cursor()
            query = f"SELECT lcl001 as cod_local, lcl002 as nome_local FROM ges_008 WHERE empresa={selected_company_code}"
            cursor.execute(query)
            for row in cursor.fetchall():
                location = {"cod_local": row.cod_local, "nome_local": row.nome_local}
                locations.append(location)

        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao obter locais: {str(e)}')

        return locations

    def centerOnScreen(self):
        resolution = QDesktopWidget().screenGeometry()
        self.move(int((resolution.width() / 2) - (self.frameSize().width() / 2)),
                  int((resolution.height() / 2) - (self.frameSize().height() / 2)))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.centerOnScreen()  # Adicione esta linha
    window.show()
    sys.exit(app.exec_())