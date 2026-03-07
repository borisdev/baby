"""Scrape allergen food guides from SolidStarts."""

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SECRETS_FILE = Path(__file__).parent / ".secrets"

# Allergen foods to scrape, mapped to their SolidStarts URL slugs
ALLERGEN_FOODS = {
    "Egg": ["egg"],
    "Peanut": ["peanut"],
    "Milk / Dairy": ["yogurt", "milk"],
    "Wheat": ["wheat"],
    "Soy": ["tofu", "soy"],
    "Sesame": ["sesame-seed"],
    "Fish": ["salmon"],
    "Tree nuts": ["almond", "cashew", "walnut"],
    "Shellfish": ["shrimp"],
}

BASE_URL = "https://solidstarts.com"


def load_secrets() -> dict[str, str]:
    secrets = {}
    if not SECRETS_FILE.exists():
        print(f"ERROR: {SECRETS_FILE} not found. Copy .secrets.example to .secrets and fill in your credentials.")
        sys.exit(1)
    for line in SECRETS_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            secrets[key.strip()] = val.strip()
    return secrets


def login(page, email: str, password: str):
    print("Logging in...")
    page.goto(f"{BASE_URL}/login/")
    page.wait_for_load_state("networkidle")

    # Try filling the email/password fields
    email_input = page.locator('input[type="email"], input[name="email"]').first
    password_input = page.locator('input[type="password"], input[name="password"]').first

    email_input.wait_for(state="visible", timeout=15000)
    email_input.fill(email)
    password_input.fill(password)

    # Click the submit/login button
    submit_btn = page.locator('button[type="submit"]').first
    submit_btn.click()

    # Wait for navigation after login
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)
    print("Logged in successfully.")


def scrape_food_page(page, slug: str) -> dict:
    url = f"{BASE_URL}/foods/{slug}/"
    print(f"  Scraping {url} ...")
    page.goto(url)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    data = {"slug": slug, "url": url, "title": "", "sections": {}}

    # Get the page title
    title_el = page.locator("h1").first
    if title_el.count():
        data["title"] = title_el.inner_text()

    # Extract main content area
    content = page.locator("main, article, .entry-content, [class*='food-page'], [class*='FoodPage']").first
    if not content.count():
        content = page.locator("body")

    # Get all text content organized by headings
    elements = content.locator("h2, h3, p, ul, ol, li, table").all()
    current_section = "Overview"
    section_text = []

    for el in elements:
        tag = el.evaluate("el => el.tagName.toLowerCase()")
        text = el.inner_text().strip()
        if not text:
            continue

        if tag in ("h2", "h3"):
            if section_text:
                data["sections"][current_section] = "\n".join(section_text)
            current_section = text
            section_text = []
        elif tag == "li":
            section_text.append(f"- {text}")
        elif tag == "table":
            section_text.append(f"[TABLE] {text}")
        else:
            section_text.append(text)

    if section_text:
        data["sections"][current_section] = "\n".join(section_text)

    return data


def main():
    secrets = load_secrets()
    email = secrets.get("solidstarts.com-login-email", "") or secrets.get("SOLIDSTARTS_EMAIL", "")
    password = secrets.get("solidstarts.com-login-password", "") or secrets.get("SOLIDSTARTS_PASSWORD", "")

    if not email or not password:
        print("ERROR: SOLIDSTARTS_EMAIL and SOLIDSTARTS_PASSWORD must be set in .secrets")
        sys.exit(1)

    all_data = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=False so you can see it working
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = context.new_page()

        login(page, email, password)

        for allergen, slugs in ALLERGEN_FOODS.items():
            print(f"\n--- {allergen} ---")
            foods = []
            for slug in slugs:
                food_data = scrape_food_page(page, slug)
                foods.append(food_data)
            all_data[allergen] = foods

        browser.close()

    # Save raw data
    output_file = Path(__file__).parent / "solidstarts_data.json"
    output_file.write_text(json.dumps(all_data, indent=2, ensure_ascii=False))
    print(f"\nData saved to {output_file}")


if __name__ == "__main__":
    main()
