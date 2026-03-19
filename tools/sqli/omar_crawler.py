import tempfile
import json
import time
from datetime import datetime

from langchain_core.tools import tool
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from ui import ui


class WebAppCrawlerAndRequestCapture:
    def __init__(self, start_url: str):
        self.start_url = start_url
        self.visited_urls: set = set()
        self.captured_requests: list = []
        self.request_counter = 0

        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_cdp_cmd("Network.enable", {})

        ui.agent_start("CrawlerAgent", goal=f"Crawl & capture requests — {start_url}")

    # ─── Public ──────────────────────────────────────────────────────────────

    def crawl_and_capture_all(self) -> list:
        """Main entry: crawl entire site and return all captured requests."""
        self._crawl_page(self.start_url)
        return self.captured_requests

    # ─── Crawl ───────────────────────────────────────────────────────────────

    def _crawl_page(self, url: str) -> None:
        if url in self.visited_urls:
            return

        ui.section(f"Page: {url}")
        self.visited_urls.add(url)

        self.driver.get(url)
        time.sleep(3)

        ui.info("Capturing page load requests…")
        self._capture_network_logs()

        ui.info("Searching for forms…")
        self._interact_with_all_forms()

        ui.info("Searching for standalone buttons…")
        self._click_all_buttons()

        ui.info("Extracting links…")
        links = self._get_all_links()
        ui.kv("Links found", len(links))

        for link in links:
            if self._is_same_domain(link):
                self._crawl_page(link)

    # ─── Forms ───────────────────────────────────────────────────────────────

    def _interact_with_all_forms(self) -> None:
        forms = self.driver.find_elements(By.TAG_NAME, "form")

        if not forms:
            ui.log("No forms found on this page")
            return

        ui.kv("Forms found", len(forms))

        for i, form in enumerate(forms):
            try:
                action = form.get_attribute("action") or "same page"
                method = (form.get_attribute("method") or "GET").upper()
                inputs = form.find_elements(By.CSS_SELECTOR, "input, textarea, select")

                ui.tool_call(
                    f"form[{i + 1}/{len(forms)}]",
                    {"action": action, "method": method, "fields": len(inputs)},
                    agent_name="CrawlerAgent",
                )

                self._fill_all_inputs(form)
                self.driver.get_log("performance")  # flush stale logs

                submit_btn = form.find_element(
                    By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"]'
                )
                submit_btn.click()
                time.sleep(2)

                self._capture_network_logs()
                self.driver.back()
                time.sleep(1)

            except Exception as e:
                ui.error(f"Form {i + 1} error: {e}")
                continue

    def _fill_all_inputs(self, form) -> None:
        for inp in form.find_elements(
            By.CSS_SELECTOR,
            'input[type="text"], input[type="search"], input[type="email"], '
            'input[type="tel"], input[type="url"], input:not([type])',
        ):
            inp.clear()
            inp.send_keys("test")

        for inp in form.find_elements(By.CSS_SELECTOR, 'input[type="password"]'):
            inp.clear()
            inp.send_keys("Password123!")

        for inp in form.find_elements(By.CSS_SELECTOR, 'input[type="number"]'):
            inp.clear()
            inp.send_keys("123")

        for inp in form.find_elements(By.CSS_SELECTOR, 'input[type="date"]'):
            inp.send_keys("2024-01-01")

        for ta in form.find_elements(By.TAG_NAME, "textarea"):
            ta.clear()
            ta.send_keys("test message")

        for select_elem in form.find_elements(By.TAG_NAME, "select"):
            select = Select(select_elem)
            if len(select.options) > 1:
                select.select_by_index(1)

        for cb in form.find_elements(By.CSS_SELECTOR, 'input[type="checkbox"]'):
            if not cb.is_selected():
                cb.click()

        radios = form.find_elements(By.CSS_SELECTOR, 'input[type="radio"]')
        if radios:
            radios[0].click()

    # ─── Buttons ─────────────────────────────────────────────────────────────

    def _click_all_buttons(self) -> None:
        buttons = self.driver.find_elements(By.TAG_NAME, "button")
        standalone = []

        for button in buttons:
            try:
                button.find_element(By.XPATH, "./ancestor::form")
            except Exception:
                standalone.append(button)

        if not standalone:
            ui.log("No standalone buttons found")
            return

        ui.kv("Standalone buttons", len(standalone))

        for i, button in enumerate(standalone):
            try:
                label = (
                    button.text or button.get_attribute("value") or f"Button {i + 1}"
                )
                ui.tool_call(
                    f"button[{i + 1}/{len(standalone)}]",
                    {"label": label},
                    agent_name="CrawlerAgent",
                )

                self.driver.get_log("performance")
                button.click()
                time.sleep(2)

                self._capture_network_logs()
                self.driver.back()
                time.sleep(1)

            except Exception as e:
                ui.error(f"Button {i + 1} error: {e}")
                continue

    # ─── Network capture ─────────────────────────────────────────────────────

    def _capture_network_logs(self) -> None:
        logs = self.driver.get_log("performance")
        new_requests = 0

        for log in logs:
            try:
                message = json.loads(log["message"])["message"]
                if message["method"] != "Network.requestWillBeSent":
                    continue

                request = message["params"]["request"]

                # Skip static assets
                if any(
                    ext in request["url"]
                    for ext in [
                        ".css",
                        ".js",
                        ".png",
                        ".jpg",
                        ".gif",
                        ".woff",
                        ".svg",
                        ".ico",
                    ]
                ):
                    continue

                self.request_counter += 1
                captured = {
                    "id": self.request_counter,
                    "url": request["url"],
                    "method": request["method"],
                    "headers": request["headers"],
                    "body": request.get("postData"),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                self.captured_requests.append(captured)
                new_requests += 1
                self._display_request(captured)

            except Exception:
                continue

        if new_requests == 0:
            ui.log("No new requests captured")

    def _display_request(self, request: dict) -> None:
        """Render a single captured request as a tool-result panel."""
        lines = [
            f"[grey50]Method:[/grey50]  [bold #ff5308]{request['method']}[/bold #ff5308]",
            f"[grey50]URL:[/grey50]     [#00bfff]{request['url']}[/#00bfff]",
            f"[grey50]Time:[/grey50]    [grey50]{request['timestamp']}[/grey50]",
        ]

        if request["body"]:
            preview = request["body"][:200] + (
                "…" if len(request["body"]) > 200 else ""
            )
            lines.append(f"[grey50]Body:[/grey50]    {preview}")

        for header in ("Content-Type", "Cookie", "Authorization"):
            if header in request["headers"]:
                val = request["headers"][header]
                if len(val) > 60:
                    val = val[:60] + "…"
                lines.append(f"[grey50]{header}:[/grey50]  {val}")

        ui.tool_result(
            f"request #{request['id']}",
            "\n".join(lines),
            agent_name="CrawlerAgent",
        )

    # ─── Links / domain helpers ───────────────────────────────────────────────

    def _get_all_links(self) -> list[str]:
        links = []
        for link in self.driver.find_elements(By.TAG_NAME, "a"):
            href = link.get_attribute("href")
            if href and href.startswith("http"):
                links.append(href)
        return list(set(links))

    def _is_same_domain(self, url: str) -> bool:
        from urllib.parse import urlparse

        return urlparse(self.start_url).netloc == urlparse(url).netloc

    # ─── Export ───────────────────────────────────────────────────────────────

    def export_requests(self, filename: str = "captured_requests.json") -> None:
        with open(filename, "w") as f:
            json.dump(self.captured_requests, f, indent=2)

        methods: dict = {}
        for req in self.captured_requests:
            methods[req["method"]] = methods.get(req["method"], 0) + 1

        ui.engagement_summary(
            status="exported",
            data={
                "Output file": filename,
                "Total requests": len(self.captured_requests),
                "Pages visited": len(self.visited_urls),
                **{f"Method {m}": c for m, c in methods.items()},
            },
        )

    def cleanup(self) -> None:
        self.driver.quit()
        ui.agent_done("CrawlerAgent", summary="Browser closed")


# ─── LangChain tool ───────────────────────────────────────────────────────────


@tool
def run_omar_crawler(target_url: str):
    """
    Crawls a web application and captures all HTTP requests in real-time.
    Not intended for direct LLM invocation — called by the recon node.
    """
    crawler = WebAppCrawlerAndRequestCapture(target_url)

    temp_file = tempfile.NamedTemporaryFile(
        prefix="captured_requests_",
        suffix=".json",
        delete=False,
    )
    temp_file_path = temp_file.name
    temp_file.close()

    all_requests: list = []
    captured_json: list = []

    try:
        all_requests = crawler.crawl_and_capture_all()
        crawler.export_requests(temp_file_path)
        with open(temp_file_path, "r", encoding="utf-8") as f:
            captured_json = json.load(f)
    finally:
        crawler.cleanup()

    sanitized_requests = []
    for req in captured_json:
        sanitized = dict(req)
        sanitized.pop("timestamp", None)
        headers = sanitized.get("headers") or {}
        if isinstance(headers, dict):
            sanitized["headers"] = {
                k: v
                for k, v in headers.items()
                if k.lower() != "user-agent" and not k.lower().startswith("sec-ch-")
            }
        sanitized_requests.append(sanitized)

    return {
        "pages_visited": len(crawler.visited_urls),
        "requests_captured": len(all_requests),
        "captured_requests": sanitized_requests,
    }


# ─── Manual test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        ui.error("Usage: python crawler.py <target_url>")
        ui.log("Example: python crawler.py http://localhost:8000")
        sys.exit(1)

    result = run_omar_crawler.invoke({"target_url": sys.argv[1]})

    ui.section("Crawler Result (LLM payload)")
    ui.panel(json.dumps(result, indent=2), title="run_omar_crawler output", style="dim")
