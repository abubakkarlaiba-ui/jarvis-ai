"""
JARVIS — Just A Rather Very Intelligent System.
================================================
Core application orchestrator that initializes and coordinates all modules.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Any

from jarvis.core.config import JarvisConfig
from jarvis.core.logging import JarvisLogger
from jarvis.core.router import CommandRouter, CommandResult

logger = logging.getLogger(__name__)


class JARVIS:
    """The main JARVIS application.

    Central orchestrator that initializes, connects, and manages
    all subsystem modules.
    """

    _instance: JARVIS | None = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_dir: str = "./data", debug: bool = False):
        if hasattr(self, "_initialized"):
            return

        self.config_dir = Path(config_dir)
        self.debug = debug
        self._running = False
        self._start_time = 0.0
        self._modules: dict[str, Any] = {}
        self._shutdown_hooks: list = []

        # Core systems
        self.config = JarvisConfig(config_dir=str(self.config_dir / "config"))
        self.log = JarvisLogger(
            log_dir=str(self.config_dir / "logs"),
            level="DEBUG" if debug else "INFO",
        )
        self.router = CommandRouter()

        self._initialized = True

    # ── Module registration ───────────────────────────────────────

    def register_module(self, name: str, module: Any) -> None:
        """Register a subsystem module."""
        self._modules[name] = module
        logger.info("Registered module: %s", name)

    def get_module(self, name: str) -> Any | None:
        return self._modules.get(name)

    # ── Startup ───────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Initialize all subsystems in dependency order."""
        self._start_time = time.time()
        self.log.setup()
        self.config.load()

        logger.info("=" * 60)
        logger.info("J.A.R.V.I.S. — Just A Rather Very Intelligent System")
        logger.info("Version: 2.0.0")
        logger.info("Debug: %s", self.debug)
        logger.info("=" * 60)

        # Phase 1: Core systems
        await self._init_core()

        # Phase 2: Security
        await self._init_security()

        # Phase 3: Memory & Storage
        await self._init_memory()

        # Phase 4: AI & Brain
        await self._init_brain()

        # Phase 5: Voice & Vision
        await self._init_senses()

        # Phase 6: Skills & Automation
        await self._init_skills()

        # Phase 7: Workflow & Coding
        await self._init_workflows()

        # Phase 8: Performance & Monitoring
        await self._init_performance()

        # Phase 9: API Server
        await self._init_api()

        # Register command handlers
        self._register_commands()

        # Set up signal handlers
        self._setup_signals()

        startup_time = time.time() - self._start_time
        logger.info("Startup complete in %.2fs", startup_time)
        logger.info("Modules loaded: %d", len(self._modules))

        self._running = True

    async def _init_core(self) -> None:
        logger.info("Phase 1: Initializing core systems...")
        # Lazy loader, platform compat
        try:
            from jarvis.core.performance import LazyLoader, PlatformCompat
            self.register_module("platform", PlatformCompat())
            self.register_module("lazy_loader", LazyLoader())
        except Exception as e:
            logger.warning("Core init partial: %s", e)

    async def _init_security(self) -> None:
        logger.info("Phase 2: Initializing security...")
        try:
            from jarvis.core.security import SecurityManager
            security = SecurityManager(data_dir=str(self.config_dir / "security"))
            await security.initialize()
            self.register_module("security", security)
        except Exception as e:
            logger.warning("Security init partial: %s", e)

    async def _init_memory(self) -> None:
        logger.info("Phase 3: Initializing memory...")
        try:
            from jarvis.core.memory import MemorySystem
            memory = MemorySystem(data_dir=str(self.config_dir / "memory"))
            self.register_module("memory", memory)
        except Exception as e:
            logger.warning("Memory init partial: %s", e)

    async def _init_brain(self) -> None:
        logger.info("Phase 4: Initializing brain...")
        try:
            from jarvis.core.brain import BrainEngine
            brain = BrainEngine(config=self.config)
            self.register_module("brain", brain)
        except Exception as e:
            logger.warning("Brain init partial: %s", e)

    async def _init_senses(self) -> None:
        logger.info("Phase 5: Initializing senses...")
        try:
            from jarvis.core.vision import VisionSystem
            vision = VisionSystem(data_dir=str(self.config_dir / "vision"))
            self.register_module("vision", vision)
        except Exception as e:
            logger.warning("Vision init partial: %s", e)
        try:
            from jarvis.core.voice import VoicePipeline
            voice = VoicePipeline(config=self.config)
            self.register_module("voice", voice)
        except Exception as e:
            logger.warning("Voice init partial: %s", e)

    async def _init_skills(self) -> None:
        logger.info("Phase 6: Initializing skills...")
        try:
            from jarvis.core.skills import SkillManager, SkillRegistry
            registry = SkillRegistry()
            manager = SkillManager(
                registry=registry,
                plugins_dir=str(self.config_dir.parent / "plugins"),
                manifest_path=str(self.config_dir / "skills" / "manifest.json"),
            )
            await manager.discover_skills()
            self.register_module("skills", manager)
            self.register_module("skill_registry", registry)
        except Exception as e:
            logger.warning("Skills init partial: %s", e)

    async def _init_workflows(self) -> None:
        logger.info("Phase 7: Initializing workflows...")
        try:
            from jarvis.core.workflow import WorkflowEngine
            engine = WorkflowEngine(store_dir=str(self.config_dir / "workflows"))
            self.register_module("workflow", engine)
        except Exception as e:
            logger.warning("Workflow init partial: %s", e)
        try:
            from jarvis.core.coding import CodingAgent
            agent = CodingAgent(working_directory=str(self.config_dir.parent))
            self.register_module("coding", agent)
        except Exception as e:
            logger.warning("Coding init partial: %s", e)

    async def _init_performance(self) -> None:
        logger.info("Phase 8: Initializing performance...")
        try:
            from jarvis.core.performance import PerformanceManager
            perf = PerformanceManager(data_dir=str(self.config_dir / "performance"))
            await perf.initialize()
            self.register_module("performance", perf)
        except Exception as e:
            logger.warning("Performance init partial: %s", e)

    async def _init_api(self) -> None:
        logger.info("Phase 9: Initializing API...")
        try:
            from jarvis.api.app import create_app
            self._app = create_app(jarvis=self)
            self.register_module("api", self._app)
        except Exception as e:
            logger.warning("API init partial: %s", e)

    # ── Command registration ──────────────────────────────────────

    def _register_commands(self) -> None:
        """Register all command handlers with the router."""
        self.router.register("chat", "message", self._handle_chat)
        self.router.register("help", "general", self._handle_help)
        self.router.register("system", "status", self._handle_system_status)
        self.router.register("system", "info", self._handle_system_info)
        self.router.register_fallback(self._handle_chat)

        # Register module-specific handlers
        if "skills" in self._modules:
            self.router.register("skill", "execute", self._handle_skill_execute)
            self.router.register("skill", "list", self._handle_skill_list)
        if "memory" in self._modules:
            self.router.register("memory", "search", self._handle_memory_search)
            self.router.register("memory", "store", self._handle_memory_store)
        if "workflow" in self._modules:
            self.router.register("workflow", "execute", self._handle_workflow_execute)
            self.router.register("workflow", "create", self._handle_workflow_create)
        if "coding" in self._modules:
            self.router.register("coding", "generate", self._handle_coding_generate)
            self.router.register("coding", "explain", self._handle_coding_explain)
        if "security" in self._modules:
            self.router.register("security", "login", self._handle_login)
            self.router.register("security", "logout", self._handle_logout)
        if "performance" in self._modules:
            self.router.register("performance", "report", self._handle_perf_report)

    # ── Command handlers ──────────────────────────────────────────

    async def _handle_chat(self, command, context=None) -> CommandResult:
        brain = self.get_module("brain")
        if brain:
            response = await brain.process(command.raw)
            return CommandResult(output=response, module="chat")
        return CommandResult(output="I'm here, but my brain is offline.", module="chat")

    async def _handle_help(self, command, context=None) -> CommandResult:
        help_text = """
**J.A.R.V.I.S. — Available Commands:**

**Chat:**
  hello, hi, how are you — Chat with JARVIS
  What can you do? — List capabilities

**Skills:**
  run <skill> — Execute a skill
  list skills — Show all available skills
  install skill — Install a new skill

**Memory:**
  remember <info> — Store information
  search <query> — Search memory
  forget <item> — Remove from memory

**Workflow:**
  create task — Create a workflow
  run task — Execute a workflow
  check status — Check workflow status

**Coding:**
  generate code — Generate code
  explain code — Explain code
  run tests — Run tests
  git status — Git operations

**System:**
  system status — System health
  system info — System information
  performance report — Performance stats

**Security:**
  login — Authenticate
  logout — Sign out

**Other:**
  help — Show this help
"""
        return CommandResult(output=help_text.strip(), module="help")

    async def _handle_system_status(self, command, context=None) -> CommandResult:
        perf = self.get_module("performance")
        if perf:
            health = perf.get_health()
            return CommandResult(output=health, module="system")
        return CommandResult(output={"status": "partial", "modules": list(self._modules.keys())})

    async def _handle_system_info(self, command, context=None) -> CommandResult:
        platform = self.get_module("platform")
        if platform:
            info = platform.get_platform_info()
            return CommandResult(output=info, module="system")
        return CommandResult(output={"modules": list(self._modules.keys())})

    async def _handle_skill_execute(self, command, context=None) -> CommandResult:
        skills = self.get_module("skills")
        skill_name = command.parameters.get("target", "")
        if skills and skill_name:
            from jarvis.core.skills import SkillContext
            ctx = SkillContext(user_input=command.raw)
            result = await skills.registry.execute(skill_name, ctx)
            return CommandResult(
                output=result.output if result.success else result.error,
                success=result.success,
                module="skill",
            )
        return CommandResult(output="Skill not found", success=False, module="skill")

    async def _handle_skill_list(self, command, context=None) -> CommandResult:
        skills = self.get_module("skills")
        if skills:
            return CommandResult(output=skills.list_skills(), module="skill")
        return CommandResult(output=[], module="skill")

    async def _handle_memory_search(self, command, context=None) -> CommandResult:
        memory = self.get_module("memory")
        if memory:
            results = memory.search(command.parameters.get("target", command.raw))
            return CommandResult(output=results, module="memory")
        return CommandResult(output="Memory offline", module="memory")

    async def _handle_memory_store(self, command, context=None) -> CommandResult:
        memory = self.get_module("memory")
        if memory:
            memory.store(command.raw)
            return CommandResult(output="Stored.", module="memory")
        return CommandResult(output="Memory offline", module="memory")

    async def _handle_workflow_execute(self, command, context=None) -> CommandResult:
        workflow = self.get_module("workflow")
        if workflow:
            plan = await workflow.plan_from_goal(command.raw)
            result = await workflow.execute_plan(plan)
            return CommandResult(output={"workflow_id": result.id, "status": result.status.name}, module="workflow")
        return CommandResult(output="Workflow engine offline", module="workflow")

    async def _handle_workflow_create(self, command, context=None) -> CommandResult:
        workflow = self.get_module("workflow")
        if workflow:
            plan = await workflow.plan_from_goal(command.raw)
            return CommandResult(output=plan, module="workflow")
        return CommandResult(output="Workflow engine offline", module="workflow")

    async def _handle_coding_generate(self, command, context=None) -> CommandResult:
        coding = self.get_module("coding")
        if coding:
            result = await coding.generate_code(command.raw)
            return CommandResult(output=result.code or result.output, module="coding")
        return CommandResult(output="Coding agent offline", module="coding")

    async def _handle_coding_explain(self, command, context=None) -> CommandResult:
        coding = self.get_module("coding")
        if coding:
            result = await coding.explain_code(command.raw)
            return CommandResult(output=result.explanation or result.output, module="coding")
        return CommandResult(output="Coding agent offline", module="coding")

    async def _handle_login(self, command, context=None) -> CommandResult:
        security = self.get_module("security")
        if security:
            return CommandResult(
                output="Login requires username and password via API",
                module="security",
            )
        return CommandResult(output="Security offline", module="security")

    async def _handle_logout(self, command, context=None) -> CommandResult:
        return CommandResult(output="Logged out.", module="security")

    async def _handle_perf_report(self, command, context=None) -> CommandResult:
        perf = self.get_module("performance")
        if perf:
            return CommandResult(output=perf.get_performance_report(), module="performance")
        return CommandResult(output="Performance module offline", module="performance")

    # ── Public API ────────────────────────────────────────────────

    async def process(self, user_input: str, context: dict | None = None) -> CommandResult:
        """Process a user command end-to-end."""
        return await self.router.route(user_input, context)

    def get_app(self):
        """Get the FastAPI application."""
        return self._modules.get("api")

    # ── Signals & Shutdown ────────────────────────────────────────

    def _setup_signals(self) -> None:
        if sys.platform != "win32":
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

    async def shutdown(self) -> None:
        """Graceful shutdown of all modules."""
        if not self._running:
            return
        self._running = False
        logger.info("Shutting down JARVIS...")

        for hook in self._shutdown_hooks:
            try:
                await hook()
            except Exception as e:
                logger.error("Shutdown hook error: %s", e)

        for name, module in reversed(list(self._modules.items())):
            if hasattr(module, "shutdown"):
                try:
                    await module.shutdown()
                    logger.info("Shut down: %s", name)
                except Exception as e:
                    logger.error("Error shutting down %s: %s", name, e)

        logger.info("JARVIS shutdown complete")

    def add_shutdown_hook(self, hook) -> None:
        self._shutdown_hooks.append(hook)

    @property
    def uptime(self) -> float:
        return time.time() - self._start_time if self._start_time else 0

    @property
    def status(self) -> dict:
        return {
            "running": self._running,
            "uptime": self.uptime,
            "modules": list(self._modules.keys()),
            "debug": self.debug,
        }


# Global instance
def get_jarvis() -> JARVIS:
    return JARVIS._instance or JARVIS()
