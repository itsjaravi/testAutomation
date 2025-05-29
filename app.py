import streamlit as st
import requests
import os
import json
import time
import pandas as pd
import traceback
import concurrent.futures
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

st.title("AI-Powered Regression Tester with llama3(MVP)")

uploaded_file = st.file_uploader(
    "Upload a .txt file with multiple prompts separated by 'Prompt X:' or blank line",
    type=["txt"]
)


def call_deepseek(prompt_text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    system_message = (
        "You are an AI test assistant. Convert the user instruction into JSON test steps "
        "for Selenium. Each step must include action, selector_type, selector_value, input_value. "
        "Use OPEN_URL as action if a URL is to be opened. ONLY respond with a JSON array of steps, strictly no extra text.\n\n"
        "The JSON format must be like:\n"
        '[\n'
        '  {\n'
        '    "action": "OPEN_URL",\n'
        '    "selector_type": "",\n'
        '    "selector_value": "",\n'
        '    "input_value": "https://example.com"\n'
        '  },\n'
        '  {\n'
        '    "action": "SEND_KEYS",\n'
        '    "selector_type": "ID",\n'
        '    "selector_value": "search-box",\n'
        '    "input_value": "test input"\n'
        '  },\n'
        '  {\n'
        '    "action": "CLICK",\n'
        '    "selector_type": "XPATH",\n'
        '    "selector_value": "//button[@id=\'submit\']",\n'
        '    "input_value": ""\n'
        '  }\n'
        ']'
    )

    payload = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.2,
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]

    # Try to extract JSON array from the response (assuming only JSON array is returned)
    match = re.search(r"(\[.*\])", content, re.DOTALL)
    if not match:
        raise ValueError(f"❌ AI call failed: JSON array not found. Response:\n{content}")

    json_str = match.group(1)

    try:
        steps = json.loads(json_str)
    except json.JSONDecodeError as e:
        # Provide a helpful error message if JSON is invalid
        raise ValueError(f"❌ AI returned invalid JSON: {e}\nContent:\n{json_str}")

    return steps


def wait_for_element(driver, by, value, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))


def wait_for_clickable(driver, by, value, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, value)))


def execute_test_steps(steps):
    chrome_options = Options()
    # Show browser window (remove headless for visible execution)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    results = []
    try:
        for idx, step in enumerate(steps, start=1):
            action = step.get("action", "").upper()
            selector_type = step.get("selector_type", "").lower()
            selector_value = step.get("selector_value", "")
            input_value = step.get("input_value", "")

            try:
                if action == "OPEN_URL":
                    driver.get(input_value)
                    results.append(f"✅ Step {idx}: Opened URL: {input_value}")
                    time.sleep(3)  # wait for page load

                elif action == "SEND_KEYS":
                    element = None
                    if selector_type == "id":
                        element = wait_for_element(driver, By.ID, selector_value)
                    elif selector_type == "name":
                        element = wait_for_element(driver, By.NAME, selector_value)
                    elif selector_type == "xpath":
                        element = wait_for_element(driver, By.XPATH, selector_value)
                    elif selector_type == "css_selector":
                        element = wait_for_element(driver, By.CSS_SELECTOR, selector_value)
                    elif selector_type == "class_name":
                        element = wait_for_element(driver, By.CLASS_NAME, selector_value)
                    else:
                        results.append(f"⚠️ Step {idx}: Unsupported selector_type '{selector_type}' in SEND_KEYS")
                        continue
                    element.clear()
                    element.send_keys(input_value)
                    results.append(f"✅ Step {idx}: Sent keys to '{selector_value}'")

                elif action == "CLICK":
                    element = None
                    if selector_type == "id":
                        element = wait_for_clickable(driver, By.ID, selector_value)
                    elif selector_type == "name":
                        element = wait_for_clickable(driver, By.NAME, selector_value)
                    elif selector_type == "xpath":
                        element = wait_for_clickable(driver, By.XPATH, selector_value)
                    elif selector_type == "css_selector":
                        element = wait_for_clickable(driver, By.CSS_SELECTOR, selector_value)
                    elif selector_type == "class_name":
                        element = wait_for_clickable(driver, By.CLASS_NAME, selector_value)
                    elif selector_type == "link_text":
                        element = wait_for_clickable(driver, By.LINK_TEXT, selector_value)
                    else:
                        results.append(f"⚠️ Step {idx}: Unsupported selector_type '{selector_type}' in CLICK")
                        continue
                    element.click()
                    results.append(f"✅ Step {idx}: Clicked on '{selector_value}'")
                    time.sleep(2)  # wait after click

                elif action == "WAIT":
                    try:
                        wait_seconds = float(input_value)
                        results.append(f"✅ Step {idx}: Waiting for {wait_seconds} seconds")
                        time.sleep(wait_seconds)
                    except:
                        results.append(f"⚠️ Step {idx}: Invalid wait time '{input_value}'")

                elif action == "GO_BACK":
                    driver.back()
                    results.append(f"✅ Step {idx}: Browser navigated back")
                    time.sleep(2)

                elif action == "VERIFY_TITLE":
                    title = driver.title
                    if input_value.lower() in title.lower():
                        results.append(f"✅ Step {idx}: Title verification passed: '{title}'")
                    else:
                        results.append(f"❌ Step {idx}: Title verification failed. Expected to find '{input_value}', got '{title}'")

                else:
                    results.append(f"⚠️ Step {idx}: Unknown action '{action}'")

            except Exception as e:
                results.append(f"❌ Step {idx} error: {e}")

    finally:
        driver.quit()
    return results


