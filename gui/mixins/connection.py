from PySide6.QtWidgets import QCheckBox, QMessageBox

from core.network import test_immich_connection


class ConnectionMixin:
    def on_test_connection_clicked(self):
        srv_widget = self.inputs.get("config", {}).get("server")
        api_widget = self.inputs.get("config", {}).get("api_key")
        ssl_widget = self.inputs.get("config", {}).get("skip-ssl")

        server_url = srv_widget.text().strip() if srv_widget else ""
        api_key = api_widget.text().strip() if api_widget else ""
        skip_ssl = ssl_widget.isChecked() if ssl_widget else False

        if not server_url:
            QMessageBox.warning(
                self, "Test Connection", "Please enter a Server URL first."
            )
            return
        if not api_key:
            QMessageBox.warning(
                self, "Test Connection", "Please enter an API Key first."
            )
            return

        res = test_immich_connection(server_url, api_key, skip_ssl=skip_ssl)
        if res.ok:
            self._last_conn_test_ok = True
            QMessageBox.information(self, "Test Connection Succeeded", res.message)
        else:
            self._last_conn_test_ok = False
            QMessageBox.warning(self, "Test Connection Failed", res.message)
        self.update_status()

    def _auto_test_connection(self):
        """Silent background test — updates status card only, no popup."""
        srv = self.server_url_edit.text().strip()
        key = self.api_key_edit.text().strip()
        if not srv or not key:
            self._last_conn_test_ok = None
            self.update_status()
            return
        skip_ssl = self.inputs["config"].get("skip-ssl", QCheckBox()).isChecked()
        res = test_immich_connection(srv, key, skip_ssl=skip_ssl, timeout=4.0)
        self._last_conn_test_ok = res.ok
        self.update_status()
