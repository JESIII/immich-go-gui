from PySide6.QtWidgets import QFileDialog


class BrowseDialogsMixin:
    def _set_input_path(self, tab_key: str, field_key: str, value: str) -> None:
        widget = self.inputs[tab_key][field_key]
        if hasattr(widget, "setPlainText"):
            widget.setPlainText(value)
        else:
            widget.setText(value)

    def _pick_existing_directory(self, title: str) -> str | None:
        folder = QFileDialog.getExistingDirectory(
            self, title, "", QFileDialog.Option.ShowDirsOnly
        )
        return folder if folder else None

    def _pick_open_file(
        self, title: str, filter_str: str = "ZIP archives (*.zip *.ZIP);;All Files (*)"
    ) -> str | None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, title, "", filter_str, options=QFileDialog.Option(0)
        )
        return file_path if file_path else None

    def _pick_open_files(
        self, title: str, filter_str: str = "ZIP archives (*.zip *.ZIP);;All Files (*)"
    ) -> list[str] | None:
        files, _ = QFileDialog.getOpenFileNames(
            self, title, "", filter_str, options=QFileDialog.Option(0)
        )
        return files if files else None

    def browse_folder_upload(self):
        folder = self._pick_existing_directory("Select Folder")
        if folder:
            self._set_input_path("upload-folder", "path", folder)

    def browse_zip_upload(self):
        file_path = self._pick_open_file("Select ZIP Archive")
        if file_path:
            self._set_input_path("upload-folder", "path", file_path)

    def browse_takeout_zips(self):
        files = self._pick_open_files("Select Takeout ZIP parts")
        if files:
            self._set_input_path("upload-gp", "path", "\n".join(files))

    def browse_takeout_folder(self):
        folder = self._pick_existing_directory("Select Extracted Folder")
        if folder:
            self._set_input_path("upload-gp", "path", folder)

    def browse_folder_archive(self):
        folder = self._pick_existing_directory("Select Folder")
        if folder:
            self._set_input_path("archive-folder", "path", folder)

    def browse_zip_archive(self):
        file_path = self._pick_open_file("Select ZIP Archive")
        if file_path:
            self._set_input_path("archive-folder", "path", file_path)

    def browse_folder_upload_icloud(self):
        folder = self._pick_existing_directory("Select iCloud Export Folder")
        if folder:
            self._set_input_path("upload-icloud", "path", folder)

    def browse_zip_upload_icloud(self):
        file_path = self._pick_open_file("Select iCloud ZIP Archive")
        if file_path:
            self._set_input_path("upload-icloud", "path", file_path)

    def browse_folder_upload_picasa(self):
        folder = self._pick_existing_directory("Select Picasa Folder")
        if folder:
            self._set_input_path("upload-picasa", "path", folder)

    def browse_zip_upload_picasa(self):
        file_path = self._pick_open_file("Select Picasa ZIP Archive")
        if file_path:
            self._set_input_path("upload-picasa", "path", file_path)

    def browse_archive_gp_zips(self):
        files = self._pick_open_files("Select Takeout ZIP parts")
        if files:
            self._set_input_path("archive-gp", "path", "\n".join(files))

    def browse_archive_gp_folder(self):
        folder = self._pick_existing_directory("Select Extracted Folder")
        if folder:
            self._set_input_path("archive-gp", "path", folder)

    def browse_folder_archive_icloud(self):
        folder = self._pick_existing_directory("Select iCloud Export Folder")
        if folder:
            self._set_input_path("archive-icloud", "path", folder)

    def browse_zip_archive_icloud(self):
        file_path = self._pick_open_file("Select iCloud ZIP Archive")
        if file_path:
            self._set_input_path("archive-icloud", "path", file_path)

    def browse_folder_archive_picasa(self):
        folder = self._pick_existing_directory("Select Picasa Folder")
        if folder:
            self._set_input_path("archive-picasa", "path", folder)

    def browse_zip_archive_picasa(self):
        file_path = self._pick_open_file("Select Picasa ZIP Archive")
        if file_path:
            self._set_input_path("archive-picasa", "path", file_path)

    def browse_takeout_source(self):
        self.browse_takeout_zips()

    def browse_local_folder(self):
        self.browse_folder_upload()
