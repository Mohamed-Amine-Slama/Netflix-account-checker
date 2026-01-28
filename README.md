# Netflix Account Checker - Advanced Cybersecurity Edition

Professional-grade Netflix account checker with CSRF token extraction, session management, proxy rotation, and advanced authentication flow. Designed for cybersecurity research and educational purposes.

## Features

✅ **CSRF Token Extraction** - Automatically extracts CSRF tokens from login pages using multiple pattern detection
✅ **Advanced Authentication Flow** - Simulates real login process with proper headers and session management  
✅ **Proxy Support** - Rotate through multiple proxies for IP anonymity and bypass detection
✅ **Account Type Detection** - Automatically categorizes results (subscription/free/invalid)
✅ **Cookie Management** - Persists and manages session cookies in encrypted pickle format
✅ **Retry Strategy** - Automatic retry logic with exponential backoff for failed requests
✅ **Session Management** - Maintains HTTP session with connection pooling and persistent cookies
✅ **Multi-Pattern Token Detection** - Regex, BeautifulSoup, and JSON parsing for token extraction
✅ **Formatted Output** - Results displayed with visual indicators (✅ ⚠️ ❌) by account status
✅ **Detailed Logging** - Comprehensive debug output for account checking process
✅ **Flexible Output** - JSON export with timestamped filenames

## Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create an `accounts.json` file:**
   For Netflix mode, use email/password pairs:
   ```json
   [
       {
           "email": "user@example.com",
           "password": "password123"
       },
       {
           "email": "another@example.com",
           "password": "securepass456"
       }
   ]
   ```

   For legacy mode, use simple string array:
   ```json
   [
       "username1",
       "username2"
   ]
   ```

3. **Optional: Create a `proxies.txt` file for proxy support:**
   ```
   10.10.1.10:3128
   10.10.1.11:1080
   192.168.1.100:8080
   ```

## Usage

### Netflix Advanced Mode (Default)
```bash
python3 checker.py accounts.json --mode netflix --output ./results
```

### With Proxy Support
```bash
python3 checker.py accounts.json --proxy-file proxies.txt --output ./results
```

### Options
```bash
python3 checker.py accounts.json [OPTIONS]

Options:
  --mode {netflix,legacy}    Check mode (default: netflix)
  --proxy-file FILE          Path to proxy file (one proxy per line)
  --output DIRECTORY         Save results to JSON file
  --cookies-dir DIRECTORY    Directory to store session cookies
  --verbose, -v              Show full result details
```


### Legacy Platform Mode
```bash
python3 checker.py accounts.json --mode legacy --output ./results
```

### With Verbose Output
```bash
python3 checker.py accounts.json --mode netflix --verbose
```

### Custom Cookies Directory
```bash
python3 checker.py accounts.json --cookies-dir ./my_cookies
```

## Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `accounts_file` | Path to JSON file with accounts | Required |
| `--mode` | Check mode: `netflix` or `legacy` | netflix |
| `--output` | Output file/directory path | stdout |
| `--cookies-dir` | Directory for cookie storage | ./cookies |
| `--verbose` | Enable verbose logging | False |
| `--help` | Show help message | - |

## Output Format

```json
{
  "email": "user@example.com",
  "status": "authenticated",
  "details": {
    "csrf_extracted": true,
    "initial_cookies": 5,
    "authenticated": true,
    "status_code": 200,
    "cookies_saved": true,
    "cookies_file": "./cookies/user_example_com_cookies.pkl",
    "timestamp": "2026-01-26T12:34:56.789123"
  }
}
```

## Architecture

### NetflixChecker Class

#### Key Methods:

- **`fetch_login_page()`** - Retrieves login page and extracts CSRF tokens
- **`authenticate(email, password, csrf_token)`** - Performs account authentication
- **`_extract_csrf_token(html_content)`** - Multi-pattern CSRF extraction
- **`_verify_authentication(response)`** - Validates authentication success
- **`_save_cookies(email)`** - Persists session cookies
- **`load_cookies(email)`** - Loads previously saved cookies
- **`check_account(email, password)`** - Complete account checking flow

#### Session Features:

- **Retry Strategy**: 3 retries with exponential backoff for network failures
- **User Agent Rotation**: Modern Chrome user agent for realistic requests
- **Session Pooling**: HTTP connection pooling for efficiency
- **Cookie Persistence**: Pickle-based cookie storage for session resumption

## Security Considerations

⚠️ **Educational Use Only** - This tool is designed for authorized security testing and educational purposes only.

- Never use against systems you don't own or have explicit permission to test
- Always handle credentials securely - avoid hardcoding credentials
- Respect rate limits and implement delays between requests
- Use VPN/proxy responsibly to avoid IP blocking
- Follow all applicable laws and regulations

## Technical Details

### CSRF Token Extraction Patterns

The tool attempts extraction using multiple patterns:
1. JSON-based CSRF token (`"csrfToken": "..."`)
2. Object property format (`csrf: '...'`)
3. HTML input element (`<input name='csrf' value='...'>`)
4. Data attribute format (`data-csrf='...'`)
5. BeautifulSoup fallback parsing

### Authentication Indicators

Success is verified by checking:
- Redirect to authenticated endpoints (`/browse`, `/profiles`)
- Presence of authenticated content markers
- Absence of error messages
- HTTP 200 status code

## Troubleshooting

### "CSRF Token not found"
- Netflix may have updated their page structure
- Try updating BeautifulSoup: `pip install --upgrade beautifulsoup4`

### "Connection timeout"
- Check your internet connection
- Try with `--verbose` flag for more details
- Netflix may be blocking the user agent

### Cookies not saving
- Ensure `./cookies` directory is writable
- Check disk space availability
- Verify file permissions

## Project Structure

```
checker/
├── checker.py           # Main application
├── accounts.json        # Account credentials
├── requirements.txt     # Python dependencies
├── README.md           # This file
└── cookies/            # Persistent session cookies
```

## Version History

**v2.0** (Current)
- Advanced Netflix authentication flow
- CSRF token extraction with multiple patterns
- Session cookie management
- Retry logic with exponential backoff
- Improved error handling and logging

**v1.0**
- Basic platform username checker
- Simple HTTP request validation

## License

For educational and authorized security testing purposes only.

---

**Disclaimer**: This tool should only be used for authorized security testing on systems you own or have explicit permission to test. Unauthorized access to computer systems is illegal.


The output is a JSON array of objects, where each object represents the result of a check.

**Example of a successful check:**

```json
{
    "platform": "github",
    "username": "testuser",
    "exists": true,
    "url": "https://github.com/testuser",
    "status_code": 200
}
```

**Example of a failed check:**

```json
{
    "platform": "twitter",
    "username": "nonexistentuser",
    "exists": false,
    "url": "https://twitter.com/nonexistentuser",
    "status_code": 404
}
```

## How it Works

The tool constructs a URL for each username and platform (e.g., `https://github.com/username`) and makes an HTTP GET request to that URL. It then checks the HTTP status code of the response to determine if the account exists. A status code of 200 usually indicates that the account exists, while a 404 status code usually indicates that it does not.

