"""
Coding Agent — Website Builder
==============================
Scaffolds website projects from templates for multiple frontend frameworks and full-stack combos.
"""

from __future__ import annotations

import json
import os
from typing import Any

from jarvis.core.coding.base import CodeLanguage, TaskType


class WebsiteBuilder:
    """Scaffold complete website projects from templates."""

    # ------------------------------------------------------------------
    # Frontend
    # ------------------------------------------------------------------

    def build_frontend(
        self,
        name: str,
        framework: str,
        pages: list[dict[str, Any]],
        output_dir: str,
    ) -> dict[str, str]:
        """Build a frontend project.

        Args:
            name: Project name.
            framework: One of React, Vue, Svelte, Next.js, Nuxt, Angular.
            pages: List of page dicts ``[{name, route, title}]``.
            output_dir: Root directory for output.

        Returns:
            Mapping of relative file paths to generated content.
        """
        fw = framework.lower().replace(" ", "").replace(".", "")
        generators = {
            "react": self._gen_react,
            "vue": self._gen_vue,
            "svelte": self._gen_svelte,
            "nextjs": self._gen_nextjs,
            "next": self._gen_nextjs,
            "nuxt": self._gen_nuxt,
            "angular": self._gen_angular,
        }
        gen = generators.get(fw)
        if gen is None:
            raise ValueError(
                f"Unsupported frontend framework '{framework}'. "
                f"Choose from: {', '.join(sorted(generators))}"
            )

        files = gen(name, pages, output_dir)
        files[os.path.join(output_dir, "README.md")] = self._gen_readme(name, framework, "Frontend")
        return files

    # ------------------------------------------------------------------
    # Full-stack
    # ------------------------------------------------------------------

    def build_fullstack(
        self,
        name: str,
        frontend: str,
        backend: str,
        output_dir: str,
    ) -> dict[str, str]:
        """Build a full-stack application with separate frontend and backend dirs."""
        files: dict[str, str] = {}
        fe_dir = os.path.join(output_dir, "frontend")
        be_dir = os.path.join(output_dir, "backend")

        fe_files = self.build_frontend(name, frontend, [{"name": "Home", "route": "/", "title": "Home"}], fe_dir)
        for k, v in fe_files.items():
            files[k] = v

        from jarvis.core.coding.api_builder import APIBuilder
        api = APIBuilder()
        api_files = api.build_rest_api(name, backend, [], [], be_dir)
        for k, v in api_files.items():
            files[k] = v

        files[os.path.join(output_dir, "docker-compose.yml")] = (
            'version: "3.8"\nservices:\n  frontend:\n    build: ./frontend\n'
            '    ports:\n      - "3000:3000"\n  backend:\n    build: ./backend\n'
            '    ports:\n      - "8000:8000"\n'
        )
        files[os.path.join(output_dir, "README.md")] = self._gen_readme(name, f"{frontend} + {backend}", "Full-Stack")
        return files

    # ------------------------------------------------------------------
    # Landing page
    # ------------------------------------------------------------------

    def build_landing_page(self, name: str, sections: list[dict[str, Any]], style: str = "modern") -> dict[str, str]:
        """Generate a landing page with HTML/CSS/JS."""
        color = {"modern": "#0ea5e9", "minimal": "#1a1a1a", "bold": "#e11d48"}.get(style, "#0ea5e9")
        sections_html = ""
        for sec in sections:
            sid = sec.get("id", sec.get("name", "section").lower().replace(" ", "-"))
            title = sec.get("title", sec.get("name", "Section"))
            content = sec.get("content", "Content goes here.")
            sections_html += f'    <section id="{sid}">\n      <h2>{title}</h2>\n      <p>{content}</p>\n    </section>\n'

        files: dict[str, str] = {}
        files[os.path.join("index.html")] = (
            '<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8">\n'
            f'  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n  <title>{name}</title>\n'
            '  <link rel="stylesheet" href="styles.css">\n</head>\n<body>\n'
            f'  <header><h1>{name}</h1><nav>' +
            "".join(f'<a href="#{s.get("id", s.get("name", "").lower().replace(" ", "-"))}">{s.get("title", s.get("name", ""))}</a>' for s in sections) +
            '</nav></header>\n' +
            sections_html +
            '  <footer>&copy; 2026 ' + name + '</footer>\n'
            '  <script src="script.js"></script>\n</body>\n</html>\n'
        )
        files[os.path.join("styles.css")] = (
            "* { margin: 0; padding: 0; box-sizing: border-box; }\n"
            "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #333; }\n"
            f"header {{ background: {color}; color: white; padding: 2rem; text-align: center; }}\n"
            "nav { margin-top: 1rem; display: flex; gap: 1rem; justify-content: center; }\n"
            "nav a { color: rgba(255,255,255,0.9); text-decoration: none; }\n"
            "section { padding: 4rem 2rem; max-width: 800px; margin: 0 auto; }\n"
            "section:nth-child(even) { background: #f8f9fa; }\n"
            "footer { text-align: center; padding: 2rem; background: #1a1a1a; color: white; }\n"
        )
        files[os.path.join("script.js")] = (
            'document.addEventListener("DOMContentLoaded", () => {\n'
            "  // Smooth scroll for anchor links\n"
            '  document.querySelectorAll(\'a[href^="#"]\').forEach(a => {\n'
            "    a.addEventListener('click', e => {\n"
            "      e.preventDefault();\n"
            "      const el = document.querySelector(a.getAttribute('href'));\n"
            "      if (el) el.scrollIntoView({ behavior: 'smooth' });\n"
            "    });\n"
            "  });\n});\n"
        )
        files[os.path.join("package.json")] = json.dumps(
            {"name": name.lower().replace(" ", "-"), "version": "1.0.0", "scripts": {"start": "npx serve ."}}, indent=2
        )
        return files

    # ------------------------------------------------------------------
    # Portfolio
    # ------------------------------------------------------------------

    def build_portfolio(self, name: str, projects: list[dict[str, Any]], style: str = "minimal") -> dict[str, str]:
        """Generate a portfolio website."""
        color = {"minimal": "#111827", "modern": "#6366f1", "bold": "#dc2626"}.get(style, "#111827")
        cards = ""
        for p in projects:
            title = p.get("name", "Project")
            desc = p.get("description", "A project I built.")
            link = p.get("link", "#")
            cards += f'      <div class="card"><h3>{title}</h3><p>{desc}</p><a href="{link}">View</a></div>\n'

        files: dict[str, str] = {}
        files[os.path.join("index.html")] = (
            '<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8">\n'
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f'  <title>{name} — Portfolio</title>\n  <link rel="stylesheet" href="styles.css">\n'
            '</head>\n<body>\n'
            f'  <header><h1>{name}</h1><p>Software Developer</p></header>\n'
            '  <main>\n'
            '    <h2>Projects</h2>\n'
            f'    <div class="grid">\n{cards}    </div>\n'
            '  </main>\n'
            '  <footer>&copy; 2026 ' + name + '</footer>\n'
            '</body>\n</html>\n'
        )
        files[os.path.join("styles.css")] = (
            "* { margin: 0; padding: 0; box-sizing: border-box; }\n"
            "body { font-family: system-ui, sans-serif; color: #333; }\n"
            f"header {{ background: {color}; color: white; padding: 4rem 2rem; text-align: center; }}\n"
            "main { max-width: 900px; margin: 2rem auto; padding: 0 1rem; }\n"
            ".grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1.5rem; margin-top: 1rem; }\n"
            ".card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.5rem; }\n"
            ".card h3 { margin-bottom: 0.5rem; }\n"
            ".card a { color: " + color + "; text-decoration: none; }\n"
            "footer { text-align: center; padding: 2rem; background: #f3f4f6; margin-top: 3rem; }\n"
        )
        files[os.path.join("package.json")] = json.dumps(
            {"name": name.lower().replace(" ", "-") + "-portfolio", "version": "1.0.0", "scripts": {"start": "npx serve ."}}, indent=2
        )
        return files

    # ------------------------------------------------------------------
    # Blog with MDX
    # ------------------------------------------------------------------

    def build_blog(self, name: str, framework: str = "next", output_dir: str = ".") -> dict[str, str]:
        """Generate a blog with MDX support."""
        fw = framework.lower()
        files: dict[str, str] = {}

        if fw in ("next", "nextjs"):
            files = self._blog_nextjs(name, output_dir)
        elif fw == "astro":
            files = self._blog_astro(name, output_dir)
        else:
            files = self._blog_nextjs(name, output_dir)

        files[os.path.join(output_dir, "README.md")] = self._gen_readme(name, framework, "Blog")
        return files

    # ------------------------------------------------------------------
    # Component generation
    # ------------------------------------------------------------------

    def generate_component(self, name: str, props: list[dict[str, Any]], framework: str = "react") -> str:
        """Generate a UI component."""
        fw = framework.lower()
        generators = {
            "react": self._component_react,
            "vue": self._component_vue,
            "svelte": self._component_svelte,
            "angular": self._component_angular,
        }
        gen = generators.get(fw, self._component_react)
        return gen(name, props)

    # ------------------------------------------------------------------
    # Page generation
    # ------------------------------------------------------------------

    def generate_page(self, name: str, route: str, framework: str = "react") -> str:
        """Generate a page component with routing."""
        fw = framework.lower()
        generators = {
            "react": self._page_react,
            "vue": self._page_vue,
            "svelte": self._page_svelte,
            "angular": self._page_angular,
            "nextjs": self._page_nextjs,
            "next": self._page_nextjs,
        }
        gen = generators.get(fw, self._page_react)
        return gen(name, route)

    # ------------------------------------------------------------------
    # Styles generation
    # ------------------------------------------------------------------

    def generate_styles(self, name: str, framework: str = "tailwind") -> str:
        """Generate CSS / SCSS / Tailwind styles."""
        fw = framework.lower()
        generators = {
            "css": self._styles_css,
            "scss": self._styles_scss,
            "tailwind": self._styles_tailwind,
            "styled-components": self._styles_styled,
            "emotion": self._styles_styled,
        }
        gen = generators.get(fw, self._styles_css)
        return gen(name)

    # ==================================================================
    #  Private helpers — React
    # ==================================================================

    def _gen_react(self, name: str, pages: list[dict[str, Any]], out: str) -> dict[str, str]:
        files: dict[str, str] = {}
        files[os.path.join(out, "public", "index.html")] = (
            '<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8">\n'
            f'  <title>{name}</title>\n</head>\n<body>\n  <div id="root"></div>\n</body>\n</html>\n'
        )
        imports = ""
        route_entries = ""
        for p in pages:
            pname = p["name"]
            imports += f'import {pname}Page from "./pages/{pname}";\n'
            route_entries += '        <Route path="' + p.get("route", "/") + '" element=<' + pname + 'Page />} />\n'
        files[os.path.join(out, "src", "App.tsx")] = (
            'import { BrowserRouter, Routes, Route } from "react-router-dom";\n'
            + imports
            + "\nexport default function App() {\n  return (\n    <BrowserRouter>\n      <Routes>\n"
            + route_entries
            + "      </Routes>\n    </BrowserRouter>\n  );\n}\n"
        )
        files[os.path.join(out, "src", "index.tsx")] = (
            'import React from "react";\nimport ReactDOM from "react-dom/client";\nimport App from "./App";\n\n'
            'ReactDOM.createRoot(document.getElementById("root")!).render(<App />);\n'
        )
        for p in pages:
            files[os.path.join(out, "src", "pages", f'{p["name"]}.tsx')] = (
                f'export default function {p["name"]}Page() {{\n  return <main><h1>{p.get("title", p["name"])}</h1></main>;\n}}\n'
            )
        pkg = {
            "name": name.lower().replace(" ", "-"),
            "version": "1.0.0",
            "private": True,
            "scripts": {"dev": "vite", "build": "vite build", "preview": "vite preview"},
            "dependencies": {"react": "^18.2.0", "react-dom": "^18.2.0", "react-router-dom": "^6.20.0"},
            "devDependencies": {"@types/react": "^18.2.0", "typescript": "^5.3.0", "vite": "^5.0.0", "@vitejs/plugin-react": "^4.2.0"},
        }
        files[os.path.join(out, "package.json")] = json.dumps(pkg, indent=2)
        files[os.path.join(out, "tsconfig.json")] = '{"compilerOptions":{"target":"ES2020","module":"ESNext","jsx":"react-jsx","strict":true}}\n'
        files[os.path.join(out, "vite.config.ts")] = (
            'import { defineConfig } from "vite";\nimport react from "@vitejs/plugin-react";\n\n'
            'export default defineConfig({ plugins: [react()] });\n'
        )
        return files

    # ==================================================================
    #  Private helpers — Vue
    # ==================================================================

    def _gen_vue(self, name: str, pages: list[dict[str, Any]], out: str) -> dict[str, str]:
        files: dict[str, str] = {}
        files[os.path.join(out, "src", "App.vue")] = (
            "<template>\n  <router-view />\n</template>\n\n<script setup lang='ts'>\n</script>\n"
        )
        files[os.path.join(out, "src", "main.ts")] = (
            'import { createApp } from "vue";\nimport App from "./App.vue";\n'
            "import router from './router';\n\ncreateApp(App).use(router).mount('#app');\n"
        )
        routes = ", ".join(
            f"{{ path: '{p.get('route', '/')}', component: () => import('./views/{p['name']}.vue') }}"
            for p in pages
        )
        files[os.path.join(out, "src", "router", "index.ts")] = (
            "import { createRouter, createWebHistory } from 'vue-router';\n\n"
            f"const routes = [{routes}];\n\n"
            "export default createRouter({ history: createWebHistory(), routes });\n"
        )
        for p in pages:
            files[os.path.join(out, "src", "views", f'{p["name"]}.vue')] = (
                f"<template>\n  <main>\n    <h1>{p.get('title', p['name'])}</h1>\n  </main>\n</template>\n"
            )
        pkg = {
            "name": name.lower().replace(" ", "-"),
            "version": "1.0.0",
            "scripts": {"dev": "vite", "build": "vite build"},
            "dependencies": {"vue": "^3.3.0", "vue-router": "^4.2.0"},
            "devDependencies": {"vite": "^5.0.0", "typescript": "^5.3.0", "@vitejs/plugin-vue": "^4.5.0"},
        }
        files[os.path.join(out, "package.json")] = json.dumps(pkg, indent=2)
        files[os.path.join(out, "vite.config.ts")] = (
            "import { defineConfig } from 'vite';\nimport vue from '@vitejs/plugin-vue';\n\n"
            "export default defineConfig({ plugins: [vue()] });\n"
        )
        files[os.path.join(out, "index.html")] = (
            '<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8">\n'
            f'  <title>{name}</title>\n</head>\n<body>\n  <div id="app"></div>\n'
            '  <script type="module" src="/src/main.ts"></script>\n</body>\n</html>\n'
        )
        return files

    # ==================================================================
    #  Private helpers — Svelte
    # ==================================================================

    def _gen_svelte(self, name: str, pages: list[dict[str, Any]], out: str) -> dict[str, str]:
        files: dict[str, str] = {}
        route_entries = ""
        for p in pages:
            rpath = p.get("route", "/")
            pname = p["name"]
            route_entries += '  <Route path="' + rpath + '" component={() => import("./pages/' + pname + '.svelte")} />\n'
        files[os.path.join(out, "src", "App.svelte")] = (
            "<script>\n  import { Router, Route } from 'svelte-routing';\n</script>\n\n"
            "<Router>\n"
            + route_entries
            + "</Router>\n"
        )
        files[os.path.join(out, "src", "main.js")] = (
            "import App from './App.svelte';\n\nconst app = new App({ target: document.getElementById('app') });\nexport default app;\n"
        )
        for p in pages:
            files[os.path.join(out, "src", "pages", f'{p["name"]}.svelte')] = (
                f"<main>\n  <h1>{p.get('title', p['name'])}</h1>\n</main>\n"
            )
        pkg = {
            "name": name.lower().replace(" ", "-"),
            "version": "1.0.0",
            "scripts": {"dev": "vite dev", "build": "vite build"},
            "devDependencies": {"svelte": "^4.2.0", "vite": "^5.0.0", "@sveltejs/vite-plugin-svelte": "^3.0.0"},
            "dependencies": {"svelte-routing": "^2.12.0"},
        }
        files[os.path.join(out, "package.json")] = json.dumps(pkg, indent=2)
        files[os.path.join(out, "svelte.config.js")] = "import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';\nexport default { preprocess: vitePreprocess() };\n"
        files[os.path.join(out, "index.html")] = (
            '<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8">\n'
            f'  <title>{name}</title>\n</head>\n<body>\n  <div id="app"></div>\n'
            '  <script type="module" src="/src/main.js"></script>\n</body>\n</html>\n'
        )
        return files

    # ==================================================================
    #  Private helpers — Next.js
    # ==================================================================

    def _gen_nextjs(self, name: str, pages: list[dict[str, Any]], out: str) -> dict[str, str]:
        files: dict[str, str] = {}
        for p in pages:
            route = p.get("route", "/")
            if route == "/":
                files[os.path.join(out, "src", "app", "page.tsx")] = (
                    f'export default function {p["name"]}Page() {{\n  return <main><h1>{p.get("title", p["name"])}</h1></main>;\n}}\n'
                )
            else:
                slug = route.strip("/").replace("/", "/")
                files[os.path.join(out, "src", "app", slug, "page.tsx")] = (
                    f'export default function {p["name"]}Page() {{\n  return <main><h1>{p.get("title", p["name"])}</h1></main>;\n}}\n'
                )
        files[os.path.join(out, "src", "app", "layout.tsx")] = (
            'export const metadata = { title: "' + name + '" };\n\n'
            "export default function RootLayout({ children }: { children: React.ReactNode }) {\n"
            "  return <html lang=\"en\"><body>{children}</body></html>;\n}\n"
        )
        pkg = {
            "name": name.lower().replace(" ", "-"),
            "version": "1.0.0",
            "scripts": {"dev": "next dev", "build": "next build", "start": "next start"},
            "dependencies": {"next": "^14.0.0", "react": "^18.2.0", "react-dom": "^18.2.0"},
            "devDependencies": {"typescript": "^5.3.0", "@types/react": "^18.2.0"},
        }
        files[os.path.join(out, "package.json")] = json.dumps(pkg, indent=2)
        files[os.path.join(out, "next.config.js")] = "/** @type {import('next').NextConfig} */\nmodule.exports = {};\n"
        files[os.path.join(out, "tsconfig.json")] = '{"compilerOptions":{"target":"es5","lib":["dom","dom.iterable","esnext"],"jsx":"preserve","module":"esnext","moduleResolution":"bundler","strict":true}}\n'
        return files

    # ==================================================================
    #  Private helpers — Nuxt
    # ==================================================================

    def _gen_nuxt(self, name: str, pages: list[dict[str, Any]], out: str) -> dict[str, str]:
        files: dict[str, str] = {}
        files[os.path.join(out, "app.vue")] = "<template>\n  <NuxtPage />\n</template>\n"
        for p in pages:
            route = p.get("route", "/").strip("/")
            dir_path = route if route else "index"
            files[os.path.join(out, "pages", f'{dir_path}.vue')] = (
                f"<template>\n  <main>\n    <h1>{p.get('title', p['name'])}</h1>\n  </main>\n</template>\n"
            )
        pkg = {
            "name": name.lower().replace(" ", "-"),
            "version": "1.0.0",
            "scripts": {"dev": "nuxt dev", "build": "nuxt build", "generate": "nuxt generate"},
            "dependencies": {"nuxt": "^3.8.0"},
        }
        files[os.path.join(out, "package.json")] = json.dumps(pkg, indent=2)
        files[os.path.join(out, "nuxt.config.ts")] = "export default defineNuxtConfig({ devtools: { enabled: true } });\n"
        return files

    # ==================================================================
    #  Private helpers — Angular
    # ==================================================================

    def _gen_angular(self, name: str, pages: list[dict[str, Any]], out: str) -> dict[str, str]:
        files: dict[str, str] = {}
        safe = name.lower().replace(" ", "-")
        files[os.path.join(out, "src", "app", "app.component.ts")] = (
            'import { Component } from "@angular/core";\n\n'
            "@Component({\n  selector: 'app-root',\n  template: '<router-outlet></router-outlet>'\n})\n"
            "export class AppComponent {}\n"
        )
        for p in pages:
            comp = p["name"].lower().replace(" ", "-")
            files[os.path.join(out, "src", "app", f'{comp}', f'{comp}.component.ts')] = (
                f'import {{ Component }} from "@angular/core";\n\n'
                f"@Component({{\n  selector: 'app-{comp}',\n  template: '<main><h1>{p.get('title', p['name'])}</h1></main>'\n}})\n"
                f"export class {p['name'].replace(' ', '')}Component {{}}\n"
            )
        routes = ", ".join(
            f"{{ path: '{p.get('route', '/').strip('/')}', loadComponent: () => import('./{p['name'].lower().replace(' ', '-')}/{p['name'].lower().replace(' ', '-')}.component').then(m => m.{p['name'].replace(' ', '')}Component) }}"
            for p in pages
        )
        files[os.path.join(out, "src", "app", "app.routes.ts")] = (
            "import { Routes } from '@angular/router';\n\nexport const routes: Routes = [\n  " + routes + "\n];\n"
        )
        files[os.path.join(out, "src", "main.ts")] = (
            "import { bootstrapApplication } from '@angular/platform-browser';\n"
            "import { AppComponent } from './app/app.component';\n"
            "import { routes } from './app/app.routes';\n"
            "import { provideRouter } from '@angular/router';\n\n"
            "bootstrapApplication(AppComponent, { providers: [provideRouter(routes)] });\n"
        )
        pkg = {
            "name": safe,
            "version": "1.0.0",
            "scripts": {"ng": "ng", "start": "ng serve", "build": "ng build"},
            "dependencies": {"@angular/core": "^17.0.0", "@angular/router": "^17.0.0", "@angular/platform-browser": "^17.0.0"},
            "devDependencies": {"@angular/cli": "^17.0.0", "typescript": "^5.3.0"},
        }
        files[os.path.join(out, "package.json")] = json.dumps(pkg, indent=2)
        files[os.path.join(out, "angular.json")] = '{"version":1,"projects":{"' + safe + '":{"architect":{"build":{"options":{"outputPath":"dist/' + safe + '","index":"src/index.html","main":"src/main.ts"}}}}}}\n'
        files[os.path.join(out, "tsconfig.json")] = '{"compilerOptions":{"target":"ES2022","module":"ES2022","moduleResolution":"bundler","strict":true}}\n'
        files[os.path.join(out, "src", "index.html")] = f"<!DOCTYPE html>\n<html lang='en'>\n<head><meta charset='UTF-8'><title>{name}</title></head>\n<body><app-root></app-root></body>\n</html>\n"
        return files

    # ==================================================================
    #  Blog — Next.js variant
    # ==================================================================

    def _blog_nextjs(self, name: str, out: str) -> dict[str, str]:
        files: dict[str, str] = {}
        files[os.path.join(out, "content", "hello-world.mdx")] = (
            '---\ntitle: "Hello World"\ndate: "2026-01-01"\ndescription: "First post"\n---\n\n# Hello World\n\nWelcome to my blog.\n'
        )
        files[os.path.join(out, "src", "app", "blog", "page.tsx")] = (
            'import fs from "fs";\nimport path from "path";\nimport matter from "gray-matter";\nimport Link from "next/link";\n\n'
            "interface Post { slug: string; title: string; date: string; description: string; }\n\n"
            "export default function BlogPage() {\n"
            '  const dir = path.join(process.cwd(), "content");\n'
            '  const files = fs.readdirSync(dir).filter(f => f.endsWith(".mdx"));\n'
            "  const posts: Post[] = files.map(f => {\n"
            "    const { data } = matter(fs.readFileSync(path.join(dir, f)));\n"
            '    return { slug: f.replace(".mdx", ""), ...data } as Post;\n  });\n\n'
            "  return (\n    <main>\n      <h1>Blog</h1>\n"
            '      {posts.map(p => (\n        <article key={p.slug}>\n'
            '          <Link href={`/blog/${p.slug}`}><h2>{p.title}</h2></Link>\n'
            '          <p>{p.description}</p>\n        </article>\n      ))}\n    </main>\n  );\n}\n'
        )
        files[os.path.join(out, "src", "app", "blog", "[slug]", "page.tsx")] = (
            'import fs from "fs";\nimport path from "path";\nimport matter from "gray-matter";\nimport { MDXRemote } from "next-mdx-remote/rsc";\n\n'
            "interface Params { params: { slug: string } }\n\n"
            "export default function BlogPost({ params }: Params) {\n"
            '  const file = path.join(process.cwd(), "content", params.slug + ".mdx");\n'
            "  const { content, data } = matter(fs.readFileSync(file, 'utf-8'));\n\n"
            "  return (\n    <main>\n      <h1>{data.title}</h1>\n      <p>{data.date}</p>\n      <MDXRemote source={content} />\n    </main>\n  );\n}\n"
        )
        pkg = {
            "name": name.lower().replace(" ", "-"),
            "version": "1.0.0",
            "scripts": {"dev": "next dev", "build": "next build"},
            "dependencies": {
                "next": "^14.0.0", "react": "^18.2.0", "react-dom": "^18.2.0",
                "gray-matter": "^4.0.3", "next-mdx-remote": "^4.4.0",
            },
            "devDependencies": {"typescript": "^5.3.0"},
        }
        files[os.path.join(out, "package.json")] = json.dumps(pkg, indent=2)
        files[os.path.join(out, "tsconfig.json")] = '{"compilerOptions":{"target":"es5","jsx":"preserve","strict":true}}\n'
        files[os.path.join(out, "src", "app", "layout.tsx")] = (
            'export const metadata = { title: "' + name + ' Blog" };\n\n'
            "export default function RootLayout({ children }: { children: React.ReactNode }) {\n"
            "  return <html lang=\"en\"><body>{children}</body></html>;\n}\n"
        )
        return files

    # ==================================================================
    #  Blog — Astro variant
    # ==================================================================

    def _blog_astro(self, name: str, out: str) -> dict[str, str]:
        files: dict[str, str] = {}
        files[os.path.join(out, "src", "pages", "index.astro")] = (
            '---\nimport Layout from "../layouts/Layout.astro";\n---\n\n<Layout title="' + name + ' Blog">\n  <h1>Blog</h1>\n</Layout>\n'
        )
        files[os.path.join(out, "src", "layouts", "Layout.astro")] = (
            "---\ninterface Props { title: string }\nconst { title } = Astro.props;\n---\n\n"
            "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <title>{title}</title>\n</head>\n<body><slot /></body>\n</html>\n"
        )
        files[os.path.join(out, "src", "content", "config.ts")] = "import { defineCollection } from 'astro:content';\n\nexport const blogCollection = defineCollection({ type: 'content', schema: ({ z }) => ({ title: z.string(), date: z.string() }) });\n"
        pkg = {
            "name": name.lower().replace(" ", "-"),
            "version": "1.0.0",
            "scripts": {"dev": "astro dev", "build": "astro build"},
            "dependencies": {"astro": "^4.0.0"},
        }
        files[os.path.join(out, "package.json")] = json.dumps(pkg, indent=2)
        files[os.path.join(out, "astro.config.mjs")] = "import { defineConfig } from 'astro/config';\nexport default defineConfig({});\n"
        return files

    # ==================================================================
    #  Component generators
    # ==================================================================

    def _component_react(self, name: str, props: list[dict[str, Any]]) -> str:
        interface = "".join(
            f"  {p['name']}: {p.get('type', 'string')};\n" for p in props
        )
        params = ", ".join(f"{p['name']}" for p in props)
        return (
            f"import React from 'react';\n\n"
            f"interface {name}Props {{\n{interface}}}\n\n"
            f"export default function {name}({{ {params} }}: {name}Props) {{\n"
            f"  return (\n    <div>\n      <h2>{name}</h2>\n    </div>\n  );\n}}\n"
        )

    def _component_vue(self, name: str, props: list[dict[str, Any]]) -> str:
        props_def = "".join(f"  {p['name']}: {{ type: String, required: true }},\n" for p in props)
        template_vars = "".join(f"{{{{ {p['name']} }}}}" for p in props)
        return (
            "<template>\n  <div>\n"
            f"    <h2>{name}: {template_vars}</h2>\n"
            "  </div>\n</template>\n\n"
            "<script setup lang='ts'>\n"
            "defineProps<{\n"
            f"{props_def}"
            "}>();\n</script>\n"
        )

    def _component_svelte(self, name: str, props: list[dict[str, Any]]) -> str:
        exports = "".join(f"  export let {p['name']}: string;\n" for p in props)
        return (
            f"<script>\n{exports}</script>\n\n"
            f"<div>\n  <h2>{name}</h2>\n</div>\n"
        )

    def _component_angular(self, name: str, props: list[dict[str, Any]]) -> str:
        inputs = "".join(f"  {p['name']} = '';\n" for p in props)
        return (
            'import { Component, Input } from "@angular/core";\n\n'
            f'@Component({{\n  selector: "app-{name.lower()}",\n'
            f'  template: `<div><h2>{name}</h2></div>`\n}})\n'
            f"export class {name}Component {{\n{inputs}}}\n"
        )

    # ==================================================================
    #  Page generators
    # ==================================================================

    def _page_react(self, name: str, route: str) -> str:
        return (
            f'export default function {name}Page() {{\n  return (\n    <main>\n      <h1>{name}</h1>\n      <p>Route: {route}</p>\n    </main>\n  );\n}}\n'
        )

    def _page_vue(self, name: str, route: str) -> str:
        return (
            f"<template>\n  <main>\n    <h1>{name}</h1>\n    <p>Route: {route}</p>\n  </main>\n</template>\n\n"
            "<script setup lang='ts'>\n</script>\n"
        )

    def _page_svelte(self, name: str, route: str) -> str:
        return (
            f"<main>\n  <h1>{name}</h1>\n  <p>Route: {route}</p>\n</main>\n"
        )

    def _page_angular(self, name: str, route: str) -> str:
        return (
            'import { Component } from "@angular/core";\n\n'
            f'@Component({{\n  selector: "app-{name.lower()}",\n'
            f'  template: `<main><h1>{name}</h1><p>Route: {route}</p></main>`\n}})\n'
            f"export class {name}Component {{}}\n"
        )

    def _page_nextjs(self, name: str, route: str) -> str:
        return (
            f'export default function {name}Page() {{\n  return <main><h1>{name}</h1><p>Route: {route}</p></main>;\n}}\n'
        )

    # ==================================================================
    #  Style generators
    # ==================================================================

    def _styles_css(self, name: str) -> str:
        return (
            f"/* {name} — CSS */\n\n"
            ":root {\n  --primary: #3b82f6;\n  --bg: #ffffff;\n  --text: #1f2937;\n  --radius: 8px;\n}\n\n"
            "* { margin: 0; padding: 0; box-sizing: border-box; }\n"
            "body { font-family: system-ui, sans-serif; color: var(--text); background: var(--bg); line-height: 1.6; }\n"
            "a { color: var(--primary); text-decoration: none; }\n"
            "a:hover { text-decoration: underline; }\n"
            ".container { max-width: 1200px; margin: 0 auto; padding: 0 1rem; }\n"
            "button { background: var(--primary); color: white; border: none; padding: 0.5rem 1rem; border-radius: var(--radius); cursor: pointer; }\n"
        )

    def _styles_scss(self, name: str) -> str:
        return (
            f"// {name} — SCSS\n\n"
            "$primary: #3b82f6;\n$bg: #ffffff;\n$text: #1f2937;\n$radius: 8px;\n\n"
            "* {\n  margin: 0;\n  padding: 0;\n  box-sizing: border-box;\n}\n\n"
            "body {\n  font-family: system-ui, sans-serif;\n  color: $text;\n  background: $bg;\n  line-height: 1.6;\n}\n\n"
            "a {\n  color: $primary;\n  text-decoration: none;\n  &:hover { text-decoration: underline; }\n}\n\n"
            ".container {\n  max-width: 1200px;\n  margin: 0 auto;\n  padding: 0 1rem;\n}\n\n"
            "button {\n  background: $primary;\n  color: white;\n  border: none;\n  padding: 0.5rem 1rem;\n  border-radius: $radius;\n  cursor: pointer;\n}\n"
        )

    def _styles_tailwind(self, name: str) -> str:
        return (
            f"/* {name} — Tailwind (utility classes used in components) */\n\n"
            "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n\n"
            "@layer base {\n"
            "  body { @apply font-sans text-gray-800 bg-white; }\n"
            "  a { @apply text-blue-600 no-underline hover:underline; }\n"
            "}\n\n"
            "@layer components {\n"
            "  .btn { @apply bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition; }\n"
            "  .container { @apply max-w-6xl mx-auto px-4; }\n"
            "}\n"
        )

    def _styles_styled(self, name: str) -> str:
        return (
            f'import styled from "styled-components";\n\n'
            f"export const Container = styled.div`\n  max-width: 1200px;\n  margin: 0 auto;\n  padding: 0 1rem;\n`;\n\n"
            f"export const Button = styled.button`\n  background: #3b82f6;\n  color: white;\n  border: none;\n  padding: 0.5rem 1rem;\n  border-radius: 8px;\n  cursor: pointer;\n  &:hover { background: #2563eb; }\n`;\n\n"
            f"export const Card = styled.div`\n  border: 1px solid #e5e7eb;\n  border-radius: 8px;\n  padding: 1.5rem;\n`;\n"
        )

    # ==================================================================
    #  Shared helpers
    # ==================================================================

    @staticmethod
    def _gen_readme(name: str, framework: str, project_type: str) -> str:
        return (
            f"# {name}\n\nAuto-generated {project_type} project using {framework}.\n\n"
            "## Quick Start\n\n```bash\nnpm install\nnpm run dev\n```\n"
        )
