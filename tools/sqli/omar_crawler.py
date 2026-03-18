import tempfile
from langchain_core.tools import tool

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import json
import time
from datetime import datetime


class WebAppCrawlerAndRequestCapture:
    def __init__(self, start_url):
        self.start_url = start_url
        self.visited_urls = set()
        self.captured_requests = []
        self.request_counter = 0

        # Setup headless browser
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_cdp_cmd("Network.enable", {})

        print("=" * 80)
        print("REAL-TIME REQUEST CAPTURE")
        print("=" * 80)

    def crawl_and_capture_all(self):
        """Main function: crawl entire site and capture all requests"""
        self._crawl_page(self.start_url)
        return self.captured_requests

    def _crawl_page(self, url):
        """Recursively crawl pages and capture requests"""

        if url in self.visited_urls:
            return

        print(f"\n{'=' * 80}")
        print(f"📄 VISITING PAGE: {url}")
        print(f"{'=' * 80}")
        self.visited_urls.add(url)

        self.driver.get(url)
        time.sleep(3)  # Let JS load

        # 1. Capture all network requests on page load
        print("\n🔍 Capturing page load requests...")
        self._capture_network_logs()

        # 2. Find and interact with ALL forms
        print("\n📝 Searching for forms...")
        self._interact_with_all_forms()

        # 3. Find and click ALL buttons (non-form)
        print("\n🔘 Searching for standalone buttons...")
        self._click_all_buttons()

        # 4. Find all links to other pages
        print("\n🔗 Extracting links to other pages...")
        links = self._get_all_links()
        print(f"   Found {len(links)} links on this page")

        # 5. Recursively visit other pages
        for link in links:
            if self._is_same_domain(link):
                self._crawl_page(link)

    def _interact_with_all_forms(self):
        """Find all forms and submit each with test data"""

        forms = self.driver.find_elements(By.TAG_NAME, "form")

        if not forms:
            print("   ℹ️  No forms found on this page")
            return

        print(f"   ✓ Found {len(forms)} form(s)")

        for i, form in enumerate(forms):
            print(f"\n   📋 FORM {i + 1}/{len(forms)}:")

            try:
                # Get form details before filling
                form_action = form.get_attribute("action") or "same page"
                form_method = form.get_attribute("method") or "GET"
                print(f"      Action: {form_action}")
                print(f"      Method: {form_method}")

                # Count inputs
                inputs = form.find_elements(By.CSS_SELECTOR, "input, textarea, select")
                print(f"      Inputs: {len(inputs)} field(s)")

                # Fill all inputs in this form
                print("      ⚙️  Filling form fields...")
                self._fill_all_inputs(form)

                # Clear old logs
                self.driver.get_log("performance")

                # Submit form
                print("      🚀 Submitting form...")
                submit_btn = form.find_element(
                    By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"]'
                )
                submit_btn.click()

                time.sleep(2)

                # Capture the request
                self._capture_network_logs()

                # Go back to original page state
                self.driver.back()
                time.sleep(1)

            except Exception as e:
                print(f"      ❌ Error with form {i + 1}: {e}")
                continue

    def _fill_all_inputs(self, form):
        """Auto-fill every input type in a form"""

        # Text inputs
        text_inputs = form.find_elements(
            By.CSS_SELECTOR,
            'input[type="text"], input[type="search"], input[type="email"], input[type="tel"], input[type="url"], input:not([type])',
        )
        for inp in text_inputs:
            inp.clear()
            inp.send_keys("test")

        # Password
        password_inputs = form.find_elements(By.CSS_SELECTOR, 'input[type="password"]')
        for inp in password_inputs:
            inp.clear()
            inp.send_keys("Password123!")

        # Number
        number_inputs = form.find_elements(By.CSS_SELECTOR, 'input[type="number"]')
        for inp in number_inputs:
            inp.clear()
            inp.send_keys("123")

        # Date/Time
        date_inputs = form.find_elements(By.CSS_SELECTOR, 'input[type="date"]')
        for inp in date_inputs:
            inp.send_keys("2024-01-01")

        # Textareas
        textareas = form.find_elements(By.TAG_NAME, "textarea")
        for ta in textareas:
            ta.clear()
            ta.send_keys("test message")

        # Dropdowns (select)
        selects = form.find_elements(By.TAG_NAME, "select")
        for select_elem in selects:
            select = Select(select_elem)
            # Try each option in the dropdown
            options = select.options
            if len(options) > 1:  # Skip first (usually "All" or empty)
                select.select_by_index(1)

        # Checkboxes
        checkboxes = form.find_elements(By.CSS_SELECTOR, 'input[type="checkbox"]')
        for cb in checkboxes:
            if not cb.is_selected():
                cb.click()

        # Radio buttons
        radios = form.find_elements(By.CSS_SELECTOR, 'input[type="radio"]')
        if radios:
            radios[0].click()  # Click first radio

    def _click_all_buttons(self):
        """Click all standalone buttons (not in forms)"""

        # Find buttons NOT inside forms
        buttons = self.driver.find_elements(By.TAG_NAME, "button")
        standalone_buttons = []

        for button in buttons:
            try:
                button.find_element(By.XPATH, "./ancestor::form")
                continue  # Skip, it's in a form
            except Exception:
                standalone_buttons.append(button)

        if not standalone_buttons:
            print("   ℹ️  No standalone buttons found")
            return

        print(f"   ✓ Found {len(standalone_buttons)} standalone button(s)")

        for i, button in enumerate(standalone_buttons):
            try:
                button_text = (
                    button.text or button.get_attribute("value") or f"Button {i + 1}"
                )
                print(
                    f"\n   🔘 BUTTON {i + 1}/{len(standalone_buttons)}: '{button_text}'"
                )

                # Clear logs
                self.driver.get_log("performance")

                # Click button
                print("      🚀 Clicking button...")
                button.click()
                time.sleep(2)

                # Capture request
                self._capture_network_logs()

                # Navigate back
                self.driver.back()
                time.sleep(1)

            except Exception as e:
                print(f"      ❌ Error clicking button: {e}")
                continue

    def _capture_network_logs(self):
        """Extract HTTP requests from browser performance logs"""

        logs = self.driver.get_log("performance")
        new_requests = 0

        for log in logs:
            try:
                message = json.loads(log["message"])["message"]

                if message["method"] == "Network.requestWillBeSent":
                    request = message["params"]["request"]

                    # Filter out static resources
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

                    captured_request = {
                        "id": self.request_counter,
                        "url": request["url"],
                        "method": request["method"],
                        "headers": request["headers"],
                        "body": request.get("postData"),
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }

                    self.captured_requests.append(captured_request)
                    new_requests += 1

                    # REAL-TIME DISPLAY
                    self._display_request(captured_request)

            except Exception:
                continue

        if new_requests == 0:
            print("      ℹ️  No new requests captured")

    def _display_request(self, request):
        """Display captured request in real-time with formatting"""

        print(f"\n      {'─' * 70}")
        print(f"      🎯 REQUEST #{request['id']} CAPTURED")
        print(f"      {'─' * 70}")
        print(f"      Method:    {request['method']}")
        print(f"      URL:       {request['url']}")
        print(f"      Time:      {request['timestamp']}")

        # Display body if exists
        if request["body"]:
            body_preview = request["body"][:200]  # First 200 chars
            if len(request["body"]) > 200:
                body_preview += "..."
            print(f"      Body:      {body_preview}")

        # Display important headers
        important_headers = ["Content-Type", "Cookie", "Authorization"]
        for header in important_headers:
            if header in request["headers"]:
                value = request["headers"][header]
                if len(value) > 60:
                    value = value[:60] + "..."
                print(f"      {header}: {value}")

        print(f"      {'─' * 70}")

    def _get_all_links(self):
        """Extract all links from current page"""

        links = []
        link_elements = self.driver.find_elements(By.TAG_NAME, "a")

        for link in link_elements:
            href = link.get_attribute("href")
            if href and href.startswith("http"):
                links.append(href)

        return list(set(links))  # Deduplicate

    def _is_same_domain(self, url):
        """Check if URL is same domain as start URL"""
        from urllib.parse import urlparse

        start_domain = urlparse(self.start_url).netloc
        url_domain = urlparse(url).netloc

        return start_domain == url_domain

    def export_requests(self, filename="captured_requests.json"):
        """Save all captured requests to file"""

        print(f"\n{'=' * 80}")
        print("💾 EXPORTING RESULTS")
        print(f"{'=' * 80}")

        with open(filename, "w") as f:
            json.dump(self.captured_requests, f, indent=2)

        print(f"✓ Exported {len(self.captured_requests)} requests to {filename}")

        # Summary
        methods = {}
        for req in self.captured_requests:
            method = req["method"]
            methods[method] = methods.get(method, 0) + 1

        print("\n📊 SUMMARY:")
        print(f"   Total Requests: {len(self.captured_requests)}")
        print(f"   Pages Visited:  {len(self.visited_urls)}")
        print("\n   By Method:")
        for method, count in methods.items():
            print(f"      {method}: {count}")

    def cleanup(self):
        self.driver.quit()


