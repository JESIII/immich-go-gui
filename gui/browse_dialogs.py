from PySide6.QtWidgets import QFileDialog


class BrowseDialogsMixin:
    def browse_folder_upload(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder", "", QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            self.inputs["upload-folder"]["path"].setText(folder)

    def browse_zip_upload(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select ZIP Archive",
            "",
            "ZIP archives (*.zip *.ZIP);;All Files (*)",
            options=QFileDialog.Option(0),
        )
        if file_path:
            self.inputs["upload-folder"]["path"].setText(file_path)

    def browse_takeout_zips(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Takeout ZIP parts",
            "",
            "ZIP archives (*.zip *.ZIP);;All Files (*)",
            options=QFileDialog.Option(0),
        )
        if files:
            self.inputs["upload-gp"]["path"].setPlainText("\n".join(files))

    def browse_takeout_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Extracted Folder", "", QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            self.inputs["upload-gp"]["path"].setPlainText(folder)

    def browse_folder_archive(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder", "", QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            self.inputs["archive-folder"]["path"].setText(folder)

    def browse_zip_archive(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select ZIP Archive",
            "",
            "ZIP archives (*.zip *.ZIP);;All Files (*)",
            options=QFileDialog.Option(0),
        )
        if file_path:
            self.inputs["archive-folder"]["path"].setText(file_path)

    def browse_folder_upload_icloud(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select iCloud Export Folder", "", QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            self.inputs["upload-icloud"]["path"].setText(folder)

    def browse_zip_upload_icloud(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select iCloud ZIP Archive",
            "",
            "ZIP archives (*.zip *.ZIP);;All Files (*)",
            options=QFileDialog.Option(0),
        )
        if file_path:
            self.inputs["upload-icloud"]["path"].setText(file_path)

    def browse_folder_upload_picasa(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Picasa Folder", "", QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            self.inputs["upload-picasa"]["path"].setText(folder)

    def browse_zip_upload_picasa(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Picasa ZIP Archive",
            "",
            "ZIP archives (*.zip *.ZIP);;All Files (*)",
            options=QFileDialog.Option(0),
        )
        if file_path:
            self.inputs["upload-picasa"]["path"].setText(file_path)

    def browse_archive_gp_zips(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Takeout ZIP parts",
            "",
            "ZIP archives (*.zip *.ZIP);;All Files (*)",
            options=QFileDialog.Option(0),
        )
        if files:
            self.inputs["archive-gp"]["path"].setPlainText("\n".join(files))

    def browse_archive_gp_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Extracted Folder", "", QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            self.inputs["archive-gp"]["path"].setPlainText(folder)

    def browse_folder_archive_icloud(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select iCloud Export Folder", "", QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            self.inputs["archive-icloud"]["path"].setText(folder)

    def browse_zip_archive_icloud(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select iCloud ZIP Archive",
            "",
            "ZIP archives (*.zip *.ZIP);;All Files (*)",
            options=QFileDialog.Option(0),
        )
        if file_path:
            self.inputs["archive-icloud"]["path"].setText(file_path)

    def browse_folder_archive_picasa(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Picasa Folder", "", QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            self.inputs["archive-picasa"]["path"].setText(folder)

    def browse_zip_archive_picasa(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Picasa ZIP Archive",
            "",
            "ZIP archives (*.zip *.ZIP);;All Files (*)",
            options=QFileDialog.Option(0),
        )
        if file_path:
            self.inputs["archive-picasa"]["path"].setText(file_path)

    def browse_takeout_source(self):
        self.browse_takeout_zips()

    def browse_local_folder(self):
        self.browse_folder_upload()
