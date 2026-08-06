"""
Code Generator — generate code from natural language descriptions.
=================================================================
Pattern-based code generation without external API calls.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from typing import Any, Optional

from jarvis.core.coding.base import (
    CodeLanguage,
    CodingResult,
    TaskType,
)


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

PROJECT_TEMPLATES: dict[str, dict[str, Any]] = {
    "fastapi": {
        "name": "FastAPI",
        "description": "FastAPI REST API application",
        "language": CodeLanguage.PYTHON,
        "files": {
            "requirements.txt": "fastapi\nuvicorn\npydantic",
            "app/__init__.py": "",
            "app/main.py": textwrap.dedent('''\
                from fastapi import FastAPI

                app = FastAPI(title="{name}", version="0.1.0")


                @app.get("/")
                async def root():
                    return {{"message": "Hello World"}}


                @app.get("/health")
                async def health():
                    return {{"status": "healthy"}}


                if __name__ == "__main__":
                    import uvicorn
                    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
            '''),
            "app/routes/__init__.py": "",
            "app/routes/items.py": textwrap.dedent('''\
                from fastapi import APIRouter
                from pydantic import BaseModel

                router = APIRouter(prefix="/items", tags=["items"])


                class Item(BaseModel):
                    name: str
                    description: str = ""
                    price: float


                @router.get("/")
                async def list_items():
                    return []


                @router.post("/")
                async def create_item(item: Item):
                    return item
            '''),
        },
    },
    "flask": {
        "name": "Flask",
        "description": "Flask web application",
        "language": CodeLanguage.PYTHON,
        "files": {
            "requirements.txt": "flask",
            "app/__init__.py": "",
            "app/main.py": textwrap.dedent('''\
                from flask import Flask, jsonify

                app = Flask(__name__)


                @app.route("/")
                def index():
                    return jsonify(message="Hello World")


                @app.route("/health")
                def health():
                    return jsonify(status="healthy")


                if __name__ == "__main__":
                    app.run(debug=True, port=5000)
            '''),
        },
    },
    "react": {
        "name": "React",
        "description": "React frontend application",
        "language": CodeLanguage.JAVASCRIPT,
        "files": {
            "package.json": textwrap.dedent('''\
                {{
                  "name": "{name}",
                  "version": "0.1.0",
                  "private": true,
                  "dependencies": {{
                    "react": "^18.2.0",
                    "react-dom": "^18.2.0",
                    "react-scripts": "5.0.1"
                  }},
                  "scripts": {{
                    "start": "react-scripts start",
                    "build": "react-scripts build",
                    "test": "react-scripts test"
                  }}
                }}
            '''),
            "public/index.html": textwrap.dedent('''\
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="utf-8" />
                    <title>{name}</title>
                </head>
                <body>
                    <div id="root"></div>
                </body>
                </html>
            '''),
            "src/index.js": textwrap.dedent('''\
                import React from 'react';
                import ReactDOM from 'react-dom/client';
                import App from './App';

                const root = ReactDOM.createRoot(document.getElementById('root'));
                root.render(
                    <React.StrictMode>
                        <App />
                    </React.StrictMode>
                );
            '''),
            "src/App.js": textwrap.dedent('''\
                import React, {{ useState, useEffect }} from 'react';

                function App() {{
                    const [message, setMessage] = useState('');

                    useEffect(() => {{
                        fetch('/api')
                            .then(res => res.json())
                            .then(data => setMessage(data.message));
                    }}, []);

                    return (
                        <div className="App">
                            <h1>{name}</h1>
                            <p>{{message}}</p>
                        </div>
                    );
                }}

                export default App;
            '''),
        },
    },
    "vue": {
        "name": "Vue",
        "description": "Vue.js frontend application",
        "language": CodeLanguage.JAVASCRIPT,
        "files": {
            "package.json": textwrap.dedent('''\
                {{
                  "name": "{name}",
                  "version": "0.1.0",
                  "scripts": {{
                    "serve": "vue-cli-service serve",
                    "build": "vue-cli-service build"
                  }},
                  "dependencies": {{
                    "vue": "^3.3.0"
                  }}
                }}
            '''),
            "src/main.js": textwrap.dedent('''\
                import {{ createApp }} from 'vue'
                import App from './App.vue'

                createApp(App).mount('#app')
            '''),
            "src/App.vue": textwrap.dedent('''\
                <template>
                    <div id="app">
                        <h1>{name}</h1>
                        <p>{{{{ message }}}}</p>
                    </div>
                </template>

                <script>
                export default {{
                    name: 'App',
                    data() {{
                        return {{ message: '' }};
                    }},
                    mounted() {{
                        fetch('/api')
                            .then(res => res.json())
                            .then(data => {{ this.message = data.message; }});
                    }}
                }};
                </script>
            '''),
        },
    },
    "express": {
        "name": "Express",
        "description": "Express.js REST API",
        "language": CodeLanguage.JAVASCRIPT,
        "files": {
            "package.json": textwrap.dedent('''\
                {{
                  "name": "{name}",
                  "version": "0.1.0",
                  "scripts": {{
                    "start": "node src/server.js",
                    "dev": "nodemon src/server.js"
                  }},
                  "dependencies": {{
                    "express": "^4.18.0"
                  }}
                }}
            '''),
            "src/server.js": textwrap.dedent('''\
                const express = require('express');
                const app = express();
                const PORT = process.env.PORT || 3000;

                app.use(express.json());

                app.get('/', (req, res) => {{
                    res.json({{ message: 'Hello World' }});
                }});

                app.get('/health', (req, res) => {{
                    res.json({{ status: 'healthy' }});
                }});

                app.listen(PORT, () => {{
                    console.log(`Server running on port ${{PORT}}`);
                }});
            '''),
        },
    },
    "nextjs": {
        "name": "Next.js",
        "description": "Next.js full-stack application",
        "language": CodeLanguage.JAVASCRIPT,
        "files": {
            "package.json": textwrap.dedent('''\
                {{
                  "name": "{name}",
                  "version": "0.1.0",
                  "scripts": {{
                    "dev": "next dev",
                    "build": "next build",
                    "start": "next start"
                  }},
                  "dependencies": {{
                    "next": "^13.4.0",
                    "react": "^18.2.0",
                    "react-dom": "^18.2.0"
                  }}
                }}
            '''),
            "pages/index.js": textwrap.dedent('''\
                export default function Home() {{
                    return (
                        <div>
                            <h1>{name}</h1>
                            <p>Welcome to your Next.js app</p>
                        </div>
                    );
                }}
            '''),
            "pages/api/hello.js": textwrap.dedent('''\
                export default function handler(req, res) {{
                    res.status(200).json({{ message: 'Hello World' }});
                }}
            '''),
        },
    },
    "django": {
        "name": "Django",
        "description": "Django web application",
        "language": CodeLanguage.PYTHON,
        "files": {
            "requirements.txt": "django",
            "manage.py": textwrap.dedent('''\
                #!/usr/bin/env python
                import os
                import sys

                def main():
                    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
                    try:
                        from django.core.management import execute_from_command_line
                    except ImportError as exc:
                        raise ImportError(
                            "Couldn't import Django."
                        ) from exc
                    execute_from_command_line(sys.argv)


                if __name__ == "__main__":
                    main()
            '''),
            "settings.py": textwrap.dedent('''\
                from pathlib import Path

                BASE_DIR = Path(__file__).resolve().parent
                SECRET_KEY = "change-me-in-production"
                DEBUG = True
                ALLOWED_HOSTS = []
                INSTALLED_APPS = ["django.contrib.contenttypes"]
                ROOT_URLCONF = "urls"
                WSGI_APPLICATION = "wsgi.application"
                DATABASES = {{
                    "default": {{
                        "ENGINE": "django.db.backends.sqlite3",
                        "NAME": BASE_DIR / "db.sqlite3",
                    }}
                }}
            '''),
            "urls.py": textwrap.dedent('''\
                from django.urls import path

                urlpatterns = [
                    path("", lambda req: __import__("django.http", fromlist=["JsonResponse"]).JsonResponse({{"message": "Hello World"}})),
                ]
            '''),
        },
    },
    "pyqt": {
        "name": "PyQt",
        "description": "PyQt5 desktop application",
        "language": CodeLanguage.PYTHON,
        "files": {
            "requirements.txt": "PyQt5",
            "main.py": textwrap.dedent('''\
                import sys
                from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
                from PyQt5.QtCore import Qt


                class MainWindow(QMainWindow):
                    def __init__(self):
                        super().__init__()
                        self.setWindowTitle("{name}")
                        self.setMinimumSize(800, 600)

                        central = QWidget()
                        layout = QVBoxLayout(central)

                        label = QLabel("Hello World")
                        label.setAlignment(Qt.AlignCenter)
                        layout.addWidget(label)

                        self.setCentralWidget(central)


                if __name__ == "__main__":
                    app = QApplication(sys.argv)
                    window = MainWindow()
                    window.show()
                    sys.exit(app.exec_())
            '''),
        },
    },
    "tkinter": {
        "name": "Tkinter",
        "description": "Tkinter desktop application",
        "language": CodeLanguage.PYTHON,
        "files": {
            "main.py": textwrap.dedent('''\
                import tkinter as tk
                from tkinter import ttk


                class App:
                    def __init__(self, root):
                        self.root = root
                        self.root.title("{name}")
                        self.root.geometry("800x600")

                        label = ttk.Label(root, text="Hello World", font=("Arial", 24))
                        label.pack(expand=True)


                if __name__ == "__main__":
                    root = tk.Tk()
                    app = App(root)
                    root.mainloop()
            '''),
        },
    },
    "pytorch": {
        "name": "PyTorch",
        "description": "PyTorch deep learning project",
        "language": CodeLanguage.PYTHON,
        "files": {
            "requirements.txt": "torch\nnumpy",
            "model.py": textwrap.dedent('''\
                import torch
                import torch.nn as nn


                class SimpleNet(nn.Module):
                    def __init__(self, input_size, hidden_size, output_size):
                        super().__init__()
                        self.layer1 = nn.Linear(input_size, hidden_size)
                        self.relu = nn.ReLU()
                        self.layer2 = nn.Linear(hidden_size, output_size)

                    def forward(self, x):
                        x = self.layer1(x)
                        x = self.relu(x)
                        x = self.layer2(x)
                        return x
            '''),
            "train.py": textwrap.dedent('''\
                import torch
                from model import SimpleNet

                def train():
                    model = SimpleNet(784, 128, 10)
                    criterion = torch.nn.CrossEntropyLoss()
                    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

                    print("Training {name} model...")

                if __name__ == "__main__":
                    train()
            '''),
        },
    },
    "tensorflow": {
        "name": "TensorFlow",
        "description": "TensorFlow/Keras deep learning project",
        "language": CodeLanguage.PYTHON,
        "files": {
            "requirements.txt": "tensorflow\nnumpy",
            "model.py": textwrap.dedent('''\
                import tensorflow as tf


                def build_model(input_shape, num_classes):
                    model = tf.keras.Sequential([
                        tf.keras.layers.Dense(128, activation="relu", input_shape=(input_shape,)),
                        tf.keras.layers.Dropout(0.2),
                        tf.keras.layers.Dense(num_classes, activation="softmax"),
                    ])
                    model.compile(
                        optimizer="adam",
                        loss="sparse_categorical_crossentropy",
                        metrics=["accuracy"],
                    )
                    return model
            '''),
            "train.py": textwrap.dedent('''\
                from model import build_model

                def train():
                    model = build_model(784, 10)
                    print("Training {name} model...")

                if __name__ == "__main__":
                    train()
            '''),
        },
    },
}


# ---------------------------------------------------------------------------
# Function / class templates per language
# ---------------------------------------------------------------------------

_FUNCTION_TEMPLATES: dict[CodeLanguage, str] = {
    CodeLanguage.PYTHON: textwrap.dedent('''\
        def {name}({params}){ret}:
            """{docstring}"""
            {body}
    '''),
    CodeLanguage.JAVASCRIPT: textwrap.dedent('''\
        /**
         * {docstring}
         */
        function {name}({params}) {{
            {body}
        }}
    '''),
    CodeLanguage.TYPESCRIPT: textwrap.dedent('''\
        /**
         * {docstring}
         */
        function {name}({params}): {ret} {{
            {body}
        }}
    '''),
    CodeLanguage.JAVA: textwrap.dedent('''\
        /**
         * {docstring}
         */
        public {ret} {name}({params}) {{
            {body}
        }}
    '''),
    CodeLanguage.GO: textwrap.dedent('''\
        // {docstring}
        func {name}({params}) {ret} {{
            {body}
        }}
    '''),
    CodeLanguage.RUST: textwrap.dedent('''\
        /// {docstring}
        fn {name}({params}) -> {ret} {{
            {body}
        }}
    '''),
    CodeLanguage.CPP: textwrap.dedent('''\
        /**
         * {docstring}
         */
        {ret} {name}({params}) {{
            {body}
        }}
    '''),
    CodeLanguage.C: textwrap.dedent('''\
        /**
         * {docstring}
         */
        {ret} {name}({params}) {{
            {body}
        }}
    '''),
    CodeLanguage.CSHARP: textwrap.dedent('''\
        /// <summary>{docstring}</summary>
        public static {ret} {name}({params})
        {{
            {body}
        }}
    '''),
    CodeLanguage.RUBY: textwrap.dedent('''\
        # {docstring}
        def {name}({params})
            {body}
        end
    '''),
    CodeLanguage.PHP: textwrap.dedent('''\
        /**
         * {docstring}
         */
        function {name}({params}): {ret} {{
            {body}
        }}
    '''),
    CodeLanguage.SWIFT: textwrap.dedent('''\
        /// {docstring}
        func {name}({params}) -> {ret} {{
            {body}
        }}
    '''),
    CodeLanguage.KOTLIN: textwrap.dedent('''\
        /**
         * {docstring}
         */
        fun {name}({params}): {ret} {{
            {body}
        }}
    '''),
    CodeLanguage.SQL: "-- {name}: {docstring}\n-- TODO: implement SQL logic",
}

_CLASS_TEMPLATES: dict[CodeLanguage, str] = {
    CodeLanguage.PYTHON: textwrap.dedent('''\
        class {name}:
            """{docstring}"""

            def __init__(self{params}):
                {init_body}

            {methods}
    '''),
    CodeLanguage.JAVASCRIPT: textwrap.dedent('''\
        /**
         * {docstring}
         */
        class {name} {{
            constructor({params}) {{
                {init_body}
            }}

            {methods}
        }}
    '''),
    CodeLanguage.TYPESCRIPT: textwrap.dedent('''\
        /**
         * {docstring}
         */
        class {name} {{
            constructor({params}) {{
                {init_body}
            }}

            {methods}
        }}
    '''),
    CodeLanguage.JAVA: textwrap.dedent('''\
        /**
         * {docstring}
         */
        public class {name} {{

            public {name}({params}) {{
                {init_body}
            }}

            {methods}
        }}
    '''),
    CodeLanguage.GO: textwrap.dedent('''\
        // {docstring}
        type {name} struct {{
            // TODO: define fields
        }}

        func New{name}({params}) *{name} {{
            {init_body}
            return &{name}{{}}
        }}

        {methods}
    '''),
    CodeLanguage.RUST: textwrap.dedent('''\
        /// {docstring}
        pub struct {name} {{
            // TODO: define fields
        }}

        impl {name} {{
            pub fn new({params}) -> Self {{
                {init_body}
                Self {{}}
            }}

            {methods}
        }}
    '''),
    CodeLanguage.CPP: textwrap.dedent('''\
        /**
         * {docstring}
         */
        class {name} {{
        public:
            {name}({params}) {{
                {init_body}
            }}

            {methods}
        }};
    '''),
    CodeLanguage.CSHARP: textwrap.dedent('''\
        /// <summary>{docstring}</summary>
        public class {name}
        {{
            public {name}({params})
            {{
                {init_body}
            }}

            {methods}
        }}
    '''),
}

_API_TEMPLATES: dict[str, dict[str, str]] = {
    "fastapi": textwrap.dedent('''\
        from fastapi import APIRouter
        from pydantic import BaseModel

        router = APIRouter(prefix="{endpoint}", tags=["{endpoint_name}"])


        class {endpoint_name}Request(BaseModel):
            # TODO: define request fields
            pass


        class {endpoint_name}Response(BaseModel):
            # TODO: define response fields
            message: str


        @{method_lower}("{endpoint}")
        async def {func_name}(request: {endpoint_name}Request) -> {endpoint_name}Response:
            """{description}"""
            # TODO: implement logic
            return {endpoint_name}Response(message="success")
    '''),
    "flask": textwrap.dedent('''\
        from flask import Blueprint, request, jsonify

        bp = Blueprint("{endpoint_name}", __name__)


        @bp.route("{endpoint}", methods=["{method_upper}"])
        def {func_name}():
            """{description}"""
            data = request.get_json() or {{}}
            # TODO: implement logic
            return jsonify(message="success")
    '''),
    "express": textwrap.dedent('''\
        const express = require('express');
        const router = express.Router();

        router.{method_lower}('{endpoint}', (req, res) => {{
            // {description}
            // TODO: implement logic
            res.json({{ message: 'success' }});
        }});

        module.exports = router;
    '''),
    "django": textwrap.dedent('''\
        from django.http import JsonResponse
        from django.views.decorators.http import require_http_methods

        @require_http_methods(["{method_upper}"])
        def {func_name}(request):
            """{description}"""
            # TODO: implement logic
            return JsonResponse({{"message": "success"}})
    '''),
    "nextjs": textwrap.dedent('''\
        export default function handler(req, res) {{
            if (req.method !== '{method_upper}') {{
                return res.status(405).json({{{{} error: 'Method not allowed' }}}});
            }}

            // {description}
            // TODO: implement logic
            res.status(200).json({{{{ message: 'success' }}}}});
        }}
    '''),
}

_TEST_TEMPLATES: dict[CodeLanguage, str] = {
    CodeLanguage.PYTHON: textwrap.dedent('''\
        import unittest
        {imports}

        class TestGenerated(unittest.TestCase):
            """Test cases auto-generated for the provided code."""

            def test_function_exists(self):
                """Verify the main entry points are callable."""
                # TODO: add real assertions
                self.assertTrue(True)

            def test_edge_cases(self):
                """Edge-case coverage."""
                # TODO: test boundary conditions
                pass

            def test_error_handling(self):
                """Ensure errors are handled gracefully."""
                # TODO: test exception paths
                pass


        if __name__ == "__main__":
            unittest.main()
    '''),
    CodeLanguage.JAVASCRIPT: textwrap.dedent('''\
        describe('{suite_name}', () => {{
            test('should perform expected behavior', () => {{
                // TODO: add assertions
                expect(true).toBe(true);
            }});

            test('should handle edge cases', () => {{
                // TODO: edge case assertions
            }});

            test('should handle errors gracefully', () => {{
                // TODO: error assertions
            }});
        }});
    '''),
    CodeLanguage.TYPESCRIPT: textwrap.dedent('''\
        describe('{suite_name}', () => {{
            test('should perform expected behavior', () => {{
                // TODO: add assertions
                expect(true).toBe(true);
            }});

            test('should handle edge cases', () => {{
                // TODO: edge case assertions
            }});
        }});
    '''),
    CodeLanguage.JAVA: textwrap.dedent('''\
        import org.junit.jupiter.api.Test;
        import static org.junit.jupiter.api.Assertions.*;

        class {suite_name}Test {{
            @Test
            void shouldPerformExpectedBehavior() {{
                // TODO: add assertions
                assertTrue(true);
            }}

            @Test
            void shouldHandleEdgeCases() {{
                // TODO: edge case assertions
            }}
        }}
    '''),
    CodeLanguage.GO: textwrap.dedent('''\
        package {pkg}

        import "testing"

        func Test{suite_name}(t *testing.T) {{
            // TODO: add assertions
            t.Log("test passed")
        }}
    '''),
    CodeLanguage.RUST: textwrap.dedent('''\
        #[cfg(test)]
        mod tests {{
            use super::*;

            #[test]
            fn test_basic() {{
                // TODO: add assertions
                assert!(true);
            }}
        }}
    '''),
    CodeLanguage.CPP: textwrap.dedent('''\
        #include <cassert>
        #include <iostream>

        void test_basic() {{
            // TODO: add assertions
            assert(true);
        }}

        int main() {{
            test_basic();
            std::cout << "All tests passed" << std::endl;
            return 0;
        }}
    '''),
    CodeLanguage.RUBY: textwrap.dedent('''\
        RSpec.describe "{suite_name}" do
            it "performs expected behavior" do
                # TODO: add assertions
                expect(true).to be true
            end

            it "handles edge cases" do
                # TODO: edge case assertions
            end
        end
    '''),
    CodeLanguage.PHP: textwrap.dedent('''\
        <?php
        use PHPUnit\\Framework\\TestCase;

        class {suite_name}Test extends TestCase
        {{
            public function testBasicBehavior(): void
            {{
                // TODO: add assertions
                $this->assertTrue(true);
            }}
        }}
    '''),
    CodeLanguage.KOTLIN: textwrap.dedent('''\
        import org.junit.Test
        import kotlin.test.assertTrue

        class {suite_name}Test {{
            @Test
            fun testBasicBehavior() {{
                // TODO: add assertions
                assertTrue(true)
            }}
        }}
    '''),
    CodeLanguage.SWIFT: textwrap.dedent('''\
        import XCTest

        class {suite_name}Tests: XCTestCase {{
            func testBasicBehavior() {{
                // TODO: add assertions
                XCTAssertTrue(true)
            }}
        }}
    '''),
}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _lang_key(lang: CodeLanguage) -> str:
    return lang.value.lower()


def _snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _camel(name: str) -> str:
    """Convert snake_case to CamelCase."""
    parts = [p.capitalize() for p in name.split("_")]
    return "".join(parts)


def _default_return(lang: CodeLanguage) -> str:
    defaults = {
        CodeLanguage.PYTHON: "None",
        CodeLanguage.JAVASCRIPT: "undefined",
        CodeLanguage.TYPESCRIPT: "void",
        CodeLanguage.JAVA: "void",
        CodeLanguage.GO: "error",
        CodeLanguage.RUST: "()",
        CodeLanguage.CPP: "void",
        CodeLanguage.C: "void",
        CodeLanguage.CSHARP: "void",
        CodeLanguage.RUBY: "nil",
        CodeLanguage.PHP: "void",
        CodeLanguage.SWIFT: "Void",
        CodeLanguage.KOTLIN: "Unit",
    }
    return defaults.get(lang, "void")


def _infer_desc_tokens(description: str) -> list[str]:
    """Extract meaningful tokens from a natural-language description."""
    stop = {
        "a", "an", "the", "to", "for", "of", "in", "on", "at", "by",
        "is", "are", "was", "were", "be", "been", "being", "do", "does",
        "and", "or", "but", "not", "with", "that", "this", "it", "as",
    }
    tokens = re.findall(r"[a-zA-Z0-9_]+", description.lower())
    return [t for t in tokens if t not in stop]


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class CodeGenerator:
    """Generate code from natural language descriptions using pattern-based templates."""

    # ------------------------------------------------------------------
    # generate
    # ------------------------------------------------------------------

    def generate(
        self,
        description: str,
        language: str | CodeLanguage = CodeLanguage.PYTHON,
        context: Optional[dict[str, Any]] = None,
    ) -> CodingResult:
        """Generate code from a natural language description."""
        lang = language if isinstance(language, CodeLanguage) else CodeLanguage.from_ext(language)
        ctx = context or {}
        tokens = _infer_desc_tokens(description)
        func_name = "_".join(tokens[:5]) if tokens else "generated_function"

        body_lines: list[str] = []
        body_lines.append(f'# Generated from: "{description}"')
        body_lines.append("")

        # Heuristic: pick a reasonable body based on keywords
        joined = " ".join(tokens)
        if "api" in joined or "endpoint" in joined or "http" in joined:
            body_lines.append("pass  # TODO: implement API endpoint")
        elif "class" in joined or "object" in joined:
            body_lines.append("pass  # TODO: implement class")
        elif "test" in joined:
            body_lines.append("pass  # TODO: implement test")
        elif "read" in joined or "write" in joined or "file" in joined:
            body_lines.append("pass  # TODO: implement file I/O")
        elif "database" in joined or "sql" in joined or "query" in joined:
            body_lines.append("pass  # TODO: implement database logic")
        elif "sort" in joined:
            body_lines.append("pass  # TODO: implement sorting")
        elif "parse" in joined or "json" in joined:
            body_lines.append("pass  # TODO: implement parsing")
        else:
            body_lines.append("pass  # TODO: implement logic")

        code = self.generate_function(
            name=func_name,
            params="",
            return_type=_default_return(lang),
            language=lang,
            body_desc=description,
        )
        code = "\n".join(body_lines) + "\n\n" + code

        return CodingResult(
            success=True,
            task_type=TaskType.GENERATE,
            code=code,
            explanation=f"Generated {lang.value} code for: {description}",
            metadata={"language": lang.value, "description": description},
        )

    # ------------------------------------------------------------------
    # generate_function
    # ------------------------------------------------------------------

    def generate_function(
        self,
        name: str,
        params: str = "",
        return_type: str = "",
        language: str | CodeLanguage = CodeLanguage.PYTHON,
        body_desc: str = "TODO: implement",
    ) -> str:
        """Generate a single function."""
        lang = language if isinstance(language, CodeLanguage) else CodeLanguage.from_ext(language)
        template = _FUNCTION_TEMPLATES.get(lang)
        if not template:
            # Fallback: generic comment
            return f"// function {name} — {body_desc}\n"

        ret = return_type or _default_return(lang)
        body = f"// {body_desc}" if lang in (CodeLanguage.JAVASCRIPT, CodeLanguage.TYPESCRIPT, CodeLanguage.JAVA, CodeLanguage.GO, CodeLanguage.CPP, CodeLanguage.C, CodeLanguage.CSHARP) else f"# {body_desc}"
        docstring = body_desc

        fmt_params = params
        fmt_body = body

        if lang == CodeLanguage.PYTHON:
            fmt_ret = f" -> {ret}" if ret != "None" else ""
            result = template.format(
                name=name, params=fmt_params, ret=fmt_ret,
                docstring=docstring, body=fmt_body,
            )
        elif lang == CodeLanguage.GO:
            result = template.format(
                name=name, params=fmt_params, ret=ret,
                docstring=docstring, body=fmt_body,
            )
        elif lang == CodeLanguage.RUST:
            result = template.format(
                name=name, params=fmt_params, ret=ret,
                docstring=docstring, body=fmt_body,
            )
        elif lang in (CodeLanguage.CSHARP,):
            result = template.format(
                name=name, params=fmt_params, ret=ret,
                docstring=docstring, body=fmt_body,
            )
        else:
            result = template.format(
                name=name, params=fmt_params, ret=ret,
                docstring=docstring, body=fmt_body,
            )

        return result.rstrip() + "\n"

    # ------------------------------------------------------------------
    # generate_class
    # ------------------------------------------------------------------

    def generate_class(
        self,
        name: str,
        methods: list[str] | None = None,
        language: str | CodeLanguage = CodeLanguage.PYTHON,
    ) -> str:
        """Generate a class with optional method stubs."""
        lang = language if isinstance(language, CodeLanguage) else CodeLanguage.from_ext(language)
        template = _CLASS_TEMPLATES.get(lang)
        if not template:
            return f"// class {name} — TODO: implement\n"

        docstring = f"Implementation of {name}."
        params = ""
        init_body = "# TODO: initialize attributes" if lang == CodeLanguage.PYTHON else "// TODO: initialize attributes"
        method_blocks: list[str] = []

        if methods:
            for m in methods:
                method_blocks.append(self.generate_function(
                    name=m, params="", language=lang, body_desc=f"TODO: implement {m}",
                ))
        else:
            # Default stub methods
            for m in ("initialize", "run", "cleanup"):
                method_blocks.append(self.generate_function(
                    name=m, params="", language=lang, body_desc=f"TODO: implement {m}",
                ))

        rendered_methods = "\n".join(method_blocks).strip()
        result = template.format(
            name=name, docstring=docstring, params=params,
            init_body=init_body, methods=rendered_methods,
        )
        return result.rstrip() + "\n"

    # ------------------------------------------------------------------
    # generate_api
    # ------------------------------------------------------------------

    def generate_api(
        self,
        endpoint: str,
        method: str = "GET",
        language: str | CodeLanguage = CodeLanguage.PYTHON,
        framework: str = "fastapi",
    ) -> str:
        """Generate an API endpoint handler."""
        lang = language if isinstance(language, CodeLanguage) else CodeLanguage.from_ext(language)
        fw = framework.lower()

        template = _API_TEMPLATES.get(fw)
        if not template:
            return f"// API endpoint {method} {endpoint} — framework '{framework}' not supported\n"

        endpoint_name = _camel(endpoint.strip("/").replace("/", "_") or "index")
        func_name = _snake(endpoint_name)
        method_upper = method.upper()
        method_lower = method_upper.lower()

        result = template.format(
            endpoint=endpoint, endpoint_name=endpoint_name,
            func_name=func_name, method_upper=method_upper,
            method_lower=method_lower, description=f"{method_upper} {endpoint}",
        )
        return result.rstrip() + "\n"

    # ------------------------------------------------------------------
    # generate_tests
    # ------------------------------------------------------------------

    def generate_tests(
        self,
        code: str,
        language: str | CodeLanguage = CodeLanguage.PYTHON,
    ) -> str:
        """Generate test cases for the provided code."""
        lang = language if isinstance(language, CodeLanguage) else CodeLanguage.from_ext(language)
        template = _TEST_TEMPLATES.get(lang)
        if not template:
            return f"// Tests for {lang.value} — template not available\n"

        # Try to extract function/class names from source
        func_names = re.findall(r"(?:def|function|func|fn|fun)\s+(\w+)", code)
        class_names = re.findall(r"(?:class)\s+(\w+)", code)
        suite_name = _camel(class_names[0]) if class_names else _camel(func_names[0]) if func_names else "Generated"

        imports = ""
        if lang == CodeLanguage.PYTHON:
            # Try to import top-level names
            top_funcs = [f for f in func_names if not f.startswith("_")]
            if top_funcs:
                imports = f"# from module import {', '.join(top_funcs[:3])}"

        result = template.format(suite_name=suite_name, imports=imports, pkg="generated")
        return result.rstrip() + "\n"

    # ------------------------------------------------------------------
    # generate_project
    # ------------------------------------------------------------------

    def generate_project(
        self,
        template: str,
        name: str,
        description: str = "",
    ) -> dict[str, str]:
        """Generate project files from a named template.

        Returns a mapping of relative file paths to file contents.
        """
        tpl = PROJECT_TEMPLATES.get(template.lower())
        if not tpl:
            available = ", ".join(sorted(PROJECT_TEMPLATES.keys()))
            return {"__error__": f"Unknown template '{template}'. Available: {available}"}

        files: dict[str, str] = {}
        for path, content in tpl["files"].items():
            try:
                files[path] = content.format(name=name, description=description)
            except (KeyError, IndexError):
                files[path] = content

        return files