@tool
def run_omar_crawler(target_url: str):
    """
    A tool that crawls a web application and captures all HTTP requests in real-time.
    Right now I am not putting more explanation since this wont be called by LLM"""
    crawler = WebAppCrawlerAndRequestCapture(target_url)
    all_requests = []
    captured_json = []

    temp_file = tempfile.NamedTemporaryFile(
        prefix="captured_requests_",
        suffix=".json",
        delete=False,
    )
    temp_file_path = temp_file.name
    temp_file.close()

    try:
        all_requests = crawler.crawl_and_capture_all()
        crawler.export_requests(temp_file_path)
        with open(temp_file_path, "r", encoding="utf-8") as f:
            captured_json = json.load(f)
    finally:
        crawler.cleanup()

    sanitized_requests = []
    for req in captured_json:
        sanitized_req = dict(req)
        sanitized_req.pop("timestamp", None)

        headers = sanitized_req.get("headers") or {}
        if isinstance(headers, dict):
            filtered_headers = {
                key: value
                for key, value in headers.items()
                if key.lower() != "user-agent" and not key.lower().startswith("sec-ch-")
            }
            sanitized_req["headers"] = filtered_headers

        sanitized_requests.append(sanitized_req)

    return {
        "pages_visited": len(crawler.visited_urls),
        "requests_captured": len(all_requests),
        "captured_requests": sanitized_requests,
    }


# Usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python crawler.py <target_url>")
        print("Example: python crawler.py http://localhost:8000")
        sys.exit(1)

    result = run_omar_crawler.invoke({"target_url": sys.argv[1]})
    print("\n=== CRAWLER RESULT (LLM GETS THIS) ===")
    print(json.dumps(result, indent=2))

    # target_url = sys.argv[1]

    # crawler = WebAppCrawlerAndRequestCapture(target_url)

    # try:
    #     all_requests = crawler.crawl_and_capture_all()
    #     crawler.export_requests()
    # finally:
    #     crawler.cleanup()

    # print(f"\n{'=' * 80}")
    # print("✅ SCAN COMPLETE")
    # print(f"{'=' * 80}\n")
