"""Executor agent for running browser automation plans."""
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

# Import WebSocket manager (will be None if not available)
try:
    from api.websocket import ws_manager
except ImportError:
    ws_manager = None


class ExecutorAgent:
    """Agent that executes browser automation plans step by step."""

    def __init__(self, page: Page, screenshots_dir: Path):
        """
        Initialize executor agent.

        Args:
            page: Playwright page object
            screenshots_dir: Directory to save screenshots
        """
        self.page = page
        self.screenshots_dir = screenshots_dir
        self.execution_history = []

    async def execute_plan(
        self,
        plan: Dict,
        task_id: int,
        selectors: Dict
    ) -> Dict:
        """
        Execute a complete automation plan.

        Args:
            plan: Execution plan from PlannerAgent
            task_id: Task ID for logging
            selectors: EMR selectors configuration

        Returns:
            Execution results
        """
        logger.info(f"Executing plan {plan['plan_id']} with {plan['total_steps']} steps")

        results = {
            "plan_id": plan["plan_id"],
            "task_id": task_id,
            "start_time": datetime.utcnow().isoformat(),
            "steps_completed": 0,
            "steps_failed": 0,
            "step_results": [],
            "success": False,
            "error": None
        }

        for step in plan["steps"]:
            step_result = await self.execute_step(step, task_id, selectors)
            results["step_results"].append(step_result)
            self.execution_history.append(step_result)

            if step_result["status"] == "success":
                results["steps_completed"] += 1
            else:
                results["steps_failed"] += 1
                # Stop on first failure (planner will adapt and retry)
                results["error"] = step_result.get("error")
                break

        results["success"] = results["steps_failed"] == 0
        results["end_time"] = datetime.utcnow().isoformat()

        return results

    async def execute_step(
        self,
        step: Dict,
        task_id: int,
        selectors: Dict
    ) -> Dict:
        """
        Execute a single automation step.

        Args:
            step: Step definition
            task_id: Task ID
            selectors: EMR selectors

        Returns:
            Step execution result
        """
        action = step["action"]
        step_number = step["step_number"]

        logger.info(f"Executing step {step_number}: {action} - {step['description']}")

        # Send WebSocket update: step started
        if ws_manager:
            total_steps = len(self.execution_history) + 10  # Estimate if not known
            await ws_manager.send_step_started(
                task_id,
                step_number,
                total_steps,
                action,
                step["description"]
            )

        result = {
            "step_number": step_number,
            "action": action,
            "status": "success",
            "error": None,
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            # Execute based on action type
            if action == "navigate":
                await self._execute_navigate(step, selectors)

            elif action == "click":
                await self._execute_click(step, selectors)

            elif action == "fill":
                await self._execute_fill(step, selectors)

            elif action == "select":
                await self._execute_select(step, selectors)

            elif action == "wait":
                await self._execute_wait(step)

            elif action == "screenshot":
                await self._execute_screenshot(step, task_id)

            elif action == "verify":
                await self._execute_verify(step, selectors)

            elif action == "reload":
                await self.page.reload(wait_until="networkidle")

            elif action == "navigate_back":
                await self.page.go_back(wait_until="networkidle")

            else:
                raise ValueError(f"Unknown action type: {action}")

            # Wait after step if specified
            wait_time = step.get("wait_after_ms", 0) / 1000
            if wait_time > 0:
                await asyncio.sleep(wait_time)

            # Take screenshot if requested
            screenshot_url = None
            if step.get("screenshot_after", False):
                screenshot_path = await self._take_screenshot(
                    f"step_{step_number}",
                    task_id
                )
                result["screenshot"] = str(screenshot_path)
                screenshot_url = f"/screenshots/{screenshot_path.name}"

            logger.info(f"Step {step_number} completed successfully")

            # Send WebSocket update: step completed
            if ws_manager:
                await ws_manager.send_step_completed(
                    task_id,
                    step_number,
                    len(self.execution_history) + 1,
                    screenshot_url
                )

        except Exception as e:
            logger.error(f"Step {step_number} failed: {e}", exc_info=True)
            result["status"] = "failed"
            result["error"] = str(e)

            # Capture error screenshot
            error_screenshot_url = None
            try:
                screenshot_path = await self._take_screenshot(
                    f"step_{step_number}_error",
                    task_id
                )
                result["error_screenshot"] = str(screenshot_path)
                error_screenshot_url = f"/screenshots/{screenshot_path.name}"
            except:
                pass

            # Send WebSocket update: step failed
            if ws_manager:
                await ws_manager.send_step_failed(
                    task_id,
                    step_number,
                    str(e),
                    error_screenshot_url
                )

        return result

    async def _execute_navigate(self, step: Dict, selectors: Dict):
        """Execute navigation action."""
        target = step["target"]

        # Check if target is a URL or a path reference
        if target.startswith("http"):
            url = target
        else:
            # Look up in selectors
            base_url = selectors.get("base_url", "")
            url = f"{base_url}{target}"

        await self.page.goto(url, wait_until="networkidle", timeout=30000)

    async def _execute_click(self, step: Dict, selectors: Dict):
        """Execute click action."""
        selector = self._resolve_selector(step["target"], selectors)

        # Wait for element to be visible
        await self.page.wait_for_selector(selector, state="visible", timeout=10000)

        # Click element
        await self.page.click(selector)

        # Wait for navigation if expected
        await asyncio.sleep(1)

    async def _execute_fill(self, step: Dict, selectors: Dict):
        """Execute fill action."""
        selector = self._resolve_selector(step["target"], selectors)
        value = step.get("value", "")

        # Wait for element
        await self.page.wait_for_selector(selector, state="visible", timeout=10000)

        # Clear and fill
        await self.page.fill(selector, value)

    async def _execute_select(self, step: Dict, selectors: Dict):
        """Execute select (dropdown) action."""
        selector = self._resolve_selector(step["target"], selectors)
        value = step.get("value", "")

        # Wait for element
        await self.page.wait_for_selector(selector, state="visible", timeout=10000)

        # Select option
        await self.page.select_option(selector, value)

    async def _execute_wait(self, step: Dict):
        """Execute wait action."""
        wait_time = step.get("duration_ms", 1000) / 1000
        await asyncio.sleep(wait_time)

    async def _execute_screenshot(self, step: Dict, task_id: int):
        """Execute screenshot action."""
        name = step.get("name", "screenshot")
        await self._take_screenshot(name, task_id)

    async def _execute_verify(self, step: Dict, selectors: Dict):
        """Execute verification action."""
        selector = self._resolve_selector(step["target"], selectors)
        expected_state = step.get("expected_state", "visible")

        # Verify element state
        await self.page.wait_for_selector(
            selector,
            state=expected_state,
            timeout=10000
        )

    def _resolve_selector(self, target: str, selectors: Dict) -> str:
        """
        Resolve selector from target reference.

        Args:
            target: Target reference (could be selector or lookup key)
            selectors: Selectors configuration

        Returns:
            CSS selector string
        """
        # If target is already a selector (starts with #, ., [, etc.), return as-is
        if any(target.startswith(c) for c in ["#", ".", "[", ">"]):
            return target

        # Otherwise, look up in selectors dict
        # Format: "login.username" -> selectors["login"]["username"]
        parts = target.split(".")
        current = selectors

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                # Fallback to original target if not found
                return target

        return current if isinstance(current, str) else target

    async def _take_screenshot(self, name: str, task_id: int) -> Path:
        """Take a screenshot."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"task_{task_id}_{name}_{timestamp}.png"
        screenshot_path = self.screenshots_dir / filename

        await self.page.screenshot(path=str(screenshot_path), full_page=True)
        logger.info(f"Screenshot saved: {screenshot_path}")

        return screenshot_path

    def get_execution_history(self) -> List[Dict]:
        """Get full execution history."""
        return self.execution_history

    def get_last_error(self) -> Optional[Dict]:
        """Get last error from execution history."""
        for result in reversed(self.execution_history):
            if result["status"] == "failed":
                return result
        return None
