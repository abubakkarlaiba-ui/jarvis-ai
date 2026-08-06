"""
Coding Agent — Desktop App Builder
===================================
Scaffolds desktop application projects for Electron, Tauri, PyQt6, Tkinter, PySide6, Flutter, and Compose Multiplatform.
"""

from __future__ import annotations

import json
import os
from typing import Any

from jarvis.core.coding.base import TaskType


class DesktopAppBuilder:
    """Scaffold complete desktop application projects from templates."""

    SUPPORTED_FRAMEWORKS = [
        "electron", "tauri", "pyqt6", "tkinter", "pyside6",
        "flutter", "compose-multiplatform",
    ]

    # ------------------------------------------------------------------
    # Main builder
    # ------------------------------------------------------------------

    def build_app(
        self,
        name: str,
        framework: str,
        features: list[str],
        output_dir: str,
    ) -> dict[str, str]:
        """Build a desktop application project.

        Args:
            name: Application name.
            framework: One of Electron, Tauri, PyQt6, Tkinter, PySide6,
                       Flutter, Compose Multiplatform.
            features: List of features (e.g. tray_icon, menu, settings, dialog).
            output_dir: Root directory for output.

        Returns:
            Mapping of relative file paths to generated content.
        """
        fw = framework.lower().replace(" ", "").replace("-", "")
        generators = {
            "electron": self._gen_electron,
            "tauri": self._gen_tauri,
            "pyqt6": self._gen_pyqt6,
            "tkinter": self._gen_tkinter,
            "pyside6": self._gen_pyside6,
            "flutter": self._gen_flutter,
            "composeMultiplatform": self._gen_compose_multiplatform,
        }
        gen = generators.get(fw)
        if gen is None:
            raise ValueError(
                f"Unsupported framework '{framework}'. "
                f"Choose from: {', '.join(sorted(generators))}"
            )

        files = gen(name, features, output_dir)
        files[os.path.join(output_dir, "README.md")] = self._gen_readme(name, framework)
        return files

    # ------------------------------------------------------------------
    # Window / screen generation
    # ------------------------------------------------------------------

    def generate_main_window(
        self,
        name: str,
        framework: str,
        layout: dict[str, Any],
    ) -> str:
        """Generate the main window or screen for the application.

        Args:
            name: Application / window title.
            framework: Target framework.
            layout: Layout specification with keys like ``widgets``,
                     ``menu``, ``status_bar``, ``size``.

        Returns:
            Generated source code as a string.
        """
        fw = framework.lower()
        if fw in ("pyqt6", "pyside6"):
            return self._gen_main_window_qt(name, framework, layout)
        if fw == "tkinter":
            return self._gen_main_window_tkinter(name, layout)
        if fw == "electron":
            return self._gen_main_window_electron(name, layout)
        if fw == "tauri":
            return self._gen_main_window_tauri(name, layout)
        if fw == "flutter":
            return self._gen_main_window_flutter(name, layout)
        if fw in ("compose-multiplatform", "composemultiplatform"):
            return self._gen_main_window_compose(name, layout)
        raise ValueError(f"Unsupported framework '{framework}'")

    # ------------------------------------------------------------------
    # Menu generation
    # ------------------------------------------------------------------

    def generate_menu(
        self,
        name: str,
        items: list[dict[str, Any]],
        framework: str,
    ) -> str:
        """Generate an application menu.

        Args:
            name: Application name.
            items: Menu items ``[{label, accelerator, action, submenu}]``.
            framework: Target framework.

        Returns:
            Generated menu code as a string.
        """
        fw = framework.lower()
        if fw in ("pyqt6", "pyside6"):
            return self._gen_menu_qt(name, items, framework)
        if fw == "tkinter":
            return self._gen_menu_tkinter(name, items)
        if fw == "electron":
            return self._gen_menu_electron(name, items)
        if fw == "tauri":
            return self._gen_menu_tauri(name, items)
        if fw == "flutter":
            return self._gen_menu_flutter(name, items)
        if fw in ("compose-multiplatform", "composemultiplatform"):
            return self._gen_menu_compose(name, items)
        raise ValueError(f"Unsupported framework '{framework}'")

    # ------------------------------------------------------------------
    # Dialog generation
    # ------------------------------------------------------------------

    def generate_dialog(
        self,
        name: str,
        fields: list[dict[str, Any]],
        framework: str,
    ) -> str:
        """Generate a dialog or modal window.

        Args:
            name: Dialog title.
            fields: Form fields ``[{name, type, label, placeholder, required}]``.
            framework: Target framework.

        Returns:
            Generated dialog code as a string.
        """
        fw = framework.lower()
        if fw in ("pyqt6", "pyside6"):
            return self._gen_dialog_qt(name, fields, framework)
        if fw == "tkinter":
            return self._gen_dialog_tkinter(name, fields)
        if fw == "electron":
            return self._gen_dialog_electron(name, fields)
        if fw == "tauri":
            return self._gen_dialog_tauri(name, fields)
        if fw == "flutter":
            return self._gen_dialog_flutter(name, fields)
        if fw in ("compose-multiplatform", "composemultiplatform"):
            return self._gen_dialog_compose(name, fields)
        raise ValueError(f"Unsupported framework '{framework}'")

    # ------------------------------------------------------------------
    # Tray icon
    # ------------------------------------------------------------------

    def generate_tray_icon(self, name: str, framework: str) -> str:
        """Generate system tray icon functionality.

        Args:
            name: Application name.
            framework: Target framework.

        Returns:
            Generated tray icon code as a string.
        """
        fw = framework.lower()
        if fw in ("pyqt6", "pyside6"):
            return self._gen_tray_qt(name, framework)
        if fw == "tkinter":
            return self._gen_tray_tkinter(name)
        if fw == "electron":
            return self._gen_tray_electron(name)
        if fw == "tauri":
            return self._gen_tray_tauri(name)
        if fw == "flutter":
            return self._gen_tray_flutter(name)
        if fw in ("compose-multiplatform", "composemultiplatform"):
            return self._gen_tray_compose(name)
        raise ValueError(f"Unsupported framework '{framework}'")

    # ------------------------------------------------------------------
    # Settings page
    # ------------------------------------------------------------------

    def generate_settings_page(
        self,
        name: str,
        framework: str,
        settings: list[dict[str, Any]],
    ) -> str:
        """Generate a settings / preferences UI.

        Args:
            name: Application name.
            framework: Target framework.
            settings: Settings entries ``[{key, label, type, default}]``.
                      Types: toggle, text, number, dropdown, color, file.

        Returns:
            Generated settings page code as a string.
        """
        fw = framework.lower()
        if fw in ("pyqt6", "pyside6"):
            return self._gen_settings_qt(name, framework, settings)
        if fw == "tkinter":
            return self._gen_settings_tkinter(name, settings)
        if fw == "electron":
            return self._gen_settings_electron(name, settings)
        if fw == "tauri":
            return self._gen_settings_tauri(name, settings)
        if fw == "flutter":
            return self._gen_settings_flutter(name, settings)
        if fw in ("compose-multiplatform", "composemultiplatform"):
            return self._gen_settings_compose(name, settings)
        raise ValueError(f"Unsupported framework '{framework}'")

    # ------------------------------------------------------------------
    # Installer scaffolding
    # ------------------------------------------------------------------

    def scaffold_installer(
        self,
        name: str,
        platform: str,
        framework: str,
    ) -> dict[str, str]:
        """Generate installer configurations.

        Args:
            name: Application name.
            platform: Target platform — windows, macos, linux, or all.
            framework: Source framework used to build the app.

        Returns:
            Mapping of file paths to installer configuration content.
        """
        files: dict[str, str] = {}
        plat = platform.lower()
        fw = framework.lower().replace(" ", "").replace("-", "")

        if plat in ("windows", "all"):
            files[f"{name}_installer.nsi"] = self._gen_nsis_installer(name, fw)
        if plat in ("macos", "all"):
            files[f"{name}.dmg.json"] = self._gen_dmg_config(name, fw)
            files["entitlements.plist"] = self._gen_entitlements(name)
        if plat in ("linux", "all"):
            files[f"{name}.appimage.desktop"] = self._gen_appimage_desktop(name)
            files[f"{name}.appimage.yml"] = self._gen_appimage_config(name, fw)
        return files

    # ==================================================================
    # Private — Electron
    # ==================================================================

    def _gen_electron(self, name: str, features: list[str], output_dir: str) -> dict[str, str]:
        files: dict[str, str] = {}
        pkg = {
            "name": name.lower().replace(" ", "-"),
            "version": "1.0.0",
            "description": f"{name} desktop application",
            "main": "src/main.js",
            "scripts": {
                "start": "electron .",
                "build": "electron-builder",
                "build:win": "electron-builder --win",
                "build:mac": "electron-builder --mac",
                "build:linux": "electron-builder --linux",
            },
            "devDependencies": {
                "electron": "^28.0.0",
                "electron-builder": "^24.0.0",
            },
        }
        files[os.path.join(output_dir, "package.json")] = json.dumps(pkg, indent=2)

        files[os.path.join(output_dir, "src/main.js")] = (
            "const { app, BrowserWindow, Menu } = require('electron');\n"
            "const path = require('path');\n\n"
            "function createWindow() {\n"
            "  const win = new BrowserWindow({\n"
            f"    width: 1200,\n    height: 800,\n"
            "    title: '" + name + "',\n"
            "    webPreferences: {\n"
            "      nodeIntegration: true,\n"
            "      contextIsolation: false,\n"
            "    },\n"
            "  });\n\n"
            "  win.loadFile('src/index.html');\n"
            "}\n\n"
            "app.whenReady().then(() => {\n"
            "  createWindow();\n"
            "  app.on('activate', () => {\n"
            "    if (BrowserWindow.getAllWindows().length === 0) createWindow();\n"
            "  });\n"
            "});\n\n"
            "app.on('window-all-closed', () => {\n"
            "  if (process.platform !== 'darwin') app.quit();\n"
            "});\n"
        )

        files[os.path.join(output_dir, "src/index.html")] = (
            "<!DOCTYPE html>\n<html>\n<head>\n"
            "  <meta charset=\"UTF-8\">\n"
            f"  <title>{name}</title>\n"
            "  <style>\n"
            "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;\n"
            "           margin: 0; padding: 20px; background: #f5f5f5; }\n"
            "    h1 { color: #333; }\n"
            "  </style>\n"
            "</head>\n<body>\n"
            f"  <h1>{name}</h1>\n"
            "  <p>Welcome to your desktop application.</p>\n"
            "</body>\n</html>\n"
        )

        files[os.path.join(output_dir, "src/preload.js")] = (
            "// Electron preload script\n"
            "const { contextBridge } = require('electron');\n\n"
            "contextBridge.exposeInMainWorld('api', {\n"
            "  platform: process.platform,\n"
            "});\n"
        )

        if "tray_icon" in features:
            files[os.path.join(output_dir, "src/tray.js")] = self.generate_tray_icon(name, "electron")

        if "menu" in features:
            files[os.path.join(output_dir, "src/menu.js")] = self.generate_menu(name, [
                {"label": "File", "submenu": [
                    {"label": "New", "accelerator": "CmdOrCtrl+N", "action": "new"},
                    {"label": "Open", "accelerator": "CmdOrCtrl+O", "action": "open"},
                    {"label": "Save", "accelerator": "CmdOrCtrl+S", "action": "save"},
                    {"label": "Exit", "accelerator": "CmdOrCtrl+Q", "action": "quit"},
                ]},
                {"label": "Edit", "submenu": [
                    {"label": "Undo", "accelerator": "CmdOrCtrl+Z", "action": "undo"},
                    {"label": "Redo", "accelerator": "CmdOrCtrl+Shift+Z", "action": "redo"},
                ]},
                {"label": "Help", "submenu": [
                    {"label": "About", "action": "about"},
                ]},
            ], "electron")

        if "dialog" in features:
            files[os.path.join(output_dir, "src/dialog.js")] = self.generate_dialog(name, [
                {"name": "name", "type": "text", "label": "Name", "placeholder": "Enter name", "required": True},
                {"name": "email", "type": "text", "label": "Email", "placeholder": "you@example.com", "required": False},
            ], "electron")

        if "settings" in features:
            files[os.path.join(output_dir, "src/settings.js")] = self.generate_settings_page(name, "electron", [
                {"key": "theme", "label": "Theme", "type": "dropdown", "default": "light", "options": ["light", "dark"]},
                {"key": "auto_save", "label": "Auto-save", "type": "toggle", "default": True},
                {"key": "font_size", "label": "Font Size", "type": "number", "default": 14},
            ])

        files[os.path.join(output_dir, "electron-builder.yml")] = (
            f"appId: com.{name.lower().replace(' ', '.')}\n"
            f"productName: {name}\n"
            "directories:\n  output: dist\n"
            "files:\n  - src/**/*\n"
            "win:\n  target: nsis\n  icon: assets/icon.ico\n"
            "mac:\n  target: dmg\n  icon: assets/icon.icns\n"
            "linux:\n  target: AppImage\n  icon: assets/icon.png\n"
        )

        return files

    def _gen_tauri(self, name: str, features: list[str], output_dir: str) -> dict[str, str]:
        files: dict[str, str] = {}
        pkg = {
            "name": name.lower().replace(" ", "-"),
            "version": "1.0.0",
            "description": f"{name} desktop application",
            "scripts": {"tauri": "tauri"},
            "devDependencies": {"@tauri-apps/cli": "^1.5.0"},
            "dependencies": {"@tauri-apps/api": "^1.5.0"},
        }
        files[os.path.join(output_dir, "package.json")] = json.dumps(pkg, indent=2)

        files[os.path.join(output_dir, "src-tauri/Cargo.toml")] = (
            "[package]\n"
            f'name = "{name.lower().replace(" ", "-")}"\n'
            'version = "1.0.0"\n'
            'edition = "2021"\n\n'
            "[dependencies]\n"
            'tauri = { version = "1.5", features = ["shell-open"] }\n'
            'serde = { version = "1.0", features = ["derive"] }\n'
            'serde_json = "1.0"\n'
        )

        files[os.path.join(output_dir, "src-tauri/tauri.conf.json")] = json.dumps({
            "build": {"beforeDevCommand": "npm run dev", "devPath": "http://localhost:5173",
                       "beforeBuildCommand": "npm run build", "distDir": "../dist"},
            "package": {"productName": name, "version": "1.0.0"},
            "tauri": {
                "bundle": {"active": True, "identifier": f"com.{name.lower().replace(' ', '.')}"},
                "windows": [{"title": name, "width": 1200, "height": 800, "resizable": True}],
                "security": {"csp": None},
            },
        }, indent=2)

        files[os.path.join(output_dir, "src-tauri/src/main.rs")] = (
            "#![cfg_attr(not(debug_assertions), windows_subsystem = \"windows\")]\n\n"
            "use tauri::Manager;\n\n"
            "#[tauri::command]\n"
            f"fn greet(name: &str) -> String {{\n"
            f"    format!(\"Hello {{}}!\", name)\n"
            "}}\n\n"
            "fn main() {\n"
            "    tauri::Builder::default()\n"
            f"        .invoke_handler(tauri::generate_handler![greet])\n"
            "        .run(tauri::generate_context!())\n"
            "        .expect(\"error while running tauri application\");\n"
            "}\n"
        )

        files[os.path.join(output_dir, "src/index.html")] = (
            "<!DOCTYPE html>\n<html>\n<head>\n"
            "  <meta charset=\"UTF-8\">\n"
            f"  <title>{name}</title>\n"
            "</head>\n<body>\n"
            f"  <h1>{name}</h1>\n"
            "  <script type=\"module\" src=\"/main.js\"></script>\n"
            "</body>\n</html>\n"
        )

        return files

    # ==================================================================
    # Private — PyQt6 / PySide6 (shared logic)
    # ==================================================================

    def _gen_pyqt6(self, name: str, features: list[str], output_dir: str) -> dict[str, str]:
        return self._gen_qt_project(name, features, output_dir, "PyQt6")

    def _gen_pyside6(self, name: str, features: list[str], output_dir: str) -> dict[str, str]:
        return self._gen_qt_project(name, features, output_dir, "PySide6")

    def _gen_qt_project(self, name: str, features: list[str], output_dir: str, framework: str) -> dict[str, str]:
        files: dict[str, str] = {}
        import_name = "PyQt6" if framework == "PyQt6" else "PySide6"

        files[os.path.join(output_dir, "requirements.txt")] = (
            f"{import_name.lower()}>=6.5.0\n"
        )

        files[os.path.join(output_dir, "main.py")] = (
            f"from {import_name.lower()}.QtWidgets import QApplication, QMainWindow\n"
            f"from {import_name.lower()}.QtCore import Qt\n"
            "import sys\n\n\n"
            f"class MainWindow(QMainWindow):\n"
            "    def __init__(self):\n"
            "        super().__init__()\n"
            f"        self.setWindowTitle('{name}')\n"
            "        self.setMinimumSize(1200, 800)\n"
            "        self._setup_ui()\n\n"
            "    def _setup_ui(self):\n"
            "        pass\n\n\n"
            "def main():\n"
            "    app = QApplication(sys.argv)\n"
            "    window = MainWindow()\n"
            "    window.show()\n"
            "    sys.exit(app.exec())\n\n\n"
            'if __name__ == "__main__":\n'
            "    main()\n"
        )

        files[os.path.join(output_dir, "app/__init__.py")] = ""
        files[os.path.join(output_dir, "app/main_window.py")] = self.generate_main_window(name, framework, {
            "size": [1200, 800],
            "widgets": [],
        })

        if "menu" in features:
            files[os.path.join(output_dir, "app/menu.py")] = self.generate_menu(name, [
                {"label": "File", "items": ["New", "Open", "Save", "Exit"]},
                {"label": "Edit", "items": ["Undo", "Redo"]},
                {"label": "Help", "items": ["About"]},
            ], framework)

        if "dialog" in features:
            files[os.path.join(output_dir, "app/dialog.py")] = self.generate_dialog(name, [
                {"name": "name", "type": "text", "label": "Name", "required": True},
                {"name": "email", "type": "text", "label": "Email", "required": False},
            ], framework)

        if "tray_icon" in features:
            files[os.path.join(output_dir, "app/tray.py")] = self.generate_tray_icon(name, framework)

        if "settings" in features:
            files[os.path.join(output_dir, "app/settings.py")] = self.generate_settings_page(name, framework, [
                {"key": "theme", "label": "Theme", "type": "dropdown", "default": "light", "options": ["light", "dark"]},
                {"key": "auto_save", "label": "Auto-save", "type": "toggle", "default": True},
            ])

        return files

    def _gen_tkinter(self, name: str, features: list[str], output_dir: str) -> dict[str, str]:
        files: dict[str, str] = {}
        files[os.path.join(output_dir, "main.py")] = (
            "import tkinter as tk\n"
            "from tkinter import ttk, messagebox\n\n\n"
            f"class App(tk.Tk):\n"
            "    def __init__(self):\n"
            "        super().__init__()\n"
            f"        self.title('{name}')\n"
            "        self.geometry('1200x800')\n"
            "        self._setup_ui()\n\n"
            "    def _setup_ui(self):\n"
            "        self.main_frame = ttk.Frame(self)\n"
            "        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)\n\n"
            "        label = ttk.Label(self.main_frame, text=f'Welcome to {name}',\n"
            "                          font=('Segoe UI', 24))\n"
            "        label.pack(pady=50)\n\n\n"
            "def main():\n"
            f"    app = App()\n"
            "    app.mainloop()\n\n\n"
            'if __name__ == "__main__":\n'
            "    main()\n"
        )

        files[os.path.join(output_dir, "requirements.txt")] = ""

        if "menu" in features:
            files[os.path.join(output_dir, "app_menu.py")] = self.generate_menu(name, [
                {"label": "File", "items": ["New", "Open", "Save", "Exit"]},
                {"label": "Edit", "items": ["Undo", "Redo"]},
                {"label": "Help", "items": ["About"]},
            ], "tkinter")

        if "dialog" in features:
            files[os.path.join(output_dir, "app_dialog.py")] = self.generate_dialog(name, [
                {"name": "name", "type": "text", "label": "Name", "required": True},
            ], "tkinter")

        if "settings" in features:
            files[os.path.join(output_dir, "app_settings.py")] = self.generate_settings_page(name, "tkinter", [
                {"key": "theme", "label": "Theme", "type": "dropdown", "default": "light", "options": ["light", "dark"]},
            ])

        return files

    def _gen_flutter(self, name: str, features: list[str], output_dir: str) -> dict[str, str]:
        files: dict[str, str] = {}
        snake = name.lower().replace(" ", "_")

        files[os.path.join(output_dir, "pubspec.yaml")] = (
            f"name: {snake}\n"
            "description: A Flutter desktop application.\n"
            "version: 1.0.0+1\n\n"
            "environment:\n  sdk: '>=3.0.0 <4.0.0'\n\n"
            "dependencies:\n  flutter:\n    sdk: flutter\n"
            "  cupertino_icons: ^1.0.6\n\n"
            "flutter:\n  uses-material-design: true\n"
        )

        files[os.path.join(output_dir, "lib/main.dart")] = (
            "import 'package:flutter/material.dart';\n\n"
            f"void main() => runApp(const {snake.replace('_', '').title()}App());\n\n"
            f"class {snake.replace('_', '').title()}App extends StatelessWidget {{\n"
            f"  const {snake.replace('_', '').title()}App({{super.key}});\n\n"
            "  @override\n"
            "  Widget build(BuildContext context) {\n"
            "    return MaterialApp(\n"
            f"      title: '{name}',\n"
            "      theme: ThemeData(\n"
            "        colorSchemeSeed: Colors.blue,\n"
            "        useMaterial3: True,\n"
            "      ),\n"
            f"      home: const {snake.replace('_', '').title()}Home(),\n"
            "    );\n"
            "  }\n"
            "}\n\n"
            f"class {snake.replace('_', '').title()}Home extends StatelessWidget {{\n"
            f"  const {snake.replace('_', '').title()}Home({{super.key}});\n\n"
            "  @override\n"
            "  Widget build(BuildContext context) {\n"
            "    return Scaffold(\n"
            "      appBar: AppBar(title: const Text('" + name + "')),\n"
            "      body: const Center(\n"
            f"        child: Text('Welcome to {name}', style: TextStyle(fontSize: 24)),\n"
            "      ),\n"
            "    );\n"
            "  }\n"
            "}\n"
        )

        return files

    def _gen_compose_multiplatform(self, name: str, features: list[str], output_dir: str) -> dict[str, str]:
        files: dict[str, str] = {}
        pkg = name.lower().replace(" ", ".")

        files[os.path.join(output_dir, "build.gradle.kts")] = (
            "plugins {\n"
            "    kotlin(\"multiplatform\") version \"1.9.0\"\n"
            "    id(\"org.jetbrains.compose\") version \"1.5.0\"\n"
            "    id(\"org.jetbrains.kotlin.plugin.compose\") version \"1.9.0\"\n"
            "}\n\n"
            f'group = "{pkg}"\n'
            'version = "1.0.0"\n\n'
            "kotlin {\n"
            "    jvm(\"desktop\")\n\n"
            "    sourceSets {\n"
            "        val desktopMain by getting {\n"
            "            dependencies {\n"
            "                implementation(compose.desktop.currentOs)\n"
            "                implementation(compose.material3)\n"
            "                implementation(\"org.jetbrains.kotlinx:kotlinx-coroutines-swing:1.7.3\")\n"
            "            }\n"
            "        }\n"
            "    }\n"
            "}\n\n"
            "compose.desktop {\n"
            "    application {\n"
            f"        mainClass = \"{pkg.replace('.', '/')}.MainKt\"\n"
            "        nativeDistributions {\n"
            f"            targetFormats(org.jetbrains.compose.desktop.application.dsl.TargetFormat.Dmg,\n"
            "                         org.jetbrains.compose.desktop.application.dsl.TargetFormat.Msi,\n"
            "                         org.jetbrains.compose.desktop.application.dsl.TargetFormat.Deb)\n"
            f"            packageName = \"{name}\"\n"
            '            packageVersion = "1.0.0"\n'
            "        }\n"
            "    }\n"
            "}\n"
        )

        src_path = pkg.replace(".", "/")
        files[os.path.join(output_dir, f"src/jvmMain/kotlin/{src_path}/Main.kt")] = (
            "import androidx.compose.desktop.ui.tooling.preview.Preview\n"
            "import androidx.compose.foundation.layout.*\n"
            "import androidx.compose.material3.*\n"
            "import androidx.compose.runtime.*\n"
            "import androidx.compose.ui.Alignment\n"
            "import androidx.compose.ui.Modifier\n"
            "import androidx.compose.ui.unit.dp\n"
            "import androidx.compose.ui.window.Window\n"
            "import androidx.compose.ui.window.application\n"
            "import androidx.compose.ui.window.rememberWindowState\n\n"
            f"@Composable\n@Preview\n"
            f"fun App() {{\n"
            "    MaterialTheme {\n"
            "        Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {\n"
            "            Column(\n"
            "                modifier = Modifier.fillMaxSize().padding(24.dp),\n"
            "                horizontalAlignment = Alignment.CenterHorizontally,\n"
            "                verticalArrangement = Arrangement.Center,\n"
            "            ) {\n"
            f"                Text(text = \"{name}\", style = MaterialTheme.typography.headlineLarge)\n"
            "                Spacer(modifier = Modifier.height(16.dp))\n"
            "                Text(text = \"Welcome to your Compose Multiplatform app\")\n"
            "            }\n"
            "        }\n"
            "    }\n"
            "}\n\n"
            "fun main() = application {\n"
            "    val state = rememberWindowState(width = 1200.dp, height = 800.dp)\n"
            f"    Window(onCloseRequest = ::exitApplication, state = state, title = \"{name}\") {{\n"
            "        App()\n"
            "    }\n"
            "}\n"
        )

        return files

    # ==================================================================
    # Private — Main window generators
    # ==================================================================

    def _gen_main_window_qt(self, name: str, framework: str, layout: dict[str, Any]) -> str:
        import_name = "PyQt6" if framework == "PyQt6" else "PySide6"
        size = layout.get("size", [1200, 800])
        return (
            f"from {import_name.lower()}.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout\n"
            f"from {import_name.lower()}.QtCore import Qt\n\n\n"
            f"class MainWindow(QMainWindow):\n"
            "    def __init__(self):\n"
            "        super().__init__()\n"
            f"        self.setWindowTitle('{name}')\n"
            f"        self.resize({size[0]}, {size[1]})\n"
            "        self._setup_ui()\n\n"
            "    def _setup_ui(self):\n"
            "        central = QWidget()\n"
            "        self.setCentralWidget(central)\n"
            "        layout = QVBoxLayout(central)\n\n"
            "        # Add your widgets here\n"
            "        self.statusBar().showMessage('Ready')\n"
        )

    def _gen_main_window_tkinter(self, name: str, layout: dict[str, Any]) -> str:
        size = layout.get("size", [1200, 800])
        return (
            "import tkinter as tk\n"
            "from tkinter import ttk\n\n\n"
            f"class MainWindow(tk.Tk):\n"
            "    def __init__(self):\n"
            "        super().__init__()\n"
            f"        self.title('{name}')\n"
            f"        self.geometry('{size[0]}x{size[1]}')\n"
            "        self._setup_ui()\n\n"
            "    def _setup_ui(self):\n"
            "        main_frame = ttk.Frame(self)\n"
            "        main_frame.pack(fill=tk.BOTH, expand=True)\n\n"
            "        # Add your widgets here\n"
            "        status = ttk.Label(self, text='Ready', relief=tk.SUNKEN)\n"
            "        status.pack(side=tk.BOTTOM, fill=tk.X)\n"
        )

    def _gen_main_window_electron(self, name: str, layout: dict[str, Any]) -> str:
        return (
            "// Electron main window is configured in src/main.js\n"
            "// This file provides the renderer process UI\n\n"
            f"document.title = '{name}';\n\n"
            "const app = document.getElementById('app');\n"
            "app.innerHTML = `\n"
            "  <header><h1>" + name + "</h1></header>\n"
            "  <main>\n"
            "    <p>Welcome to your desktop application.</p>\n"
            "  </main>\n"
            "`;\n"
        )

    def _gen_main_window_tauri(self, name: str, layout: dict[str, Any]) -> str:
        return (
            "// Tauri main window is configured in src-tauri/tauri.conf.json\n"
            "// This file provides the web frontend UI\n\n"
            f"document.title = '{name}';\n\n"
            "const app = document.getElementById('app');\n"
            "if (app) {\n"
            "  app.innerHTML = `\n"
            "    <h1>" + name + "</h1>\n"
            "    <p>Welcome to your Tauri desktop application.</p>\n"
            "  `;\n"
            "}\n"
        )

    def _gen_main_window_flutter(self, name: str, layout: dict[str, Any]) -> str:
        class_name = name.lower().replace(" ", "_").replace("-", "_")
        class_name = "".join(w.title() for w in class_name.split("_"))
        return (
            "import 'package:flutter/material.dart';\n\n"
            f"class {class_name}Window extends StatelessWidget {{\n"
            f"  const {class_name}Window({{super.key}});\n\n"
            "  @override\n"
            "  Widget build(BuildContext context) {\n"
            "    return Scaffold(\n"
            f"      appBar: AppBar(title: const Text('{name}')),\n"
            "      body: const Center(\n"
            "        child: Text('Main Window'),\n"
            "      ),\n"
            "    );\n"
            "  }\n"
            "}\n"
        )

    def _gen_main_window_compose(self, name: str, layout: dict[str, Any]) -> str:
        return (
            "import androidx.compose.foundation.layout.*\n"
            "import androidx.compose.material3.*\n"
            "import androidx.compose.runtime.*\n"
            "import androidx.compose.ui.Alignment\n"
            "import androidx.compose.ui.Modifier\n"
            "import androidx.compose.ui.unit.dp\n\n"
            "@Composable\n"
            f"fun {name.replace(' ', '')}Window() {{\n"
            "    Scaffold(\n"
            f"        topBar = {{ TopAppBar(title = {{ Text(\"{name}\") }}) }}\n"
            "    ) {{ padding ->\n"
            "        Box(\n"
            "            modifier = Modifier.fillMaxSize().padding(padding),\n"
            "            contentAlignment = Alignment.Center,\n"
            "        ) {\n"
            "            Text(text = \"Main Window\")\n"
            "        }\n"
            "    }\n"
            "}\n"
        )

    # ==================================================================
    # Private — Menu generators
    # ==================================================================

    def _gen_menu_qt(self, name: str, items: list[dict[str, Any]], framework: str) -> str:
        import_name = "PyQt6" if framework == "PyQt6" else "PySide6"
        lines = [
            f"from {import_name.lower()}.QtWidgets import QMainWindow, QMenuBar, QMenu, QAction\n\n\n",
            "class MenuMixin:\n",
            "    \"\"\"Mixin to attach a menu bar to a QMainWindow.\"\"\"\n\n",
            "    def setup_menu(self: QMainWindow):\n",
            "        menu_bar = self.menuBar()\n",
        ]
        for item in items:
            label = item.get("label", "Menu")
            lines.append(f'        {label.lower().replace(" ", "_")}_menu = menu_bar.addMenu("{label}")\n')
            sub = item.get("items", item.get("submenu", []))
            for sub_item in sub:
                if isinstance(sub_item, dict):
                    sub_label = sub_item.get("label", sub_item.get("name", ""))
                    action = sub_item.get("action", sub_label.lower().replace(" ", "_"))
                    lines.append(f'        {action}_action = QAction("{sub_label}", self)\n')
                    lines.append(f"        {action}_action.triggered.connect(self.on_{action})\n")
                    lines.append(f'        {label.lower().replace(" ", "_")}_menu.addAction({action}_action)\n')
                else:
                    action = sub_item.lower().replace(" ", "_")
                    lines.append(f'        {action}_action = QAction("{sub_item}", self)\n')
                    lines.append(f"        {action}_action.triggered.connect(self.on_{action})\n")
                    lines.append(f'        {label.lower().replace(" ", "_")}_menu.addAction({action}_action)\n')
            lines.append("\n")
        return "".join(lines)

    def _gen_menu_tkinter(self, name: str, items: list[dict[str, Any]]) -> str:
        lines = [
            "import tkinter as tk\n\n\n",
            "def setup_menu(root: tk.Tk) -> tk.Menu:\n",
            "    menubar = tk.Menu(root)\n",
        ]
        for item in items:
            label = item.get("label", "Menu")
            var = label.lower().replace(" ", "_")
            lines.append(f'    {var} = tk.Menu(menubar, tearoff=0)\n')
            sub = item.get("items", item.get("submenu", []))
            for sub_item in sub:
                sub_label = sub_item if isinstance(sub_item, str) else sub_item.get("label", "")
                action = sub_label.lower().replace(" ", "_")
                lines.append(f'    {var}.add_command(label="{sub_label}", command=lambda: print("{action}"))\n')
            lines.append(f'    menubar.add_cascade(label="{label}", menu={var})\n')
        lines.append("    root.config(menu=menubar)\n")
        lines.append("    return menubar\n")
        return "".join(lines)

    def _gen_menu_electron(self, name: str, items: list[dict[str, Any]]) -> str:
        lines = [
            "const { Menu } = require('electron');\n\n",
            "function buildMenu() {\n",
            "  const template = [\n",
        ]
        for item in items:
            label = item.get("label", "Menu")
            sub = item.get("items", item.get("submenu", []))
            lines.append(f'    {{ label: "{label}", submenu: [\n')
            for sub_item in sub:
                if isinstance(sub_item, dict):
                    s_label = sub_item.get("label", "")
                    accel = sub_item.get("accelerator", "")
                    accel_part = f', accelerator: "{accel}"' if accel else ""
                    lines.append(f'      {{ label: "{s_label}"{accel_part} }},\n')
                else:
                    lines.append(f'      {{ label: "{sub_item}" }},\n')
            lines.append("    ]},\n")
        lines.append("  ];\n  return Menu.buildFromTemplate(template);\n}\n\nmodule.exports = { buildMenu };\n")
        return "".join(lines)

    def _gen_menu_tauri(self, name: str, items: list[dict[str, Any]]) -> str:
        lines = [
            "// Tauri menu configuration\n"
            "// Menus are configured in Rust via tauri::Menu\n\n"
            "// Example JS-side menu helper\n"
            "function createMenuTemplate() {\n"
            "  return [\n"
        ]
        for item in items:
            label = item.get("label", "Menu")
            sub = item.get("items", item.get("submenu", []))
            lines.append(f'    {{ label: "{label}", submenu: [\n')
            for sub_item in sub:
                s_label = sub_item if isinstance(sub_item, str) else sub_item.get("label", "")
                lines.append(f'      {{ label: "{s_label}" }},\n')
            lines.append("    ]},\n")
        lines.append("  ];\n}\n\nmodule.exports = { createMenuTemplate };\n")
        return "".join(lines)

    def _gen_menu_flutter(self, name: str, items: list[dict[str, Any]]) -> str:
        lines = [
            "import 'package:flutter/material.dart';\n\n",
            "AppBar buildAppBar() {\n",
            f'  return AppBar(title: const Text("{name}"),\n',
            "    actions: [\n",
        ]
        for item in items:
            label = item.get("label", item.get("name", ""))
            lines.append(f'      IconButton(icon: const Icon(Icons.menu), tooltip: "{label}", onPressed: () {{}}),\n')
        lines.append("    ],\n  );\n}\n")
        return "".join(lines)

    def _gen_menu_compose(self, name: str, items: list[dict[str, Any]]) -> str:
        lines = [
            "import androidx.compose.material3.*\n"
            "import androidx.compose.runtime.*\n\n",
            "@Composable\n"
            f"fun {name.replace(' ', '')}TopBar() {{\n",
            "    TopAppBar(\n",
            f"        title = {{ Text(\"{name}\") }},\n",
            "        actions = {\n",
        ]
        for item in items:
            label = item.get("label", item.get("name", ""))
            lines.append(f'            TextButton(onClick = {{}}) {{ Text("{label}") }}\n')
        lines.append("        },\n    )\n}\n")
        return "".join(lines)

    # ==================================================================
    # Private — Dialog generators
    # ==================================================================

    def _gen_dialog_qt(self, name: str, fields: list[dict[str, Any]], framework: str) -> str:
        import_name = "PyQt6" if framework == "PyQt6" else "PySide6"
        lines = [
            f"from {import_name.lower()}.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,\n"
            f"    QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton, QFormLayout)\n"
            f"from {import_name.lower()}.QtCore import Qt\n\n\n",
            f"class {name.replace(' ', '')}Dialog(QDialog):\n",
            "    def __init__(self, parent=None):\n",
            "        super().__init__(parent)\n",
            f"        self.setWindowTitle('{name}')\n",
            "        self.setMinimumWidth(400)\n",
            "        self._setup_ui()\n\n",
            "    def _setup_ui(self):\n",
            "        layout = QFormLayout(self)\n",
        ]
        for f in fields:
            fname = f.get("name", "field")
            label = f.get("label", fname.title())
            ftype = f.get("type", "text")
            if ftype == "text":
                lines.append(f"        self.{fname}_input = QLineEdit()\n")
                lines.append(f'        self.{fname}_input.setPlaceholderText("{f.get("placeholder", "")}")\n')
                lines.append(f'        layout.addRow("{label}:", self.{fname}_input)\n')
            elif ftype == "dropdown":
                lines.append(f"        self.{fname}_input = QComboBox()\n")
                for opt in f.get("options", []):
                    lines.append(f'        self.{fname}_input.addItem("{opt}")\n')
                lines.append(f'        layout.addRow("{label}:", self.{fname}_input)\n')
            elif ftype == "toggle":
                lines.append(f"        self.{fname}_input = QCheckBox()\n")
                lines.append(f"        self.{fname}_input.setChecked({f.get('default', False)})\n")
                lines.append(f'        layout.addRow("{label}:", self.{fname}_input)\n')
            lines.append("\n")
        lines.append(
            "        btn_layout = QHBoxLayout()\n"
            '        ok_btn = QPushButton("OK")\n'
            "        ok_btn.clicked.connect(self.accept)\n"
            '        cancel_btn = QPushButton("Cancel")\n'
            "        cancel_btn.clicked.connect(self.reject)\n"
            "        btn_layout.addStretch()\n"
            "        btn_layout.addWidget(ok_btn)\n"
            "        btn_layout.addWidget(cancel_btn)\n"
            "        layout.addRow(btn_layout)\n"
        )
        return "".join(lines)

    def _gen_dialog_tkinter(self, name: str, fields: list[dict[str, Any]]) -> str:
        lines = [
            "import tkinter as tk\n",
            "from tkinter import ttk\n\n\n",
            f"class {name.replace(' ', '')}Dialog(tk.Toplevel):\n",
            "    def __init__(self, parent):\n",
            "        super().__init__(parent)\n",
            f"        self.title('{name}')\n",
            "        self.resizable(False, False)\n"
            "        self.result = None\n"
            "        self._setup_ui()\n\n",
            "    def _setup_ui(self):\n",
            "        frame = ttk.Frame(self, padding=20)\n"
            "        frame.pack(fill=tk.BOTH, expand=True)\n\n",
        ]
        for f in fields:
            fname = f.get("name", "field")
            label = f.get("label", fname.title())
            ftype = f.get("type", "text")
            if ftype == "text":
                lines.append(f"        ttk.Label(frame, text='{label}:').grid(row={fields.index(f)}, column=0, sticky=tk.W, pady=5)\n")
                lines.append(f"        self.{fname}_var = tk.StringVar()\n")
                lines.append(f"        ttk.Entry(frame, textvariable=self.{fname}_var).grid(row={fields.index(f)}, column=1, pady=5, padx=(10, 0))\n")
            elif ftype == "toggle":
                lines.append(f"        self.{fname}_var = tk.BooleanVar(value={f.get('default', False)})\n")
                lines.append(f"        ttk.Checkbutton(frame, text='{label}', variable=self.{fname}_var).grid(row={fields.index(f)}, column=0, columnspan=2, sticky=tk.W, pady=5)\n")
            lines.append("\n")
        lines.append(
            "        btn_frame = ttk.Frame(frame)\n"
            f"        btn_frame.grid(row={len(fields)}, column=0, columnspan=2, pady=15)\n"
            '        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side=tk.LEFT, padx=5)\n'
            '        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)\n\n'
            "    def _on_ok(self):\n"
            "        self.result = True\n"
            "        self.destroy()\n"
        )
        return "".join(lines)

    def _gen_dialog_electron(self, name: str, fields: list[dict[str, Any]]) -> str:
        inputs = ""
        for f in fields:
            fname = f.get("name", "field")
            label = f.get("label", fname.title())
            ftype = f.get("type", "text")
            placeholder = f.get("placeholder", "")
            if ftype == "text":
                inputs += f'      <label for="{fname}">{label}</label>\n'
                inputs += f'      <input type="text" id="{fname}" name="{fname}" placeholder="{placeholder}"><br><br>\n'
            elif ftype == "toggle":
                inputs += f'      <label for="{fname}">{label}</label>\n'
                inputs += f'      <input type="checkbox" id="{fname}" name="{fname}"><br><br>\n'
        return (
            "// Dialog renderer — load this HTML in a BrowserWindow\n"
            f"// Title: {name}\n\n"
            "const dialogHtml = `\n"
            "<!DOCTYPE html>\n<html><head><style>\n"
            "  body { font-family: sans-serif; padding: 20px; }\n"
            "  input { width: 100%; padding: 8px; margin: 4px 0 12px; box-sizing: border-box; }\n"
            "  button { padding: 8px 20px; margin: 4px; }\n"
            "</style></head><body>\n"
            f"  <h2>{name}</h2>\n"
            f"  <form id=\"dialogForm\">\n{inputs}  </form>\n"
            "  <button onclick=\"window.close()\">Cancel</button>\n"
            "  <button onclick=\"submitForm()\">OK</button>\n"
            "  <script>\n"
            "    function submitForm() {\n"
            "      const data = Object.fromEntries(new FormData(document.getElementById('dialogForm')));\n"
            "      window.api.submitDialog(data);\n"
            "    }\n"
            "  </script>\n"
            "</body></html>\n`;\n\n"
            "module.exports = { dialogHtml };\n"
        )

    def _gen_dialog_tauri(self, name: str, fields: list[dict[str, Any]]) -> str:
        inputs = ""
        for f in fields:
            fname = f.get("name", "field")
            label = f.get("label", fname.title())
            inputs += f'      <label for="{fname}">{label}</label>\n'
            inputs += f'      <input type="text" id="{fname}" name="{fname}"><br><br>\n'
        return (
            f"// Tauri dialog component for: {name}\n\n"
            "<template>\n"
            "  <div class=\"dialog-overlay\">\n"
            f"    <div class=\"dialog\"><h3>{name}</h3>\n"
            f"      <form @submit.prevent=\"submit\">\n{inputs}      </form>\n"
            '      <button @click="$emit(\'close\')">Cancel</button>\n'
            '      <button @click="submit">OK</button>\n'
            "    </div>\n"
            "  </div>\n"
            "</template>\n\n"
            "<script>\n"
            "export default {\n"
            "  methods: {\n"
            "    submit() { this.$emit('submit', this.$data); },\n"
            "  },\n"
            "};\n"
            "</script>\n"
        )

    def _gen_dialog_flutter(self, name: str, fields: list[dict[str, Any]]) -> str:
        return (
            "import 'package:flutter/material.dart';\n\n"
            f"class {name.replace(' ', '')}Dialog extends StatefulWidget {{\n"
            f"  const {name.replace(' ', '')}Dialog({{super.key}});\n\n"
            "  @override\n"
            f"  State<{name.replace(' ', '')}Dialog> createState() => _DialogState();\n"
            "}\n\n"
            f"class _DialogState extends State<{name.replace(' ', '')}Dialog> {{\n"
            "  final _formKey = GlobalKey<FormState>();\n\n"
            "  @override\n"
            "  Widget build(BuildContext context) {\n"
            "    return AlertDialog(\n"
            f"      title: Text('{name}'),\n"
            "      content: Form(\n"
            "        key: _formKey,\n"
            "        child: Column(\n"
            "          mainAxisSize: MainAxisSize.min,\n"
            + "".join(
                f"          [TextField(decoration: InputDecoration(labelText: '{f.get('label', f.get('name', ''))}')),\n"
                for f in fields
            )
            + "        ],\n"
            "        ),\n"
            "      ),\n"
            "      actions: [\n"
            '        TextButton(onPressed: () => Navigator.pop(context), child: const Text("Cancel")),\n'
            '        ElevatedButton(onPressed: () => Navigator.pop(context, true), child: const Text("OK")),\n'
            "      ],\n"
            "    );\n"
            "  }\n"
            "}\n"
        )

    def _gen_dialog_compose(self, name: str, fields: list[dict[str, Any]]) -> str:
        return (
            "import androidx.compose.material3.*\n"
            "import androidx.compose.runtime.*\n\n"
            "@Composable\n"
            f"fun {name.replace(' ', '')}Dialog(onDismiss: () -> Unit) {{\n"
            "    AlertDialog(\n"
            f"        title = {{ Text(\"{name}\") }},\n"
            "        text = {\n"
            "            Column {\n"
            + "".join(
                f'                var {f.get("name", "field")} by remember {{ mutableStateOf("") }}\n'
                f'                OutlinedTextField(value = {f.get("name", "field")}, onValueChange = {{ {f.get("name", "field")} = it }},\n'
                f'                    label = {{ Text("{f.get("label", f.get("name", ""))}") }})\n'
                for f in fields
            )
            + "            }\n"
            "        },\n"
            "        confirmButton = {\n"
            f'            TextButton(onClick = onDismiss) {{ Text("OK") }}\n'
            "        },\n"
            "        dismissButton = {\n"
            f'            TextButton(onClick = onDismiss) {{ Text("Cancel") }}\n'
            "        },\n"
            "        onDismissRequest = onDismiss,\n"
            "    )\n"
            "}\n"
        )

    # ==================================================================
    # Private — Tray icon generators
    # ==================================================================

    def _gen_tray_qt(self, name: str, framework: str) -> str:
        import_name = "PyQt6" if framework == "PyQt6" else "PySide6"
        return (
            f"from {import_name.lower()}.QtWidgets import QSystemTrayIcon, QMenu, QApplication\n"
            f"from {import_name.lower()}.QtGui import QIcon\n\n\n"
            "def setup_tray(parent=None):\n"
            "    tray = QSystemTrayIcon(QIcon('icon.png'), parent)\n"
            f"    tray.setToolTip('{name}')\n"
            "    menu = QMenu()\n"
            '    show_action = menu.addAction("Show")\n'
            '    quit_action = menu.addAction("Quit")\n'
            "    tray.setContextMenu(menu)\n"
            "    tray.activated.connect(lambda reason: tray.show() if reason == QSystemTrayIcon.DoubleClick else None)\n"
            "    quit_action.triggered.connect(QApplication.quit)\n"
            "    tray.show()\n"
            "    return tray\n"
        )

    def _gen_tray_tkinter(self, name: str) -> str:
        return (
            "# System tray icon — requires pystray\n"
            "try:\n"
            "    import pystray\n"
            "    from PIL import Image\n"
            "except ImportError:\n"
            "    print('Install pystray and Pillow for tray support: pip install pystray Pillow')\n\n\n"
            f"def setup_tray():\n"
            f"    def on_show(icon, item): icon.visible = True\n"
            f"    def on_quit(icon, item): icon.stop()\n\n"
            f"    image = Image.new('RGB', (64, 64), 'blue')\n"
            f"    menu = pystray.Menu(\n"
            f"        pystray.MenuItem('Show', on_show),\n"
            f"        pystray.MenuItem('Quit', on_quit),\n"
            f"    )\n"
            f"    icon = pystray.Icon('{name}', image, '{name}', menu)\n"
            f"    icon.run()\n"
        )

    def _gen_tray_electron(self, name: str) -> str:
        return (
            "const { Tray, Menu, nativeImage } = require('electron');\n"
            "const path = require('path');\n\n"
            "let tray = null;\n\n"
            "function createTray(mainWindow) {\n"
            "  const icon = nativeImage.createFromPath(path.join(__dirname, '../assets/icon.png'));\n"
            "  tray = new Tray(icon);\n"
            f"  tray.setToolTip('{name}');\n\n"
            "  const contextMenu = Menu.buildFromTemplate([\n"
            '    { label: "Show", click: () => mainWindow.show() },\n'
            '    { label: "Quit", click: () => require("electron").app.quit() },\n'
            "  ]);\n\n"
            "  tray.setContextMenu(contextMenu);\n"
            "  tray.on('double-click', () => mainWindow.show());\n"
            "  return tray;\n"
            "}\n\n"
            "module.exports = { createTray };\n"
        )

    def _gen_tray_tauri(self, name: str) -> str:
        return (
            "// Tauri system tray — configure in Rust via tauri::SystemTray\n"
            "// Example JS-side event handling\n\n"
            "import { invoke } from '@tauri-apps/api/tauri';\n\n"
            "async function showTray() {\n"
            "  await invoke('show_tray');\n"
            "}\n\n"
            "module.exports = { showTray };\n"
        )

    def _gen_tray_flutter(self, name: str) -> str:
        return (
            "import 'package:flutter/material.dart';\n\n"
            "// System tray for Flutter desktop requires tray_manager package\n"
            "// Add tray_manager to pubspec.yaml dependencies\n\n"
            f"class {name.replace(' ', '')}Tray {{\n"
            "  // Implement using tray_manager package\n"
            "  // See: https://pub.dev/packages/tray_manager\n"
            "}\n"
        )

    def _gen_tray_compose(self, name: str) -> str:
        return (
            "// Compose Multiplatform system tray\n"
            "// Requires androidx.compose.desktop:desktop-runtime\n\n"
            "import androidx.compose.ui.window.Tray\n"
            "import androidx.compose.ui.window.rememberTrayState\n\n"
            "@Composable\n"
            f"fun {name.replace(' ', '')}Tray() {{\n"
            "    val trayState = rememberTrayState()\n"
            f"    Tray(state = trayState, tooltip = \"{name}\")\n"
            "    // Add menu items via trayState\n"
            "}\n"
        )

    # ==================================================================
    # Private — Settings page generators
    # ==================================================================

    def _gen_settings_qt(self, name: str, framework: str, settings: list[dict[str, Any]]) -> str:
        import_name = "PyQt6" if framework == "PyQt6" else "PySide6"
        lines = [
            f"from {import_name.lower()}.QtWidgets import (QWidget, QVBoxLayout, QFormLayout,\n"
            f"    QLabel, QLineEdit, QComboBox, QCheckBox, QSpinBox, QPushButton, QColorDialog)\n\n\n",
            f"class SettingsPage(QWidget):\n",
            "    def __init__(self, parent=None):\n",
            "        super().__init__(parent)\n",
            "        self._settings = {}\n",
            "        self._setup_ui()\n\n",
            "    def _setup_ui(self):\n",
            "        layout = QVBoxLayout(self)\n",
            "        form = QFormLayout()\n",
        ]
        for s in settings:
            key = s.get("key", "setting")
            label = s.get("label", key.title())
            stype = s.get("type", "text")
            default = s.get("default", "")
            if stype == "toggle":
                lines.append(f"        self.{key}_check = QCheckBox()\n")
                lines.append(f"        self.{key}_check.setChecked({default})\n")
                lines.append(f'        form.addRow("{label}:", self.{key}_check)\n')
            elif stype == "number":
                lines.append(f"        self.{key}_spin = QSpinBox()\n")
                lines.append(f"        self.{key}_spin.setValue({default})\n")
                lines.append(f'        form.addRow("{label}:", self.{key}_spin)\n')
            elif stype == "dropdown":
                lines.append(f"        self.{key}_combo = QComboBox()\n")
                for opt in s.get("options", []):
                    lines.append(f'        self.{key}_combo.addItem("{opt}")\n')
                lines.append(f'        form.addRow("{label}:", self.{key}_combo)\n')
            else:
                lines.append(f"        self.{key}_input = QLineEdit()\n")
                lines.append(f'        self.{key}_input.setText("{default}")\n')
                lines.append(f'        form.addRow("{label}:", self.{key}_input)\n')
        lines.append("        layout.addLayout(form)\n")
        lines.append('        save_btn = QPushButton("Save Settings")\n')
        lines.append("        save_btn.clicked.connect(self._save)\n")
        lines.append("        layout.addWidget(save_btn)\n")
        lines.append("        layout.addStretch()\n\n")
        lines.append("    def _save(self):\n")
        lines.append("        self._settings = {}\n")
        for s in settings:
            key = s.get("key", "setting")
            stype = s.get("type", "text")
            if stype == "toggle":
                lines.append(f"        self._settings['{key}'] = self.{key}_check.isChecked()\n")
            elif stype == "number":
                lines.append(f"        self._settings['{key}'] = self.{key}_spin.value()\n")
            elif stype == "dropdown":
                lines.append(f"        self._settings['{key}'] = self.{key}_combo.currentText()\n")
            else:
                lines.append(f"        self._settings['{key}'] = self.{key}_input.text()\n")
        lines.append("        return self._settings\n")
        return "".join(lines)

    def _gen_settings_tkinter(self, name: str, settings: list[dict[str, Any]]) -> str:
        lines = [
            "import tkinter as tk\n",
            "from tkinter import ttk\n\n\n",
            f"class SettingsPage(ttk.Frame):\n",
            "    def __init__(self, parent):\n",
            "        super().__init__(parent)\n",
            "        self._vars = {}\n",
            "        self._setup_ui()\n\n",
            "    def _setup_ui(self):\n",
        ]
        for idx, s in enumerate(settings):
            key = s.get("key", "setting")
            label = s.get("label", key.title())
            stype = s.get("type", "text")
            default = s.get("default", "")
            if stype == "toggle":
                lines.append(f"        self._vars['{key}'] = tk.BooleanVar(value={default})\n")
                lines.append(f"        ttk.Checkbutton(self, text='{label}', variable=self._vars['{key}']).grid(row={idx}, column=0, columnspan=2, sticky=tk.W, pady=5)\n")
            elif stype == "number":
                lines.append(f"        self._vars['{key}'] = tk.IntVar(value={default})\n")
                lines.append(f"        ttk.Label(self, text='{label}:').grid(row={idx}, column=0, sticky=tk.W, pady=5)\n")
                lines.append(f"        ttk.Entry(self, textvariable=self._vars['{key}']).grid(row={idx}, column=1, pady=5, padx=(10, 0))\n")
            else:
                lines.append(f"        self._vars['{key}'] = tk.StringVar(value='{default}')\n")
                lines.append(f"        ttk.Label(self, text='{label}:').grid(row={idx}, column=0, sticky=tk.W, pady=5)\n")
                lines.append(f"        ttk.Entry(self, textvariable=self._vars['{key}']).grid(row={idx}, column=1, pady=5, padx=(10, 0))\n")
        lines.append("\n    def get_settings(self):\n")
        lines.append("        return {k: v.get() for k, v in self._vars.items()}\n")
        return "".join(lines)

    def _gen_settings_electron(self, name: str, settings: list[dict[str, Any]]) -> str:
        inputs = ""
        for s in settings:
            key = s.get("key", "setting")
            label = s.get("label", key.title())
            stype = s.get("type", "text")
            default = s.get("default", "")
            if stype == "toggle":
                checked = "checked" if default else ""
                inputs += f'      <label><input type="checkbox" id="{key}" name="{key}" {checked}> {label}</label><br><br>\n'
            elif stype == "number":
                inputs += f'      <label for="{key}">{label}</label>\n'
                inputs += f'      <input type="number" id="{key}" name="{key}" value="{default}"><br><br>\n'
            elif stype == "dropdown":
                inputs += f'      <label for="{key}">{label}</label>\n'
                inputs += f'      <select id="{key}" name="{key}">\n'
                for opt in s.get("options", []):
                    selected = "selected" if opt == default else ""
                    inputs += f'        <option value="{opt}" {selected}>{opt}</option>\n'
                inputs += "      </select><br><br>\n"
            else:
                inputs += f'      <label for="{key}">{label}</label>\n'
                inputs += f'      <input type="text" id="{key}" name="{key}" value="{default}"><br><br>\n'
        return (
            f"// Settings page for {name}\n\n"
            "const settingsHtml = `\n"
            "<!DOCTYPE html>\n<html><head><style>\n"
            "  body { font-family: sans-serif; padding: 20px; }\n"
            "  input, select { width: 100%; padding: 8px; margin: 4px 0 12px; box-sizing: border-box; }\n"
            "  label { font-weight: bold; }\n"
            "  button { padding: 8px 20px; margin: 4px; }\n"
            "</style></head><body>\n"
            f"  <h2>{name} — Settings</h2>\n"
            f"  <form id=\"settingsForm\">\n{inputs}  </form>\n"
            '  <button onclick="save()">Save</button>\n'
            "  <script>\n"
            "    async function save() {\n"
            "      const data = Object.fromEntries(new FormData(document.getElementById('settingsForm')));\n"
            "      await window.api.saveSettings(data);\n"
            "    }\n"
            "  </script>\n"
            "</body></html>\n`;\n\n"
            "module.exports = { settingsHtml };\n"
        )

    def _gen_settings_tauri(self, name: str, settings: list[dict[str, Any]]) -> str:
        inputs = ""
        for s in settings:
            key = s.get("key", "setting")
            label = s.get("label", key.title())
            inputs += f'      <label for="{key}">{label}</label>\n'
            inputs += f'      <input type="text" id="{key}" name="{key}"><br><br>\n'
        return (
            f"// Settings page for {name}\n\n"
            "<template>\n"
            f"  <div class=\"settings\"><h3>{name} Settings</h3>\n"
            "    <form @submit.prevent=\"save\">\n"
            f"{inputs}      <button type=\"submit\">Save</button>\n"
            "    </form>\n"
            "  </div>\n"
            "</template>\n\n"
            "<script>\n"
            "export default {\n"
            "  methods: {\n"
            "    async save() { await invoke('save_settings', { settings: this.$data }); },\n"
            "  },\n"
            "};\n"
            "</script>\n"
        )

    def _gen_settings_flutter(self, name: str, settings: list[dict[str, Any]]) -> str:
        return (
            "import 'package:flutter/material.dart';\n\n"
            f"class {name.replace(' ', '')}Settings extends StatefulWidget {{\n"
            f"  const {name.replace(' ', '')}Settings({{super.key}});\n\n"
            "  @override\n"
            f"  State<{name.replace(' ', '')}Settings> createState() => _SettingsState();\n"
            "}\n\n"
            f"class _SettingsState extends State<{name.replace(' ', '')}Settings> {{\n"
            "  @override\n"
            "  Widget build(BuildContext context) {\n"
            "    return Scaffold(\n"
            f"      appBar: AppBar(title: Text('{name} Settings')),\n"
            "      body: ListView(\n"
            "        padding: const EdgeInsets.all(16),\n"
            "        children: [\n"
            + "".join(
                f"          SwitchListTile(title: const Text('{s.get('label', s.get('key', ''))}'), "
                f"value: false, onChanged: (v) {{}}),\n"
                if s.get("type") == "toggle"
                else f"          ListTile(title: Text('{s.get('label', s.get('key', ''))}')), \n"
                for s in settings
            )
            + "        ],\n"
            "      ),\n"
            "    );\n"
            "  }\n"
            "}\n"
        )

    def _gen_settings_compose(self, name: str, settings: list[dict[str, Any]]) -> str:
        return (
            "import androidx.compose.foundation.layout.*\n"
            "import androidx.compose.material3.*\n"
            "import androidx.compose.runtime.*\n"
            "import androidx.compose.ui.Modifier\n"
            "import androidx.compose.ui.unit.dp\n\n"
            "@Composable\n"
            f"fun {name.replace(' ', '')}Settings(onSave: (Map<String, Any>) -> Unit) {{\n"
            "    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {\n"
            f'        Text("{name} Settings", style = MaterialTheme.typography.headlineMedium)\n'
            "        Spacer(modifier = Modifier.height(16.dp))\n"
            + "".join(
                f"        var {s.get('key', 'setting')} by remember {{ mutableStateOf(false) }}\n"
                f"        Switch(checked = {s.get('key', 'setting')}, onCheckedChange = {{ {s.get('key', 'setting')} = it }})\n"
                f"        Text(\"{s.get('label', s.get('key', ''))}\")\n\n"
                if s.get("type") == "toggle"
                else f"        var {s.get('key', 'setting')}Text by remember {{ mutableStateOf(\"\") }}\n"
                f"        OutlinedTextField(value = {s.get('key', 'setting')}Text, onValueChange = {{ {s.get('key', 'setting')}Text = it }},\n"
                f"            label = {{ Text(\"{s.get('label', s.get('key', ''))}\") }})\n\n"
                for s in settings
            )
            + "        Spacer(modifier = Modifier.height(16.dp))\n"
            "        Button(onClick = { onSave(emptyMap()) }) { Text(\"Save\") }\n"
            "    }\n"
            "}\n"
        )

    # ==================================================================
    # Private — Installer generators
    # ==================================================================

    def _gen_nsis_installer(self, name: str, framework: str) -> str:
        return (
            "; NSIS Installer Script\n"
            f"; {name} — generated by JARVIS DesktopAppBuilder\n\n"
            "!include \"MUI2.nsh\"\n\n"
            f'Name "{name}"\n'
            f'OutFile "{name.lower().replace(" ", "-")}-setup.exe"\n'
            "InstallDir \"$PROGRAMFILES\\\\{name}\"\n"
            "RequestExecutionLevel admin\n\n"
            "Section \"Install\"\n"
            "  SetOutPath $INSTDIR\n"
            '  File "dist\\\\{name}.exe"\n'
            '  File /r "dist\\\\resources\\\\*.*"\n'
            "  CreateUninstaller \"$INSTDIR\\\\uninstall.exe\"\n"
            '  CreateDirectory "$SMPROGRAMS\\\\{name}"\n'
            '  CreateShortcut "$SMPROGRAMS\\\\{name}\\\\{name}.lnk" "$INSTDIR\\\\{name}.exe"\n'
            '  WriteRegStr HKLM "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Uninstall\\\\{name}" \\\n'
            '    "DisplayName" "{name}"\n'
            '  WriteRegStr HKLM "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Uninstall\\\\{name}" \\\n'
            '    "UninstallString" "$INSTDIR\\\\uninstall.exe"\n'
            "SectionEnd\n\n"
            "Section \"Uninstall\"\n"
            '  Delete "$INSTDIR\\\\{name}.exe"\n'
            '  Delete "$INSTDIR\\\\uninstall.exe"\n'
            '  RMDir /r "$INSTDIR"\n'
            '  Delete "$SMPROGRAMS\\\\{name}\\\\{name}.lnk"\n'
            '  RMDir "$SMPROGRAMS\\\\{name}"\n'
            "  DeleteRegKey HKLM \"Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Uninstall\\\\{name}\"\n"
            "SectionEnd\n"
        )

    def _gen_dmg_config(self, name: str, framework: str) -> str:
        return json.dumps({
            "title": name,
            "icon": "assets/icon.icns",
            "background": "assets/background.png",
            "icon-size": 100,
            "window": {"size": {"width": 660, "height": 400}},
            "contents": [
                {"x": 180, "y": 170, "type": "file", "path": f"dist/{name}.app"},
                {"x": 480, "y": 170, "type": "link", "path": "/Applications"},
            ],
        }, indent=2)

    def _gen_entitlements(self, name: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n<dict>\n'
            '  <key>com.apple.security.cs.allow-jit</key><true/>\n'
            '  <key>com.apple.security.cs.allow-unsigned-executable-memory</key><true/>\n'
            '  <key>com.apple.security.network.client</key><true/>\n'
            '</dict>\n</plist>\n'
        )

    def _gen_appimage_desktop(self, name: str) -> str:
        slug = name.lower().replace(" ", "-")
        return (
            "[Desktop Entry]\n"
            f"Name={name}\n"
            f"Exec={slug}\n"
            "Type=Application\n"
            "Categories=Utility;\n"
            f"Icon={slug}\n"
        )

    def _gen_appimage_config(self, name: str, framework: str) -> str:
        slug = name.lower().replace(" ", "-")
        return json.dumps({
            "version": 1,
            "assembly": {
                "name": slug,
                "version": "1.0.0",
                "statement": f"{name} desktop application",
            },
            "build": {
                "appDir": "dist",
                "arch": "x86_64",
                "targetDir": "AppDir",
            },
            "update": {"url": f"https://example.com/{slug}/releases/download/v1.0.0/{slug}.AppImage"},
        }, indent=2)

    # ==================================================================
    # README
    # ==================================================================

    def _gen_readme(self, name: str, framework: str) -> str:
        return (
            f"# {name}\n\n"
            f"Desktop application built with **{framework}**.\n\n"
            "## Getting Started\n\n"
            "```bash\n"
            "# Install dependencies\n"
        ) + (
            "npm install\n\n"
            "# Run the app\n"
            "npm start\n"
            "```\n" if framework.lower() in ("electron", "tauri") else
            "pip install -r requirements.txt\n\n"
            "# Run the app\n"
            "python main.py\n"
            "```\n" if framework.lower() in ("pyqt6", "pyside6", "tkinter") else
            "flutter pub get\n"
            "flutter run -d desktop\n"
            "```\n" if framework.lower() == "flutter" else
            "./gradlew run\n"
            "```\n"
        ) + (
            "\n## Build\n\n"
            "See the project documentation for build instructions.\n"
        )