def split_prompts(file_text):
    parts = re.split(r'(?:Prompt\s*\d+:)|(?:\n\s*\n)', file_text)
    prompts = [p.strip() for p in parts if p.strip()]
    return prompts


def process_prompt(idx, prompt):
    try:
        steps = call_deepseek(prompt)
    except Exception as e:
        return {
            "Prompt Number": idx,
            "Prompt": prompt,
            "Test Steps": "",
            "Execution Results": f"❌ AI call failed: {e}\n{traceback.format_exc()}"
        }

    try:
        results = execute_test_steps(steps)
    except Exception as e:
        return {
            "Prompt Number": idx,
            "Prompt": prompt,
            "Test Steps": json.dumps(steps, indent=2),
            "Execution Results": f"❌ Selenium execution failed: {e}\n{traceback.format_exc()}"
        }

    return {
        "Prompt Number": idx,
        "Prompt": prompt,
        "Test Steps": json.dumps(steps, indent=2),
        "Execution Results": "\n".join(results)
    }


if uploaded_file and st.button("Run Regression on All Prompts"):
    file_text = uploaded_file.read().decode("utf-8")
    prompts = split_prompts(file_text)
    total = len(prompts)

    st.info(f"Processing {total} prompts in parallel...")

    progress_bar = st.progress(0)
    status_text = st.empty()

    results_list = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        # Running with max_workers=1 because Selenium browser is heavy and parallel may cause issues
        futures = {executor.submit(process_prompt, idx, prompt): idx for idx, prompt in enumerate(prompts, 1)}

        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            res = future.result()
            results_list.append(res)
            progress_bar.progress(i / total)
            status_text.text(f"Processed {i}/{total} prompts")

    st.success("All prompts processed!")

    # Show summary in app
    for res in sorted(results_list, key=lambda x: x["Prompt Number"]):
        st.subheader(f"Prompt {res['Prompt Number']}")
        st.markdown(f"**Prompt:**\n```\n{res['Prompt']}\n```")
        st.markdown(f"**Test Steps JSON:**\n```json\n{res['Test Steps']}\n```")
        st.markdown(f"**Execution Results:**\n```\n{res['Execution Results']}\n```")

    # Save results to Excel
    df = pd.DataFrame(results_list)
    excel_path = "test_results.xlsx"
    df.to_excel(excel_path, index=False)

    with open(excel_path, "rb") as f:
        st.download_button(
            label="Download Results as Excel",
            data=f,
            file_name="test_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("Upload a .txt file containing prompts and click 'Run Regression on All Prompts'")
