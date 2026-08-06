"""
Coding Agent — API Builder
==========================
Scaffolds REST and GraphQL APIs from templates for multiple frameworks and languages.
"""

from __future__ import annotations

import json
import os
from typing import Any

from jarvis.core.coding.base import CodeLanguage, TaskType


class APIBuilder:
    """Scaffold complete REST and GraphQL API projects from templates."""

    # ------------------------------------------------------------------
    # REST API
    # ------------------------------------------------------------------

    def build_rest_api(
        self,
        name: str,
        framework: str,
        models: list[dict[str, Any]],
        endpoints: list[dict[str, Any]],
        output_dir: str,
    ) -> dict[str, str]:
        """Build a complete REST API project.

        Args:
            name: Project / module name.
            framework: One of FastAPI, Flask, Express, DjangoREST, GoFiber, Gin.
            models: List of model dicts ``[{name, fields: [{name, type, required}]}]``.
            endpoints: List of endpoint dicts ``[{method, path, model, action}]``.
            output_dir: Root directory to write files into.

        Returns:
            Mapping of relative file paths to their generated content.
        """
        framework = framework.lower().replace(" ", "")
        files: dict[str, str] = {}

        generators = {
            "fastapi": self._gen_fastapi,
            "flask": self._gen_flask,
            "express": self._gen_express,
            "djangorest": self._gen_django_rest,
            "gofiber": self._gen_go_fiber,
            "fiber": self._gen_go_fiber,
            "gin": self._gen_gin,
        }
        gen = generators.get(framework)
        if gen is None:
            raise ValueError(
                f"Unsupported REST framework '{framework}'. "
                f"Choose from: {', '.join(sorted(generators))}"
            )

        files = gen(name, models, endpoints, output_dir)

        files[os.path.join(output_dir, "README.md")] = self._gen_readme(
            name, framework, "REST"
        )
        files[os.path.join(output_dir, ".gitignore")] = self._gen_gitignore(framework)

        return files

    # ------------------------------------------------------------------
    # GraphQL API
    # ------------------------------------------------------------------

    def build_graphql_api(
        self,
        name: str,
        framework: str,
        schema: dict[str, Any],
        output_dir: str,
    ) -> dict[str, str]:
        """Build a GraphQL API project.

        Args:
            name: Project name.
            framework: One of Strawberry, Ariadne, Hasura.
            schema: ``{types: [{name, fields: [...]}], queries: [...], mutations: [...]}``
            output_dir: Root directory for output.

        Returns:
            Mapping of relative file paths to generated content.
        """
        framework = framework.lower().replace(" ", "")
        generators = {
            "strawberry": self._gen_strawberry,
            "ariadne": self._gen_ariadne,
            "hasura": self._gen_hasura,
        }
        gen = generators.get(framework)
        if gen is None:
            raise ValueError(
                f"Unsupported GraphQL framework '{framework}'. "
                f"Choose from: {', '.join(sorted(generators))}"
            )

        files = gen(name, schema, output_dir)
        files[os.path.join(output_dir, "README.md")] = self._gen_readme(
            name, framework, "GraphQL"
        )
        files[os.path.join(output_dir, ".gitignore")] = self._gen_gitignore("python")
        return files

    # ------------------------------------------------------------------
    # Model generation
    # ------------------------------------------------------------------

    def generate_model(self, name: str, fields: list[dict[str, Any]], language: str = "python") -> str:
        """Generate a data model with validation."""
        lang = CodeLanguage(language) if language in [e.value for e in CodeLanguage] else CodeLanguage.PYTHON
        generators = {
            CodeLanguage.PYTHON: self._model_python,
            CodeLanguage.TYPESCRIPT: self._model_typescript,
            CodeLanguage.JAVASCRIPT: self._model_javascript,
            CodeLanguage.GO: self._model_go,
            CodeLanguage.JAVA: self._model_java,
            CodeLanguage.RUST: self._model_rust,
            CodeLanguage.CSHARP: self._model_csharp,
        }
        gen = generators.get(lang, self._model_python)
        return gen(name, fields)

    # ------------------------------------------------------------------
    # CRUD generation
    # ------------------------------------------------------------------

    def generate_crud(self, model_name: str, fields: list[dict[str, Any]], language: str = "python") -> str:
        """Generate CRUD operations."""
        lang = CodeLanguage(language) if language in [e.value for e in CodeLanguage] else CodeLanguage.PYTHON
        generators = {
            CodeLanguage.PYTHON: self._crud_python,
            CodeLanguage.TYPESCRIPT: self._crud_typescript,
            CodeLanguage.GO: self._crud_go,
            CodeLanguage.JAVA: self._crud_java,
        }
        gen = generators.get(lang, self._crud_python)
        return gen(model_name, fields)

    # ------------------------------------------------------------------
    # Middleware generation
    # ------------------------------------------------------------------

    def generate_middleware(self, name: str, language: str = "python") -> str:
        """Generate auth / logging middleware."""
        lang = CodeLanguage(language) if language in [e.value for e in CodeLanguage] else CodeLanguage.PYTHON
        generators = {
            CodeLanguage.PYTHON: self._middleware_python,
            CodeLanguage.TYPESCRIPT: self._middleware_typescript,
            CodeLanguage.GO: self._middleware_go,
            CodeLanguage.JAVA: self._middleware_java,
        }
        gen = generators.get(lang, self._middleware_python)
        return gen(name)

    # ------------------------------------------------------------------
    # OpenAPI / Swagger spec
    # ------------------------------------------------------------------

    def generate_openapi_spec(self, api_name: str, endpoints: list[dict[str, Any]]) -> str:
        """Generate an OpenAPI 3.0 JSON specification."""
        paths: dict[str, Any] = {}
        for ep in endpoints:
            method = ep.get("method", "get").lower()
            path = ep.get("path", "/")
            model = ep.get("model", "Resource")
            action = ep.get("action", "list")
            operation: dict[str, Any] = {
                "summary": f"{action.title()} {model}",
                "responses": {
                    "200": {"description": "Success", "content": {"application/json": {"schema": {"type": "object"}}}},
                    "404": {"description": "Not found"},
                },
            }
            if method in ("post", "put", "patch"):
                operation["requestBody"] = {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object"}}},
                }
            paths.setdefault(path, {})[method] = operation

        spec = {
            "openapi": "3.0.3",
            "info": {"title": api_name, "version": "1.0.0", "description": f"Auto-generated API spec for {api_name}"},
            "paths": paths,
        }
        return json.dumps(spec, indent=2)

    # ------------------------------------------------------------------
    # Database scaffolding
    # ------------------------------------------------------------------

    def scaffold_database(
        self, name: str, db_type: str, models: list[dict[str, Any]]
    ) -> dict[str, str]:
        """Generate DB setup files for SQLite, PostgreSQL, or MongoDB."""
        db_type = db_type.lower()
        if db_type == "sqlite":
            return self._db_sqlite(name, models)
        elif db_type in ("postgresql", "postgres"):
            return self._db_postgresql(name, models)
        elif db_type == "mongodb":
            return self._db_mongodb(name, models)
        raise ValueError(f"Unsupported database type '{db_type}'. Choose from: sqlite, postgresql, mongodb")

    # ==================================================================
    #  Private helpers – FastAPI
    # ==================================================================

    def _gen_fastapi(self, name: str, models: list[dict[str, Any]], endpoints: list[dict[str, Any]], out: str) -> dict[str, str]:
        files: dict[str, str] = {}

        # main.py
        routes = ""
        for ep in endpoints:
            method = ep.get("method", "get").lower()
            path = ep.get("path", "/")
            model = ep.get("model", "Resource")
            action = ep.get("action", "list")
            func = f"{action}_{model.lower()}"
            routes += f'@app.{method}("{path}", response_model={model}Response)\nasync def {func}():\n    return {{}}\n\n'

        models_code = ""
        for m in models:
            fields_def = ""
            for f in m.get("fields", []):
                ft = f.get("type", "str")
                required = f.get("required", True)
                python_type = {"str": "str", "int": "int", "float": "float", "bool": "bool", "list": "list", "dict": "dict"}.get(ft, "Any")
                fields_def += f"    {f['name']}: {python_type}\n"
            models_code += f"class {m['name']}(BaseModel):\n{fields_def}\n\n"

        files[os.path.join(out, "main.py")] = (
            f'"""Auto-generated FastAPI application — {name}"""\n\n'
            "from fastapi import FastAPI, HTTPException\n"
            "from pydantic import BaseModel\n"
            "from typing import Any, Optional\n\n"
            "app = FastAPI(title=" + json.dumps(name) + ")\n\n"
            f"{models_code}"
            f"{routes}"
            '@app.get("/health")\nasync def health():\n    return {"status": "ok"}\n'
        )

        files[os.path.join(out, "requirements.txt")] = "fastapi>=0.100.0\nuvicorn[standard]>=0.23.0\npydantic>=2.0\n"
        files[os.path.join(out, "pyproject.toml")] = self._gen_pyproject(name, "python")
        files[os.path.join(out, ".env.example")] = "DATABASE_URL=sqlite:///./app.db\nSECRET_KEY=change-me\n"
        files[os.path.join(out, "Dockerfile")] = self._gen_dockerfile("python")
        files[os.path.join(out, "docker-compose.yml")] = self._gen_docker_compose(name, "python")
        return files

    # ==================================================================
    #  Private helpers – Flask
    # ==================================================================

    def _gen_flask(self, name: str, models: list[dict[str, Any]], endpoints: list[dict[str, Any]], out: str) -> dict[str, str]:
        files: dict[str, str] = {}
        routes = ""
        for ep in endpoints:
            method = ep.get("method", "get").lower()
            path = ep.get("path", "/").replace("{", "<").replace("}", ">")
            model = ep.get("model", "Resource")
            action = ep.get("action", "list")
            func = f"{action}_{model.lower()}"
            if method == "get":
                routes += f'@app.route("{path}", methods=["GET"])\ndef {func}():\n    return jsonify({{"items": []}})\n\n'
            else:
                routes += f'@app.route("{path}", methods=["{method.upper()}"])\ndef {func}():\n    return jsonify({{"status": "created"}}), 201\n\n'

        models_code = ""
        for m in models:
            fields_def = ""
            for f in m.get("fields", []):
                fields_def += f"    {f['name']} = db.Column(db.String)\n"
            models_code += f"class {m['name']}(db.Model):\n    id = db.Column(db.Integer, primary_key=True)\n{fields_def}\n\n"

        files[os.path.join(out, "app.py")] = (
            f'"""Auto-generated Flask application — {name}"""\n\n'
            "from flask import Flask, jsonify, request\n\n"
            "app = Flask(__name__)\n\n"
            f"{routes}"
            '@app.route("/health")\ndef health():\n    return jsonify({"status": "ok"})\n\n'
            'if __name__ == "__main__":\n    app.run(debug=True)\n'
        )
        files[os.path.join(out, "requirements.txt")] = "flask>=3.0\nflask-sqlalchemy>=3.1\nflask-marshmallow>=0.15\n"
        files[os.path.join(out, "pyproject.toml")] = self._gen_pyproject(name, "python")
        files[os.path.join(out, ".env.example")] = "DATABASE_URL=sqlite:///./app.db\nSECRET_KEY=change-me\n"
        files[os.path.join(out, "Dockerfile")] = self._gen_dockerfile("python")
        files[os.path.join(out, "docker-compose.yml")] = self._gen_docker_compose(name, "python")
        return files

    # ==================================================================
    #  Private helpers – Express
    # ==================================================================

    def _gen_express(self, name: str, models: list[dict[str, Any]], endpoints: list[dict[str, Any]], out: str) -> dict[str, str]:
        files: dict[str, str] = {}
        routes = ""
        for ep in endpoints:
            method = ep.get("method", "get").lower()
            path = ep.get("path", "/").replace("{", ":").replace("}", "")
            model = ep.get("model", "Resource")
            action = ep.get("action", "list")
            func = f"{action}{model}"
            routes += (
                f"router.{method}('{path}', async (req, res) => {{\n"
                f"  res.json({{ items: [] }});\n}});\n\n"
            )

        files[os.path.join(out, "src", "app.js")] = (
            f'/** Auto-generated Express application — {name} */\n'
            "const express = require('express');\n"
            "const app = express();\n\n"
            "app.use(express.json());\n"
            f"app.use('/api', require('./routes'));\n\n"
            "app.get('/health', (req, res) => res.json({ status: 'ok' }));\n\n"
            "const PORT = process.env.PORT || 3000;\n"
            "app.listen(PORT, () => console.log(`Server running on port ${PORT}`));\n"
        )
        files[os.path.join(out, "src", "routes.js")] = (
            "const router = require('express').Router();\n\n"
            f"{routes}"
            "module.exports = router;\n"
        )

        pkg = {
            "name": name.lower().replace(" ", "-"),
            "version": "1.0.0",
            "main": "src/app.js",
            "scripts": {"start": "node src/app.js", "dev": "nodemon src/app.js"},
            "dependencies": {"express": "^4.18.0"},
            "devDependencies": {"nodemon": "^3.0.0"},
        }
        files[os.path.join(out, "package.json")] = json.dumps(pkg, indent=2)
        files[os.path.join(out, ".env.example")] = "PORT=3000\nDATABASE_URL=mongodb://localhost:27017\n"
        files[os.path.join(out, "Dockerfile")] = self._gen_dockerfile("node")
        files[os.path.join(out, "docker-compose.yml")] = self._gen_docker_compose(name, "node")
        return files

    # ==================================================================
    #  Private helpers – Django REST Framework
    # ==================================================================

    def _gen_django_rest(self, name: str, models: list[dict[str, Any]], endpoints: list[dict[str, Any]], out: str) -> dict[str, str]:
        files: dict[str, str] = {}
        safe = name.lower().replace(" ", "_")
        models_code = ""
        serializers = ""
        viewsets = ""
        for m in models:
            mn = m["name"]
            fields = ", ".join(f['name'] for f in m.get("fields", []))
            model_fields = "\n".join(f"    {f['name']} = models.CharField(max_length=255)" for f in m.get("fields", []))
            models_code += f"class {mn}(models.Model):\n    created_at = models.DateTimeField(auto_now_add=True)\n{model_fields}\n\n    class Meta:\n        app_label = '{safe}'\n\n    def __str__(self):\n        return str(self.id)\n\n"
            serializers += f"class {mn}Serializer(serializers.ModelSerializer):\n    class Meta:\n        model = {mn}\n        fields = '__all__'\n\n"
            viewsets += f"class {mn}ViewSet(viewsets.ModelViewSet):\n    queryset = {mn}.objects.all()\n    serializer_class = {mn}Serializer\n\n"

        files[os.path.join(out, safe, "models.py")] = f'"""Auto-generated models — {name}"""\n\nfrom django.db import models\n\n\n{models_code}'
        files[os.path.join(out, safe, "serializers.py")] = f'"""Auto-generated serializers"""\n\nfrom rest_framework import serializers\nfrom .models import *\n\n\n{serializers}'
        files[os.path.join(out, safe, "views.py")] = f'"""Auto-generated viewsets"""\n\nfrom rest_framework import viewsets\nfrom .serializers import *\nfrom .models import *\n\n\n{viewsets}'
        files[os.path.join(out, safe, "urls.py")] = (
            'from django.urls import path, include\n'
            'from rest_framework.routers import DefaultRouter\n\n'
            'router = DefaultRouter()\n\n'
            + "".join(f"router.register('{m['name'].lower()}s', {m['name']}ViewSet)\n" for m in models)
            + '\nurlpatterns = [\n    path("", include(router.urls)),\n]\n'
        )
        files[os.path.join(out, "manage.py")] = self._django_manage(safe)
        files[os.path.join(out, safe, "settings.py")] = self._django_settings(safe)
        files[os.path.join(out, "requirements.txt")] = "django>=4.2\ndjangorestframework>=3.14\ndjango-cors-headers>=4.0\n"
        files[os.path.join(out, "pyproject.toml")] = self._gen_pyproject(name, "python")
        files[os.path.join(out, "Dockerfile")] = self._gen_dockerfile("python")
        files[os.path.join(out, "docker-compose.yml")] = self._gen_docker_compose(name, "python")
        return files

    # ==================================================================
    #  Private helpers – Go Fiber
    # ==================================================================

    def _gen_go_fiber(self, name: str, models: list[dict[str, Any]], endpoints: list[dict[str, Any]], out: str) -> dict[str, str]:
        files: dict[str, str] = {}
        go_models = ""
        for m in models:
            fields = "\n".join(f'    {f["name"].title()} {self._go_type(f.get("type", "string"))} `json:"{f["name"]}"`' for f in m.get("fields", []))
            go_models += f"type {m['name']} struct {{\n    ID int `json:\"id\"`\n{fields}\n}}\n\n"

        routes = ""
        for ep in endpoints:
            method = ep.get("method", "get").lower()
            path = "/" + ep.get("path", "/").strip("/").replace("{", ":").replace("}", "")
            action = ep.get("action", "list")
            model = ep.get("model", "Resource")
            func = action.title() + model
            if method == "get":
                routes += f'app.Get("{path}", func(c *fiber.Ctx) error {{\n    return c.JSON(fiber.Map{{"items": []}})\n}})\n\n'
            else:
                routes += f'app.{method.title()}("{path}", func(c *fiber.Ctx) error {{\n    return c.JSON(fiber.Map{{"status": "created"}})\n}})\n\n'

        files[os.path.join(out, "main.go")] = (
            f'package main\n\nimport (\n    "github.com/gofiber/fiber/v2"\n)\n\n{go_models}'
            f'func main() {{\n    app := fiber.New()\n\n{routes}'
            '    app.Get("/health", func(c *fiber.Ctx) error {\n        return c.JSON(fiber.Map{"status": "ok"})\n    })\n\n'
            '    app.Listen(":8080")\n}\n'
        )
        mod = f'module {name.lower().replace(" ", "-")}\n\ngo 1.21\n\nrequire github.com/gofiber/fiber/v2 v2.50.0\n'
        files[os.path.join(out, "go.mod")] = mod
        files[os.path.join(out, ".env.example")] = "PORT=8080\nDATABASE_URL=postgres://localhost:5432\n"
        files[os.path.join(out, "Dockerfile")] = self._gen_dockerfile("go")
        files[os.path.join(out, "docker-compose.yml")] = self._gen_docker_compose(name, "go")
        return files

    # ==================================================================
    #  Private helpers – Go Gin
    # ==================================================================

    def _gen_gin(self, name: str, models: list[dict[str, Any]], endpoints: list[dict[str, Any]], out: str) -> dict[str, str]:
        files: dict[str, str] = {}
        go_models = ""
        for m in models:
            fields = "\n".join(f'    {f["name"].title()} {self._go_type(f.get("type", "string"))} `json:"{f["name"]}"`' for f in m.get("fields", []))
            go_models += f"type {m['name']} struct {{\n    ID int `json:\"id\"`\n{fields}\n}}\n\n"

        routes = ""
        for ep in endpoints:
            method = ep.get("method", "get").lower()
            path = "/" + ep.get("path", "/").strip("/").replace("{", ":").replace("}", "")
            action = ep.get("action", "list")
            model = ep.get("model", "Resource")
            func = action.title() + model
            gin_method = method.title()
            routes += f'    r.{gin_method}("{path}", func(c *gin.Context) {{\n        c.JSON(200, gin.H{{"items": []}})\n    }})\n\n'

        files[os.path.join(out, "main.go")] = (
            'package main\n\nimport "github.com/gin-gonic/gin"\n\n'
            + go_models
            + 'func main() {\n    r := gin.Default()\n\n'
            + routes
            + '    r.GET("/health", func(c *gin.Context) {\n        c.JSON(200, gin.H{"status": "ok"})\n    })\n\n'
            '    r.Run(":8080")\n}\n'
        )
        mod = f'module {name.lower().replace(" ", "-")}\n\ngo 1.21\n\nrequire github.com/gin-gonic/gin v1.9.0\n'
        files[os.path.join(out, "go.mod")] = mod
        files[os.path.join(out, ".env.example")] = "PORT=8080\nDATABASE_URL=postgres://localhost:5432\n"
        files[os.path.join(out, "Dockerfile")] = self._gen_dockerfile("go")
        files[os.path.join(out, "docker-compose.yml")] = self._gen_docker_compose(name, "go")
        return files

    # ==================================================================
    #  Private helpers – Strawberry (GraphQL)
    # ==================================================================

    def _gen_strawberry(self, name: str, schema: dict[str, Any], out: str) -> dict[str, str]:
        files: dict[str, str] = {}
        types_code = ""
        for t in schema.get("types", []):
            fields = "\n".join(f'    {f["name"]}: str' for f in t.get("fields", []))
            types_code += f'@strawberry.type\nclass {t["name"]}:\n{fields}\n\n'

        queries = ""
        for q in schema.get("queries", []):
            ret_type = q.get("returnType", "str")
            queries += f'    @strawberry.field\ndef {q["name"]}(self) -> {ret_type}:\n    return "placeholder"\n\n'

        mutations = ""
        for m in schema.get("mutations", []):
            mutations += f'    @strawberry.mutation\ndef {m["name"]}(self, id: int) -> str:\n    return "done"\n\n'

        files[os.path.join(out, "schema.py")] = f'"""Auto-generated Strawberry schema — {name}"""\n\nimport strawberry\n\n\n{types_code}@strawberry.type\nclass Query:\n{queries}\n@strawberry.type\nclass Mutation:\n{mutations}schema = strawberry.Schema(query=Query, mutation=Mutation)\n'
        files[os.path.join(out, "app.py")] = (
            '"""Auto-generated Strawberry ASGI app."""\n'
            'from strawberry.asgi import GraphQL\n'
            'from schema import schema\n'
            'import uvicorn\n'
            'from fastapi import FastAPI\n\n'
            'app = FastAPI(title=' + json.dumps(name) + ')\n'
            'app.add_route("/graphql", GraphQL(schema))\n\n'
            'if __name__ == "__main__":\n    uvicorn.run("app:app", reload=True)\n'
        )
        files[os.path.join(out, "requirements.txt")] = "strawberry-graphql[fastapi]>=0.200\nfastapi>=0.100\nuvicorn>=0.23\n"
        files[os.path.join(out, "pyproject.toml")] = self._gen_pyproject(name, "python")
        return files

    # ==================================================================
    #  Private helpers – Ariadne (GraphQL)
    # ==================================================================

    def _gen_ariadne(self, name: str, schema: dict[str, Any], out: str) -> dict[str, str]:
        files: dict[str, str] = {}
        sdl = 'type Query {\n'
        for q in schema.get("queries", []):
            sdl += f'    {q["name"]}: String!\n'
        sdl += '}\n\n'
        for t in schema.get("types", []):
            sdl += f'type {t["name"]} {{\n'
            for f in t.get("fields", []):
                sdl += f'    {f["name"]}: String!\n'
            sdl += '}\n\n'
        if schema.get("mutations"):
            sdl += 'type Mutation {\n'
            for m in schema["mutations"]:
                sdl += f'    {m["name"]}(id: Int!): String!\n'
            sdl += '}\n'

        files[os.path.join(out, "schema.graphql")] = sdl
        resolvers = 'from ariadne import make_executable_schema, QueryType\n\nquery = QueryType()\n\n'
        for q in schema.get("queries", []):
            resolvers += f'@query.field("{q["name"]}")\ndef resolve_{q["name"]}(_, info):\n    return "placeholder"\n\n'
        files[os.path.join(out, "resolvers.py")] = resolvers
        files[os.path.join(out, "app.py")] = (
            '"""Auto-generated Ariadne app."""\n'
            'from ariadne import graphql_sync, make_executable_schema\n'
            'from flask import Flask, request, jsonify\n'
            'from schema import type_defs\nfrom resolvers import query\n\n'
            'schema = make_executable_schema(type_defs, query)\n'
            'app = Flask(__name__)\n\n'
            '@app.route("/graphql", methods=["POST"])\ndef graphql_server():\n'
            '    data = request.get_json()\n    success, result = graphql_sync(schema, data)\n'
            '    return jsonify(result)\n\n'
            'if __name__ == "__main__":\n    app.run(debug=True)\n'
        )
        files[os.path.join(out, "requirements.txt")] = "ariadne>=0.20\nflask>=3.0\n"
        files[os.path.join(out, "pyproject.toml")] = self._gen_pyproject(name, "python")
        return files

    # ==================================================================
    #  Private helpers – Hasura (GraphQL)
    # ==================================================================

    def _gen_hasura(self, name: str, schema: dict[str, Any], out: str) -> dict[str, str]:
        files: dict[str, str] = {}
        tables_yaml = ""
        for t in schema.get("types", []):
            cols = "\n".join(
                f'            - column:\n                name: {f["name"]}\n                type: text'
                for f in t.get("fields", [])
            )
            tables_yaml += f"- table:\n    schema: public\n    name: {t['name'].lower()}\n  configuration:\n    custom_name: {t['name']}\n    {cols}\n\n" if cols else ""

        files[os.path.join(out, "metadata", "tables.yaml")] = tables_yaml or "# No tables defined\n"
        docker_compose = (
            'version: "3.8"\nservices:\n  graphql-engine:\n    image: hasura/graphql-engine:v2.30.0\n'
            '    ports:\n      - "8080:8080"\n    environment:\n'
            '      HASURA_GRAPHQL_DATABASE_URL: postgres://postgres:password@db:5432/postgres\n'
            '      HASURA_GRAPHQL_ADMIN_SECRET: myadminsecret\n'
            '      HASURA_GRAPHQL_DEV_MODE: "true"\n'
            '    volumes:\n      - ./metadata:/hasura-metadata\n'
            '  db:\n    image: postgres:15\n'
            '    environment:\n      POSTGRES_PASSWORD: password\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n\nvolumes:\n  pgdata:\n'
        )
        files[os.path.join(out, "docker-compose.yml")] = docker_compose
        files[os.path.join(out, "README.md")] = self._gen_readme(name, "Hasura", "GraphQL")
        return files

    # ==================================================================
    #  Model generators per language
    # ==================================================================

    def _model_python(self, name: str, fields: list[dict[str, Any]]) -> str:
        imports = "from pydantic import BaseModel, Field\nfrom typing import Optional\n\n"
        body = f"class {name}(BaseModel):\n"
        for f in fields:
            pt = {"str": "str", "int": "int", "float": "float", "bool": "bool", "list": "list", "dict": "dict"}.get(f.get("type", "str"), "Any")
            default = "" if f.get("required", True) else " = None"
            body += f'    {f["name"]}: {pt}{default} = Field(..., description="{f["name"]}")\n' if f.get("required") else f'    {f["name"]}: Optional[{pt}] = None\n'
        return imports + body

    def _model_typescript(self, name: str, fields: list[dict[str, Any]]) -> str:
        body = f"export interface {name} {{\n"
        for f in fields:
            ts_type = {"str": "string", "int": "number", "float": "number", "bool": "boolean", "list": "unknown[]", "dict": "Record<string, unknown>"}.get(f.get("type", "str"), "unknown")
            optional = "?" if not f.get("required", True) else ""
            body += f"  {f['name']}{optional}: {ts_type};\n"
        body += "}\n"
        return body

    def _model_javascript(self, name: str, fields: list[dict[str, Any]]) -> str:
        body = f"/** @typedef {{Object}} {name} */\n"
        props = ", ".join(f["name"] for f in fields)
        body += f"// @property {{string}} {props}\n"
        body += f"function create{name}(data) {{\n  return {{\n"
        for f in fields:
            body += f'    {f["name"]}: data.{f["name"]},\n'
        body += "  };\n}\n"
        return body

    def _model_go(self, name: str, fields: list[dict[str, Any]]) -> str:
        go_fields = "\n".join(f'    {f["name"].title()} {self._go_type(f.get("type", "string"))} `json:"{f["name"]}"`' for f in fields)
        return f"type {name} struct {{\n    ID int `json:\"id\"`\n{go_fields}\n}}\n"

    def _model_java(self, name: str, fields: list[dict[str, Any]]) -> str:
        body = f"public class {name} {{\n    private Long id;\n"
        getters = ""
        setters = ""
        for f in fields:
            jt = {"str": "String", "int": "int", "float": "double", "bool": "boolean"}.get(f.get("type", "str"), "Object")
            body += f"    private {jt} {f['name']};\n"
            cap = f["name"].title()
            body_type = jt
            getters += f"    public {body_type} get{cap}() {{ return {f['name']}; }}\n"
            setters += f"    public void set{cap}({body_type} {f['name']}) {{ this.{f['name']} = {f['name']}; }}\n"
        body += f"\n{getters}\n{setters}\n}}\n"
        return body

    def _model_rust(self, name: str, fields: list[dict[str, Any]]) -> str:
        body = "#[derive(Debug, Clone, Serialize, Deserialize)]\npub struct " + name + " {\n    pub id: i64,\n"
        for f in fields:
            rt = {"str": "String", "int": "i64", "float": "f64", "bool": "bool"}.get(f.get("type", "str"), "String")
            body += f'    pub {f["name"]}: {rt},\n'
        body += "}\n"
        return body

    def _model_csharp(self, name: str, fields: list[dict[str, Any]]) -> str:
        body = f"public class {name}\n{{\n    public int Id {{ get; set; }}\n"
        for f in fields:
            ct = {"str": "string", "int": "int", "float": "double", "bool": "bool"}.get(f.get("type", "str"), "object")
            body += f'    public {ct} {f["name"].title()} {{ get; set; }}\n'
        body += "}\n"
        return body

    # ==================================================================
    #  CRUD generators per language
    # ==================================================================

    def _crud_python(self, model_name: str, fields: list[dict[str, Any]]) -> str:
        mn = model_name
        return (
            f'"""CRUD operations for {mn}."""\n\n'
            f"from typing import Optional\nfrom sqlalchemy.orm import Session\nfrom .models import {mn}\n\n"
            f"def create_{mn.lower()}(db: Session, data: dict) -> {mn}:\n"
            f"    obj = {mn}(**data)\n    db.add(obj)\n    db.commit()\n    db.refresh(obj)\n    return obj\n\n"
            f"def get_{mn.lower()}(db: Session, id: int) -> Optional[{mn}]:\n"
            f"    return db.query({mn}).filter({mn}.id == id).first()\n\n"
            f"def list_{mn.lower()}s(db: Session, skip: int = 0, limit: int = 100) -> list[{mn}]:\n"
            f"    return db.query({mn}).offset(skip).limit(limit).all()\n\n"
            f"def update_{mn.lower()}(db: Session, id: int, data: dict) -> Optional[{mn}]:\n"
            f"    obj = get_{mn.lower()}(db, id)\n    if obj:\n        for k, v in data.items():\n            setattr(obj, k, v)\n        db.commit()\n        db.refresh(obj)\n    return obj\n\n"
            f"def delete_{mn.lower()}(db: Session, id: int) -> bool:\n"
            f"    obj = get_{mn.lower()}(db, id)\n    if obj:\n        db.delete(obj)\n        db.commit()\n        return True\n    return False\n"
        )

    def _crud_typescript(self, model_name: str, fields: list[dict[str, Any]]) -> str:
        mn = model_name
        return (
            f'/** CRUD operations for {mn} */\n\n'
            f"import {{ {mn} }} from './types';\n\n"
            f"const {mn.lower()}s: {mn}[] = [];\nlet nextId = 1;\n\n"
            f"export function create{mn}(data: Omit<{mn}, 'id'>): {mn} {{\n"
            f"  const item = {{ ...data, id: nextId++ }} as {mn};\n  {mn.lower()}s.push(item);\n  return item;\n}}\n\n"
            f"export function get{mn}(id: number): {mn} | undefined {{\n"
            f"  return {mn.lower()}s.find(i => i.id === id);\n}}\n\n"
            f"export function list{mn}s(skip = 0, limit = 100): {mn}[] {{\n"
            f"  return {mn.lower()}s.slice(skip, skip + limit);\n}}\n\n"
            f"export function update{mn}(id: number, data: Partial<{mn}>): {mn} | undefined {{\n"
            f"  const item = get{mn}(id);\n  if (item) Object.assign(item, data);\n  return item;\n}}\n\n"
            f"export function delete{mn}(id: number): boolean {{\n"
            f"  const idx = {mn.lower()}s.findIndex(i => i.id === id);\n  if (idx >= 0) {{ {mn.lower()}s.splice(idx, 1); return true; }}\n  return false;\n}}\n"
        )

    def _crud_go(self, model_name: str, fields: list[dict[str, Any]]) -> str:
        mn = model_name
        return (
            f"package models\n\n"
            f"var {mn.lower()}s []{mn}\nvar nextID int64 = 1\n\n"
            f"func Create{mn}(data {mn}) {mn} {{\n    data.ID = nextID; nextID++\n"
            f"    {mn.lower()}s = append({mn.lower()}s, data)\n    return data\n}}\n\n"
            f"func Get{mn}(id int64) *{mn} {{\n"
            f"    for i := range {mn.lower()}s {{ if {mn.lower()}s[i].ID == id {{ return &{mn.lower()}s[i] }} }}\n    return nil\n}}\n\n"
            f"func List{mn}s(skip, limit int) []{mn} {{\n"
            f"    end := skip + limit; if end > len({mn.lower()}s) {{ end = len({mn.lower()}s) }}\n"
            f"    return {mn.lower()}s[skip:end]\n}}\n\n"
            f"func Update{mn}(id int64, data {mn}) *{mn} {{\n"
            f"    for i := range {mn.lower()}s {{ if {mn.lower()}s[i].ID == id {{ {mn.lower()}s[i] = data; {mn.lower()}s[i].ID = id; return &{mn.lower()}s[i] }} }}\n    return nil\n}}\n\n"
            f"func Delete{mn}(id int64) bool {{\n"
            f"    for i := range {mn.lower()}s {{ if {mn.lower()}s[i].ID == id {{ {mn.lower()}s = append({mn.lower()}s[:i], {mn.lower()}s[i+1:]...); return true }} }}\n    return false\n}}\n"
        )

    def _crud_java(self, model_name: str, fields: list[dict[str, Any]]) -> str:
        mn = model_name
        return (
            f"import java.util.*;\nimport java.util.concurrent.atomic.AtomicLong;\n\n"
            f"public class {mn}Repository {{\n"
            f"    private final Map<Long, {mn}> store = new HashMap<>();\n"
            f"    private final AtomicLong idGen = new AtomicLong(1);\n\n"
            f"    public {mn} create({mn} entity) {{\n"
            f"        entity.setId(idGen.getAndIncrement());\n"
            f"        store.put(entity.getId(), entity);\n"
            f"        return entity;\n"
            f"    }}\n\n"
            f"    public Optional<{mn}> findById(long id) {{\n"
            f"        return Optional.ofNullable(store.get(id));\n"
            f"    }}\n\n"
            f"    public List<{mn}> findAll(int skip, int limit) {{\n"
            f"        return store.values().stream().skip(skip).limit(limit).toList();\n"
            f"    }}\n\n"
            f"    public Optional<{mn}> update(long id, {mn} entity) {{\n"
            f"        if (store.containsKey(id)) {{ entity.setId(id); store.put(id, entity); return Optional.of(entity); }}\n"
            f"        return Optional.empty();\n"
            f"    }}\n\n"
            f"    public boolean delete(long id) {{\n"
            f"        return store.remove(id) != null;\n"
            f"    }}\n"
            f"}}\n"
        )

    # ==================================================================
    #  Middleware generators per language
    # ==================================================================

    def _middleware_python(self, name: str) -> str:
        return (
            f'"""Auth / Logging middleware — {name}"""\n\n'
            "import time\nimport logging\nfrom typing import Callable\nfrom starlette.middleware.base import BaseHTTPMiddleware\nfrom starlette.requests import Request\nfrom starlette.responses import Response\n\n"
            "logger = logging.getLogger(__name__)\n\n"
            "class AuthMiddleware(BaseHTTPMiddleware):\n"
            '    """Validate Bearer token from Authorization header."""\n\n'
            "    async def dispatch(self, request: Request, call_next: Callable) -> Response:\n"
            '        token = request.headers.get("authorization", "")\n'
            '        if not token.startswith("Bearer "):\n'
            '            return Response("Unauthorized", status_code=401)\n'
            "        request.state.token = token[7:]\n"
            "        return await call_next(request)\n\n\n"
            "class LoggingMiddleware(BaseHTTPMiddleware):\n"
            '    """Log request method, path, and duration."""\n\n'
            "    async def dispatch(self, request: Request, call_next: Callable) -> Response:\n"
            "        start = time.perf_counter()\n"
            "        response = await call_next(request)\n"
            "        duration = (time.perf_counter() - start) * 1000\n"
            '        logger.info("%s %s -> %s (%.1fms)", request.method, request.url.path, response.status_code, duration)\n'
            "        return response\n"
        )

    def _middleware_typescript(self, name: str) -> str:
        return (
            f'/** Auth / Logging middleware — {name} */\n\n'
            "import { Request, Response, NextFunction } from 'express';\n\n"
            "export function authMiddleware(req: Request, res: Response, next: NextFunction): void {\n"
            "  const token = req.headers.authorization ?? '';\n"
            "  if (!token.startsWith('Bearer ')) {\n"
            "    res.status(401).json({ error: 'Unauthorized' });\n"
            "    return;\n"
            "  }\n"
            "  (req as any).token = token.slice(7);\n"
            "  next();\n"
            "}\n\n"
            "export function loggingMiddleware(req: Request, res: Response, next: NextFunction): void {\n"
            "  const start = Date.now();\n"
            "  res.on('finish', () => {\n"
            "    const ms = Date.now() - start;\n"
            "    console.log(`${req.method} ${req.path} -> ${res.statusCode} (${ms}ms)`);\n"
            "  });\n"
            "  next();\n"
            "}\n"
        )

    def _middleware_go(self, name: str) -> str:
        return (
            "package middleware\n\n"
            'import (\n    "log"\n    "net/http"\n    "strings"\n    "time"\n)\n\n'
            "func Auth(next http.Handler) http.Handler {\n"
            '    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {\n'
            '        token := r.Header.Get("Authorization")\n'
            '        if !strings.HasPrefix(token, "Bearer ") {\n'
            '            http.Error(w, "Unauthorized", http.StatusUnauthorized)\n'
            "            return\n"
            "        }\n"
            "        next.ServeHTTP(w, r)\n"
            "    })\n"
            "}\n\n"
            "func Logging(next http.Handler) http.Handler {\n"
            '    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {\n'
            "        start := time.Now()\n"
            "        next.ServeHTTP(w, r)\n"
            '        log.Printf("%s %s (%s)", r.Method, r.URL.Path, time.Since(start))\n'
            "    })\n"
            "}\n"
        )

    def _middleware_java(self, name: str) -> str:
        return (
            f"import jakarta.servlet.http.*;\nimport jakarta.servlet.*;\nimport java.io.IOException;\nimport java.util.logging.Logger;\n\n"
            f"public class AuthFilter implements Filter {{\n"
            f"    private static final Logger LOG = Logger.getLogger(AuthFilter.class.getName());\n\n"
            f"    @Override\n    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain)\n"
            f"            throws IOException, ServletException {{\n"
            f"        HttpServletRequest httpReq = (HttpServletRequest) req;\n"
            f"        String auth = httpReq.getHeader(\"Authorization\");\n"
            f"        if (auth == null || !auth.startsWith(\"Bearer \")) {{\n"
            f"            ((HttpServletResponse) res).setStatus(401);\n"
            f"            return;\n"
            f"        }}\n"
            f"        long start = System.currentTimeMillis();\n"
            f"        chain.doFilter(req, res);\n"
            f"        long ms = System.currentTimeMillis() - start;\n"
            f"        LOG.info(httpReq.getMethod() + \" \" + httpReq.getRequestURI() + \" (\" + ms + \"ms)\");\n"
            f"    }}\n"
            f"}}\n"
        )

    # ==================================================================
    #  Database scaffolding
    # ==================================================================

    def _db_sqlite(self, name: str, models: list[dict[str, Any]]) -> dict[str, str]:
        files: dict[str, str] = {}
        tables = ""
        for m in models:
            cols = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
            for f in m.get("fields", []):
                sql_type = {"str": "TEXT", "int": "INTEGER", "float": "REAL", "bool": "INTEGER"}.get(f.get("type", "str"), "TEXT")
                cols.append(f"{f['name']} {sql_type}")
            tables += f"CREATE TABLE IF NOT EXISTS {m['name'].lower()} (\n    {', '.join(cols)}\n);\n\n"
        files[os.path.join(out, "schema.sql")] = f"-- Auto-generated SQLite schema — {name}\nPRAGMA journal_mode=WAL;\n\n{tables}"
        files[os.path.join(out, "db.py")] = (
            '"""SQLite database helper."""\n\nimport sqlite3\nfrom pathlib import Path\n\n'
            f"DB_PATH = Path('{name.lower()}.db')\n\n"
            "def get_connection():\n    conn = sqlite3.connect(DB_PATH)\n    conn.row_factory = sqlite3.Row\n    return conn\n\n"
            "def init_db():\n    conn = get_connection()\n    with open('schema.sql') as f:\n        conn.executescript(f.read())\n    conn.close()\n"
        )
        files[os.path.join(out, "requirements.txt")] = "sqlalchemy>=2.0\naiosqlite>=0.19\n"
        return files

    def _db_postgresql(self, name: str, models: list[dict[str, Any]]) -> dict[str, str]:
        files: dict[str, str] = {}
        tables = ""
        for m in models:
            cols = ["id SERIAL PRIMARY KEY"]
            for f in m.get("fields", []):
                pg_type = {"str": "VARCHAR(255)", "int": "INTEGER", "float": "DOUBLE PRECISION", "bool": "BOOLEAN"}.get(f.get("type", "str"), "TEXT")
                cols.append(f"{f['name']} {pg_type}")
            tables += f"CREATE TABLE IF NOT EXISTS {m['name'].lower()} (\n    {', '.join(cols)}\n);\n\n"
        files[os.path.join(out, "schema.sql")] = f"-- Auto-generated PostgreSQL schema — {name}\n\n{tables}"
        files[os.path.join(out, "docker-compose.yml")] = (
            'version: "3.8"\nservices:\n  db:\n    image: postgres:15\n'
            '    environment:\n      POSTGRES_DB: ' + name.lower() + '\n      POSTGRES_USER: postgres\n      POSTGRES_PASSWORD: password\n'
            '    ports:\n      - "5432:5432"\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n'
            '      - ./schema.sql:/docker-entrypoint-initdb.d/01-schema.sql\n\nvolumes:\n  pgdata:\n'
        )
        files[os.path.join(out, "requirements.txt")] = "psycopg2-binary>=2.9\nsqlalchemy>=2.0\nasyncpg>=0.28\n"
        return files

    def _db_mongodb(self, name: str, models: list[dict[str, Any]]) -> dict[str, str]:
        files: dict[str, str] = {}
        schemas = ""
        for m in models:
            props = ", ".join(f'        "{f["name"]}": {{"type": "{f.get("type", "string")}"}}' for f in m.get("fields", []))
            schemas += (
                f'db.createCollection("{m["name"].lower()}", {{\n'
                f'    validator: {{ $jsonSchema: {{\n'
                f'        bsonType: "object",\n'
                f'        required: [{" ".join(f["" + f["name"] + ""] for f in m.get("fields", []) if f.get("required"))}],\n'
                f'        properties: {{\n{props}\n        }}\n'
                f'    }} }}\n}});\n\n'
            )
        files[os.path.join(out, "init-mongo.js")] = f'// Auto-generated MongoDB init — {name}\ndb = db.getSiblingDB("{name.lower()}");\n\n{schemas}'
        files[os.path.join(out, "docker-compose.yml")] = (
            'version: "3.8"\nservices:\n  mongo:\n    image: mongo:7\n'
            '    ports:\n      - "27017:27017"\n'
            '    volumes:\n      - mongodata:/data/db\n'
            '      - ./init-mongo.js:/docker-entrypoint-initdb.d/init-mongo.js\n\nvolumes:\n  mongodata:\n'
        )
        files[os.path.join(out, "requirements.txt")] = "motor>=3.3\npymongo>=4.5\n"
        return files

    # ==================================================================
    #  Shared helpers
    # ==================================================================

    @staticmethod
    def _go_type(t: str) -> str:
        return {"str": "string", "int": "int", "float": "float64", "bool": "bool"}.get(t, "interface{}")

    @staticmethod
    def _gen_pyproject(name: str, lang: str) -> str:
        if lang == "python":
            return (
                f'[project]\nname = "{name.lower().replace(" ", "-")}"\nversion = "1.0.0"\n'
                'requires-python = ">=3.10"\n\n'
                '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
            )
        return ""

    @staticmethod
    def _gen_dockerfile(lang: str) -> str:
        dockerfiles = {
            "python": (
                "FROM python:3.11-slim\nWORKDIR /app\n"
                "COPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\n"
                "COPY . .\nEXPOSE 8000\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]\n"
            ),
            "node": (
                "FROM node:20-alpine\nWORKDIR /app\n"
                "COPY package*.json ./\nRUN npm ci\nCOPY . .\nEXPOSE 3000\nCMD [\"node\", \"src/app.js\"]\n"
            ),
            "go": (
                "FROM golang:1.21-alpine AS builder\nWORKDIR /app\n"
                "COPY go.mod go.sum ./\nRUN go mod download\nCOPY . .\nRUN CGO_ENABLED=0 go build -o server .\n\n"
                "FROM alpine:3.18\nCOPY --from=builder /app/server /server\nEXPOSE 8080\nCMD [\"/server\"]\n"
            ),
        }
        return dockerfiles.get(lang, dockerfiles["python"])

    @staticmethod
    def _gen_docker_compose(name: str, lang: str) -> str:
        port = {"python": "8000", "node": "3000", "go": "8080"}.get(lang, "8000")
        cmd = {"python": "uvicorn main:app --reload", "node": "npm run dev", "go": "go run ."}.get(lang, "python main.py")
        return (
            'version: "3.8"\nservices:\n  app:\n    build: .\n    ports:\n'
            f'      - "{port}:{port}"\n    volumes:\n      - .:/app\n    command: {cmd}\n'
        )

    @staticmethod
    def _gen_readme(name: str, framework: str, api_type: str) -> str:
        return (
            f"# {name}\n\nAuto-generated {api_type} API project using {framework}.\n\n"
            "## Quick Start\n\n```bash\n# Install dependencies\n# Start the server\n# Visit /docs (REST) or /graphql (GraphQL)\n```\n"
        )

    @staticmethod
    def _gen_gitignore(framework: str) -> str:
        base = "__pycache__/\n*.pyc\n.env\nnode_modules/\n.DS_Store\n*.db\n"
        if framework == "node":
            base += "dist/\n"
        return base

    @staticmethod
    def _django_manage(safe: str) -> str:
        return (
            '#!/usr/bin/env python\n"""Django management command."""\n'
            "import os, sys\n\n"
            "if __name__ == '__main__':\n"
            "    os.environ.setdefault('DJANGO_SETTINGS_MODULE', '" + safe + ".settings')\n"
            "    from django.core.management import execute_from_command_line\n"
            "    execute_from_command_line(sys.argv)\n"
        )

    @staticmethod
    def _django_settings(safe: str) -> str:
        return (
            f'INSTALLED_APPS = [\n    "django.contrib.admin",\n    "django.contrib.auth",\n'
            f'    "django.contrib.contenttypes",\n    "django.contrib.sessions",\n'
            f'    "rest_framework",\n    "{safe}",\n]\n\n'
            "DATABASES = {\n    'default': {\n        'ENGINE': 'django.db.backends.sqlite3',\n"
            "        'NAME': 'db.sqlite3',\n    }\n}\n"
            "SECRET_KEY = 'change-me'\nDEBUG = True\nALLOWED_HOSTS = ['*']\n"
        )
