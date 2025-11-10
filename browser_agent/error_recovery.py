"""Advanced error recovery with LLM-based screenshot analysis."""
import asyncio
import base64
import logging
import os
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime

import httpx
from playwright.async_api import Page, Error as PlaywrightError

logger = logging.getLogger(__name__)


class RecoveryStrategy:
    """Recovery strategies for browser automation failures."""

    RETRY_SAME = "retry_same"  # Retry with same selectors
    ALTERNATIVE_SELECTOR = "alternative_selector"  # Try alternative selectors
    NAVIGATE_BACK = "navigate_back"  # Go back and retry
    RELOAD_PAGE = "reload_page"  # Reload and retry
    HUMAN_ESCALATION = "human_escalation"  # Give up, notify human


class LLMErrorAnalyzer:
    """Analyze screenshots and error states using LLM to determine recovery strategy."""

    def __init__(self):
        """Initialize LLM error analyzer."""
        self.llm_endpoint = os.getenv("LLM_ENDPOINT", "http://localhost:8000/infer")
        self.max_retries = int(os.getenv("MAX_ERROR_RECOVERY_RETRIES", "3"))
        self.timeout = httpx.Timeout(30.0)

    async def analyze_error(
        self,
        screenshot_path: Path,
        error_message: str,
        page_url: str,
        current_step: str,
        attempt_number: int = 1
    ) -> Dict:
        """
        Analyze error using screenshot and context.

        Args:
            screenshot_path: Path to screenshot of error state
            error_message: Error message from Playwright
            page_url: Current page URL
            current_step: Which step failed (login, navigate, fill_form, submit)
            attempt_number: Current attempt number

        Returns:
            Dict with recovery strategy and details
        """
        logger.info(f"Analyzing error at step '{current_step}' (attempt {attempt_number})")

        try:
            # Read screenshot as base64
            screenshot_b64 = self._encode_screenshot(screenshot_path)

            # Build analysis prompt
            prompt = self._build_analysis_prompt(
                error_message,
                page_url,
                current_step,
                attempt_number
            )

            # Call LLM with screenshot (if supported) or text-only
            analysis = await self._call_llm_with_vision(prompt, screenshot_b64)

            # Parse response to extract strategy
            strategy = self._extract_recovery_strategy(analysis)

            logger.info(f"LLM suggests recovery strategy: {strategy['action']}")
            return strategy

        except Exception as e:
            logger.error(f"Error during LLM analysis: {e}", exc_info=True)
            # Fallback to heuristic strategy
            return self._fallback_heuristic_strategy(error_message, current_step, attempt_number)

    def _encode_screenshot(self, screenshot_path: Path) -> str:
        """Encode screenshot to base64."""
        try:
            with open(screenshot_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encode screenshot: {e}")
            return ""

    def _build_analysis_prompt(
        self,
        error_message: str,
        page_url: str,
        current_step: str,
        attempt_number: int
    ) -> str:
        """Build prompt for LLM analysis."""
        prompt = f"""You are an expert web automation debugger analyzing a browser automation failure.

**Context:**
- Step: {current_step}
- Attempt: {attempt_number}
- URL: {page_url}
- Error: {error_message}

**Task:**
Analyze the screenshot (if provided) and error context to determine the best recovery strategy.

**Available Strategies:**
1. RETRY_SAME - The page looks correct, just retry with same selectors (temporary glitch)
2. ALTERNATIVE_SELECTOR - The selector is wrong/outdated, suggest alternative selectors
3. NAVIGATE_BACK - Navigation went wrong, go back and re-navigate
4. RELOAD_PAGE - Page is in bad state, reload and retry
5. HUMAN_ESCALATION - Error is not recoverable automatically

**Output Format (JSON):**
{{
  "action": "RETRY_SAME" | "ALTERNATIVE_SELECTOR" | "NAVIGATE_BACK" | "RELOAD_PAGE" | "HUMAN_ESCALATION",
  "confidence": 0-100,
  "reason": "Brief explanation of why this strategy",
  "alternative_selectors": {{
    "username": "#alternative-username-selector",
    "password": "#alternative-password-selector"
  }},
  "recommended_wait_time": 3000,
  "notes": "Additional observations from screenshot"
}}

Respond ONLY with valid JSON.
"""
        return prompt

    async def _call_llm_with_vision(self, prompt: str, screenshot_b64: str) -> str:
        """Call LLM endpoint with vision support."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # For now, call text-only LLM
                # TODO: Switch to vision model when available
                response = await client.post(
                    self.llm_endpoint,
                    json={
                        "prompt": prompt,
                        "max_tokens": 500,
                        "temperature": 0.3
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result.get("text", "")
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def _extract_recovery_strategy(self, llm_response: str) -> Dict:
        """Extract recovery strategy from LLM response."""
        import json
        import re

        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                strategy = json.loads(json_match.group())
                return strategy
            else:
                raise ValueError("No JSON found in LLM response")
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            # Return safe default
            return {
                "action": RecoveryStrategy.RETRY_SAME,
                "confidence": 50,
                "reason": "Failed to parse LLM response",
                "recommended_wait_time": 2000
            }

    def _fallback_heuristic_strategy(
        self,
        error_message: str,
        current_step: str,
        attempt_number: int
    ) -> Dict:
        """Fallback heuristic when LLM analysis fails."""
        error_lower = error_message.lower()

        # Timeout errors - just retry
        if "timeout" in error_lower or "waiting for selector" in error_lower:
            if attempt_number < 2:
                return {
                    "action": RecoveryStrategy.RETRY_SAME,
                    "confidence": 70,
                    "reason": "Timeout on first attempt, likely loading delay",
                    "recommended_wait_time": 5000
                }
            else:
                return {
                    "action": RecoveryStrategy.ALTERNATIVE_SELECTOR,
                    "confidence": 60,
                    "reason": "Multiple timeouts, selector may be wrong",
                    "recommended_wait_time": 3000
                }

        # Network errors - reload
        if "net::" in error_lower or "network" in error_lower:
            return {
                "action": RecoveryStrategy.RELOAD_PAGE,
                "confidence": 80,
                "reason": "Network error detected",
                "recommended_wait_time": 3000
            }

        # Navigation errors - go back
        if "navigation" in error_lower or "navigate" in error_lower:
            return {
                "action": RecoveryStrategy.NAVIGATE_BACK,
                "confidence": 70,
                "reason": "Navigation failure",
                "recommended_wait_time": 2000
            }

        # Too many retries - escalate
        if attempt_number >= self.max_retries:
            return {
                "action": RecoveryStrategy.HUMAN_ESCALATION,
                "confidence": 90,
                "reason": f"Max retries ({self.max_retries}) exceeded",
                "recommended_wait_time": 0
            }

        # Default: retry
        return {
            "action": RecoveryStrategy.RETRY_SAME,
            "confidence": 50,
            "reason": "Unknown error, attempting retry",
            "recommended_wait_time": 3000
        }


class AdaptiveSelectorDiscovery:
    """Discover alternative selectors when primary ones fail."""

    def __init__(self):
        """Initialize selector discovery."""
        self.llm_analyzer = LLMErrorAnalyzer()

    async def discover_login_selectors(self, page: Page) -> Optional[Dict[str, str]]:
        """
        Discover login form selectors by analyzing page structure.

        Args:
            page: Playwright page object

        Returns:
            Dict with discovered selectors or None
        """
        try:
            # Try common patterns for login forms
            patterns = [
                # Username patterns
                {
                    "username": [
                        "input[name='username']",
                        "input[name='user']",
                        "input[name='email']",
                        "input[type='email']",
                        "input[placeholder*='username' i]",
                        "input[placeholder*='email' i]",
                        "input#username",
                        "input#user",
                        "input#email"
                    ],
                    "password": [
                        "input[type='password']",
                        "input[name='password']",
                        "input[name='pass']",
                        "input#password",
                        "input#pass"
                    ],
                    "submit": [
                        "button[type='submit']",
                        "input[type='submit']",
                        "button:has-text('log in')",
                        "button:has-text('sign in')",
                        "button:has-text('login')",
                        "button:has-text('submit')"
                    ]
                }
            ]

            discovered = {}

            for field, selectors in patterns[0].items():
                for selector in selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            # Verify element is visible
                            is_visible = await element.is_visible()
                            if is_visible:
                                discovered[field] = selector
                                logger.info(f"Discovered {field} selector: {selector}")
                                break
                    except Exception:
                        continue

            if len(discovered) >= 3:  # Found all three fields
                return discovered
            else:
                logger.warning(f"Only discovered {len(discovered)}/3 login fields")
                return None

        except Exception as e:
            logger.error(f"Error discovering login selectors: {e}")
            return None

    async def discover_form_selectors(self, page: Page, field_labels: List[str]) -> Optional[Dict[str, str]]:
        """
        Discover form field selectors based on labels.

        Args:
            page: Playwright page object
            field_labels: List of expected field labels (e.g., ["Subjective", "Objective"])

        Returns:
            Dict mapping label to selector
        """
        try:
            discovered = {}

            for label in field_labels:
                # Try multiple strategies
                selectors_to_try = [
                    f"textarea[name='{label.lower()}']",
                    f"textarea#{label.lower()}",
                    f"input[name='{label.lower()}']",
                    f"input#{label.lower()}",
                    f"textarea[aria-label*='{label}' i]",
                    f"//label[contains(text(), '{label}')]/following::textarea[1]",
                    f"//label[contains(text(), '{label}')]/following::input[1]"
                ]

                for selector in selectors_to_try:
                    try:
                        if selector.startswith("//"):
                            # XPath selector
                            element = await page.query_selector(f"xpath={selector}")
                        else:
                            element = await page.query_selector(selector)

                        if element and await element.is_visible():
                            discovered[label.lower()] = selector
                            logger.info(f"Discovered {label} selector: {selector}")
                            break
                    except Exception:
                        continue

            return discovered if discovered else None

        except Exception as e:
            logger.error(f"Error discovering form selectors: {e}")
            return None


class ErrorRecoveryOrchestrator:
    """Orchestrate error recovery with LLM analysis and adaptive strategies."""

    def __init__(self):
        """Initialize error recovery orchestrator."""
        self.llm_analyzer = LLMErrorAnalyzer()
        self.selector_discovery = AdaptiveSelectorDiscovery()
        self.max_recovery_attempts = 3

    async def handle_error(
        self,
        error: Exception,
        page: Page,
        current_step: str,
        attempt_number: int,
        screenshots_dir: Path,
        task_id: int
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Handle automation error with intelligent recovery.

        Args:
            error: The exception that occurred
            page: Playwright page object
            current_step: Current automation step
            attempt_number: Current attempt number
            screenshots_dir: Directory to save screenshots
            task_id: Task ID for logging

        Returns:
            Tuple of (should_retry, error_message, recovery_data)
        """
        try:
            # Capture error screenshot
            screenshot_path = screenshots_dir / f"task_{task_id}_error_{current_step}_{attempt_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                await page.screenshot(path=str(screenshot_path))
                logger.info(f"Error screenshot saved: {screenshot_path}")
            except Exception as e:
                logger.error(f"Failed to capture error screenshot: {e}")

            # Get current page state
            page_url = page.url
            error_message = str(error)

            # Analyze error with LLM
            strategy = await self.llm_analyzer.analyze_error(
                screenshot_path,
                error_message,
                page_url,
                current_step,
                attempt_number
            )

            # Execute recovery strategy
            recovery_data = None
            should_retry = False

            if strategy["action"] == RecoveryStrategy.RETRY_SAME:
                logger.info(f"Retrying same approach after {strategy['recommended_wait_time']}ms")
                await asyncio.sleep(strategy['recommended_wait_time'] / 1000)
                should_retry = True

            elif strategy["action"] == RecoveryStrategy.RELOAD_PAGE:
                logger.info("Reloading page for recovery")
                await page.reload(wait_until="networkidle")
                await asyncio.sleep(2)
                should_retry = True

            elif strategy["action"] == RecoveryStrategy.NAVIGATE_BACK:
                logger.info("Navigating back for recovery")
                await page.go_back(wait_until="networkidle")
                await asyncio.sleep(2)
                should_retry = True

            elif strategy["action"] == RecoveryStrategy.ALTERNATIVE_SELECTOR:
                logger.info("Attempting to discover alternative selectors")

                if current_step == "login":
                    discovered = await self.selector_discovery.discover_login_selectors(page)
                    if discovered:
                        recovery_data = {"discovered_selectors": discovered}
                        should_retry = True
                        logger.info(f"Discovered alternative selectors: {discovered}")
                    else:
                        logger.warning("Failed to discover alternative selectors")

                elif current_step in ["fill_form", "fill_soap_form"]:
                    discovered = await self.selector_discovery.discover_form_selectors(
                        page,
                        ["Subjective", "Objective", "Assessment", "Plan"]
                    )
                    if discovered:
                        recovery_data = {"discovered_selectors": discovered}
                        should_retry = True
                        logger.info(f"Discovered form selectors: {discovered}")

            elif strategy["action"] == RecoveryStrategy.HUMAN_ESCALATION:
                logger.warning(f"Escalating to human: {strategy['reason']}")
                should_retry = False

            return should_retry, strategy.get("reason", error_message), recovery_data

        except Exception as e:
            logger.error(f"Error recovery itself failed: {e}", exc_info=True)
            return False, str(e), None


# Global instance
error_recovery = ErrorRecoveryOrchestrator()
