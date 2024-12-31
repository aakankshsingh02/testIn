from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from datetime import datetime
from typing import Dict
from webdriver_manager.chrome import ChromeDriverManager
import time
import logging
from ..config import settings

logger = logging.getLogger(__name__)

class GrowwAutomation:
    def __init__(self):
        self.driver = None
        self.logged_in = False
        self.setup_driver()

    def setup_driver(self):
        """Initialize the Chrome driver with necessary settings"""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            # Uncomment below line for headless mode
            # options.add_argument('--headless')
            
            self.driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
            self.driver.implicitly_wait(10)
            logger.info("Chrome driver setup successful")
        except Exception as e:
            logger.error(f"Failed to setup Chrome driver: {str(e)}")
            raise

    async def login(self) -> bool:
        """Login to Groww platform"""
        try:
            if self.logged_in:
                return True

            self.driver.get('https://groww.in/login')
            
            # Wait for email field and enter email
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, 'login_email1'))
            )
            email_field.clear()
            email_field.send_keys(settings.GROWW_EMAIL)
            
            # Enter password
            password_field = self.driver.find_element(By.ID, 'login_password1')
            password_field.clear()
            password_field.send_keys(settings.GROWW_PASSWORD)
            
            # Click continue button
            continue_button = self.driver.find_element(By.CLASS_NAME, 'btn-primary')
            continue_button.click()
            
            # Wait for 2FA/PIN input
            logger.info("Waiting for 2FA completion...")
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'user-profile'))
            )
            
            self.logged_in = True
            logger.info("Successfully logged into Groww")
            return True

        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            raise

    async def execute_trade(self, symbol: str, quantity: int, trade_type: str) -> Dict:
        """Execute a trade on Groww"""
        if not self.logged_in:
            raise Exception("Not logged in to Groww")

        try:
            # Navigate to stock page
            self.driver.get(f'https://groww.in/stocks/{symbol}')
            time.sleep(2)  # Allow page to load
            
            # Wait for stock page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'stock-main'))
            )
            
            # Click buy/sell button
            button_text = "BUY" if trade_type.upper() == "BUY" else "SELL"
            action_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, f"//button[contains(text(), '{button_text}')]")
                )
            )
            action_button.click()
            
            # Wait for order form
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'order-form'))
            )
            
            # Enter quantity
            quantity_input = self.driver.find_element(By.NAME, 'quantity')
            quantity_input.clear()
            quantity_input.send_keys(str(quantity))
            
            # Get current market price
            price_element = self.driver.find_element(By.CLASS_NAME, 'current-price')
            current_price = float(price_element.text.replace('₹', '').replace(',', ''))
            
            # Click submit order button
            submit_button = self.driver.find_element(
                By.XPATH, "//button[contains(@class, 'btn-primary')]"
            )
            submit_button.click()
            
            # Wait for order confirmation
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'order-success'))
            )
            
            logger.info(f"Successfully executed {trade_type} order for {symbol}")
            
            return {
                'status': 'success',
                'symbol': symbol,
                'quantity': quantity,
                'price': current_price,
                'type': trade_type,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Trade execution failed for {symbol}: {str(e)}")
            raise

    async def get_stock_price(self, symbol: str) -> float:
        """Get current stock price from Groww"""
        try:
            self.driver.get(f'https://groww.in/stocks/{symbol}')
            
            price_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'current-price'))
            )
            
            price = float(price_element.text.replace('₹', '').replace(',', ''))
            return price

        except Exception as e:
            logger.error(f"Failed to get stock price for {symbol}: {str(e)}")
            raise

    async def get_holdings(self) -> List[Dict]:
        """Get current holdings from Groww"""
        try:
            self.driver.get('https://groww.in/dashboard/stocks/holdings')
            
            holdings = []
            holding_elements = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, 'holdings-row'))
            )
            
            for element in holding_elements:
                symbol = element.find_element(By.CLASS_NAME, 'holding-stock-name').text
                quantity = int(element.find_element(By.CLASS_NAME, 'holding-quantity').text)
                avg_price = float(element.find_element(By.CLASS_NAME, 'holding-avg-price')
                                .text.replace('₹', '').replace(',', ''))
                current_price = float(element.find_element(By.CLASS_NAME, 'holding-current-price')
                                    .text.replace('₹', '').replace(',', ''))
                
                holdings.append({
                    'symbol': symbol,
                    'quantity': quantity,
                    'avg_price': avg_price,
                    'current_price': current_price,
                    'pnl': (current_price - avg_price) * quantity
                })
            
            return holdings

        except Exception as e:
            logger.error(f"Failed to get holdings: {str(e)}")
            raise

    def cleanup(self):
        """Clean up browser resources"""
        try:
            if self.driver:
                self.driver.quit()
                logger.info("Browser resources cleaned up")
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")

    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup()